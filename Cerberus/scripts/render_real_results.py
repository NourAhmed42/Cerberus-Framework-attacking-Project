"""Rebuild the real-result PDF from its explanatory source and saved captures.

This renderer does not scan anything. Public tests are an explicit separate
operation in scripts/live_tests/public_tool_results.py.
"""

import argparse
import contextlib
import hashlib
import html
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "REAL_RESULTS.md"
DATA = ROOT / "docs" / "real_results.json"
OUTPUT = ROOT / "docs" / "real result.pdf"

CSS = """
@page {
  size: A4; margin: 16mm 18mm 19mm;
  @bottom-left { content: "CERBERUS  /  REAL TOOL RESULTS";
    color: #73849b; font: 7.2pt "DejaVu Sans", sans-serif; }
  @bottom-right { content: "Page " counter(page) " / " counter(pages);
    color: #73849b; font: 7.2pt "DejaVu Sans", sans-serif; }
}
html { color: #26364b; font: 9.2pt/1.4 "DejaVu Sans", sans-serif; }
body { margin: 0; }
h1, h2, h3 { color: #102b49; line-height: 1.18; break-after: avoid; }
h1 { font-size: 20.5pt; margin: 0 0 4mm; letter-spacing: -0.35pt; }
h2 { font-size: 13pt; margin: 4.5mm 0 2mm; }
h3 { font-size: 10.3pt; margin: 3.8mm 0 1.5mm; }
p { margin: 0 0 2.7mm; }
a { color: #007d88; text-decoration: none; }
strong { color: #132f4c; }
ul { margin: 1.5mm 0 3mm; padding-left: 5mm; }
li { margin: 0 0 1.6mm; }
blockquote { margin: 3mm 0; padding: 3mm 4mm; border-left: 3pt solid #0a9a9b;
  background: #eaf7f6; border-radius: 1.5mm; }
blockquote p:last-child { margin-bottom: 0; }
table { width: 100%; border-collapse: collapse; margin: 2.5mm 0 4mm; font-size: 8.1pt; }
tr { break-inside: avoid; }
th { background: #143450; color: white; text-align: left; font-weight: 700; }
th, td { padding: 1.8mm 2.2mm; vertical-align: top; border: 0.3pt solid #d4dfea; }
tbody tr:nth-child(even) { background: #f2f7fa; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8pt;
  color: #075c6a; overflow-wrap: anywhere; }
pre { margin: 1.5mm 0 2.5mm; padding: 2.7mm 3mm; background: #10283e;
  border-radius: 1.5mm; color: #f2f8fc; white-space: pre-wrap;
  overflow-wrap: anywhere; }
pre code { font-size: 7.4pt; line-height: 1.29; color: #f2f8fc; }
.page-break { break-before: page; }
"""


def _safe_inline(value: Any) -> str:
    """External text is never allowed to become active HTML/Markdown markup."""
    result = html.escape(str(value), quote=True).replace("\n", " ").replace("\r", " ")
    for char in ("\\", "`", "*", "_", "[", "]", "|", "{", "}"):
        result = result.replace(char, "\\" + char)
    return result


def _code_block(value: Any) -> str:
    text = str(value or "No real output recorded.")[:16000]
    # Choose a fence longer than any consecutive backtick sequence in the data.
    longest = max((len(match.group()) for match in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def _display(entry: dict[str, Any]) -> dict[str, Any] | None:
    latest = entry.get("latest") or {}
    if latest.get("status") == "captured":
        return latest
    previous = entry.get("last_success")
    if isinstance(previous, dict) and previous.get("status") == "captured":
        return previous
    if latest.get("status") == "failed":
        return latest
    return None


def _status(entry: dict[str, Any]) -> str:
    latest = entry.get("latest") or {}
    status = str(latest.get("status", "not_tested")).replace("_", " ").upper()
    time = latest.get("at_utc") or "not captured"
    message = latest.get("message") or ""
    text = f"**Latest attempt:** {_safe_inline(status)} · {_safe_inline(time)}."
    if message:
        text += f" {_safe_inline(message)}"
    previous = _display(entry)
    if previous is not None:
        if latest.get("status") == "captured":
            label = "This capture"
        elif previous is latest:
            label = "Failed attempt output (not a successful result)"
        else:
            label = "Previous successful capture"
        text += (
            f"\n\n**{label}:** {_safe_inline(previous.get('at_utc', 'unknown time'))}"
            f" · Target: `{_safe_inline(previous.get('target', 'unknown'))}`"
            f" · Version: {_safe_inline(previous.get('version', 'unknown'))}."
        )
    return text


def _format_framework_output(raw: Any, tool: str) -> str:
    """Produce a compact, labelled view of real Finding.to_dict() fields."""
    if not raw:
        return "No real output recorded."
    try:
        findings = json.loads(str(raw))
        if not isinstance(findings, list):
            raise ValueError
        blocks = []
        for finding in findings:
            meta = finding.get("metadata") or {}
            lines = [
                f"[{str(finding.get('severity', 'unknown')).upper()}] {finding.get('title', '')}",
                f"target: {finding.get('target', '')}",
                f"module: {finding.get('module_name', '')}",
            ]
            if tool == "nmap":
                lines.append(f"probed TCP ports: {meta.get('probed_ports', [])}")
                lines.append(f"open TCP ports: {meta.get('open_ports', [])}")
                lines.append("services:")
                for service in meta.get("services", []):
                    description = " ".join(
                        str(service.get(key, "")) for key in ("service", "product", "version")
                    ).strip()
                    lines.append(f"  {service.get('port')}/tcp  {description}")
            elif tool == "sqlmap":
                lines.append(f"parameter: {meta.get('parameter', '')} ({meta.get('method', '')})")
                lines.append(f"CWE: {finding.get('cwe_id', '')}")
                lines.append(f"DBMS: {meta.get('dbms', '')}")
                for technique in meta.get("techniques", []):
                    lines.append(f"technique: {technique.get('type', '')}")
                    lines.append(f"  {technique.get('title', '')}")
            lines.append(f"confidence: {finding.get('confidence', '')}")
            lines.append(f"verified: {str(finding.get('verified', False)).lower()}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks) or "The framework returned no findings."
    except (ValueError, TypeError, AttributeError):
        return str(raw)


def _format_nmap_xml(raw: Any) -> str:
    """Show selected captured XML attributes without changing their values."""
    if not raw:
        return "No real output recorded."
    try:
        wrapper = ET.fromstring(f"<captured>{raw}</captured>")  # noqa: S314 — saved XML excerpt
        pieces = []
        for name, attributes in (
            ("status", ("state", "reason")),
            ("address", ("addr", "addrtype")),
        ):
            original = wrapper.find(name)
            if original is not None:
                element = ET.Element(
                    name,
                    {key: original.attrib[key] for key in attributes if key in original.attrib},
                )
                pieces.append(ET.tostring(element, encoding="unicode"))
        for original in wrapper.findall("ports/port"):
            port = ET.Element("port", dict(original.attrib))
            for child_name, child_attributes in (
                ("state", ("state", "reason")),
                ("service", ("name", "product", "version", "method", "conf")),
            ):
                child = original.find(child_name)
                if child is not None:
                    ET.SubElement(
                        port,
                        child_name,
                        {key: child.attrib[key] for key in child_attributes if key in child.attrib},
                    )
            ET.indent(port, space="  ")
            pieces.append(ET.tostring(port, encoding="unicode"))
        return "\n".join(pieces) or str(raw)
    except (ET.ParseError, ValueError):
        return str(raw)


def _format_metasploit_local(entry: dict[str, Any]) -> str:
    """Keep local genuine checks distinct from the public-test status."""
    check = entry.get("local_integration_check") or entry.get("local_standalone_check") or {}
    if not check:
        return "No real local standalone check recorded."
    lines = [
        f"Completed (UTC): {check.get('at_utc', 'unknown')}",
        f"Version: {check.get('version', 'unknown')}",
        f"Target: {check.get('target', 'unknown')} (temporary local listener)",
        f"Real tool check: {check.get('tool_status', 'unknown')}",
        f"Cerberus connection: {check.get('integration_status', 'unknown')}",
    ]
    if check.get("finding_title"):
        lines.extend(
            [
                f"Framework finding: {check['finding_title']}",
                f"Open ports: {check.get('open_ports', [])}",
            ]
        )
    lines.extend(
        [
            "Selected real Metasploit console output:",
            str(check.get("tool_output_excerpt") or "No output recorded."),
        ]
    )
    ipv6 = entry.get("local_ipv6_check") or {}
    if ipv6:
        lines.extend(
            [
                "",
                f"Separate genuine IPv6 loopback check (UTC): {ipv6.get('at_utc', 'unknown')}",
                f"Target: {ipv6.get('target', 'unknown')} (temporary local listener)",
                f"Framework finding: {ipv6.get('finding_title', 'unknown')}",
                f"Open ports: {ipv6.get('open_ports', [])}",
                str(ipv6.get("tool_output_excerpt") or "No output recorded."),
            ]
        )
    lines.extend(_format_latest_loopback_runs(entry))
    return "\n".join(lines)


def _format_latest_loopback_runs(entry: dict[str, Any]) -> list[str]:
    """Show the newest genuine loopback Metasploit runs (local lab only)."""
    lines: list[str] = []
    run = entry.get("local_all_tools_run") or {}
    if run.get("status") == "captured":
        title = "Metasploit open-port finding"
        try:
            findings = json.loads(run.get("framework_output") or "[]")
            if findings:
                title = findings[0].get("title", title)
        except (TypeError, ValueError):
            pass
        lines.extend(
            [
                "",
                f"Same-run all-tools check (UTC): {run.get('at_utc', 'unknown')}",
                f"Target: {run.get('target', 'unknown')} (local loopback lab)",
                f"Framework finding: {title}",
                f"Open ports: {run.get('open_ports', [])}",
                "Cerberus connection: CAPTURED — the real daemon reported the expected port.",
            ]
        )
    re_check = entry.get("local_reverification_check") or {}
    if re_check:
        lines.extend(
            [
                "",
                f"Loopback re-verification (UTC): {re_check.get('at_utc', 'unknown')}",
                f"Version: {re_check.get('version', 'unknown')}",
                f"Scope: {re_check.get('scope', 'unknown')}",
                f"IPv4 open ports found: {re_check.get('ipv4_open_ports_found', 'unknown')}; "
                f"IPv6 open ports found: {re_check.get('ipv6_open_ports_found', 'unknown')}",
                f"Out-of-scope target: {re_check.get('out_of_scope_target', 'unknown')}",
                f"Exploit module: {re_check.get('exploit_module', 'unknown')}",
            ]
        )
    return lines


def _format_combined_local(entry: dict[str, Any]) -> str:
    """Show the saved three-real-tool local run without implying data handoff."""
    check = entry.get("local_combined_check") or {}
    if not check:
        return "No genuine three-tool local scheduler check recorded."
    versions = check.get("versions") or {}
    lines = [
        f"Completed (UTC): {check.get('at_utc', 'unknown')}",
        f"Target: {check.get('target', 'unknown')} (disposable loopback lab)",
        "Real tools: "
        f"Nmap {versions.get('nmap', 'unknown')}; "
        f"sqlmap {versions.get('sqlmap', 'unknown')}; "
        f"Metasploit {versions.get('metasploit', 'unknown')}",
        f"Sequential plan: {' -> '.join(check.get('plan') or [])}",
        f"Nmap probed ports: {check.get('nmap_probed_ports', [])}",
        f"Nmap open ports: {check.get('nmap_open_ports', [])}",
        f"sqlmap: {check.get('sqlmap_status', 'unknown')} "
        f"in {check.get('sqlmap_method', 'unknown')} parameter "
        f"{check.get('sqlmap_parameter', 'unknown')}",
        f"Metasploit scanned ports: {check.get('msf_scanned_ports', [])}",
        f"Metasploit open ports: {check.get('msf_open_ports', [])}",
        f"Out-of-scope requests refused: {', '.join(check.get('scope_refused') or [])}",
        f"Console creation in this run: {check.get('first_console_create_seconds', 'unknown')}s "
        f"with {check.get('rpc_timeout_seconds', 'unknown')}s RPC timeout",
        f"Consoles left after successful run: {check.get('consoles_left_after_successful_run', 'unknown')}",
        "Selected genuine Metasploit output:",
        str(check.get("metasploit_console_excerpt") or "No output recorded."),
    ]
    return "\n".join(lines)


def _summary_table(results: dict[str, Any]) -> str:
    lines = ["| Tool | Latest public-test status | Captured at (UTC) |", "|---|---|---|"]
    for name, entry in results.items():
        latest = entry.get("latest") or {}
        status = str(latest.get("status", "not_tested")).replace("_", " ").upper()
        at = latest.get("at_utc") or "Not tested"
        lines.append(f"| {_safe_inline(name)} | {_safe_inline(status)} | {_safe_inline(at)} |")
    return "\n".join(lines)


def render_markdown(source: str, data: dict[str, Any]) -> str:
    results = data["results"]
    replacements = {
        "updated_at": _safe_inline(data.get("updated_at", "unknown")),
        "summary_table": _summary_table(results),
        "nmap_status": _status(results["nmap"]),
        "sqlmap_status": _status(results["sqlmap"]),
        "metasploit_status": _status(results["metasploit"]),
        "metasploit_local": _code_block(_format_metasploit_local(results["metasploit"])),
        "three_real_tools_local": _code_block(_format_combined_local(results["metasploit"])),
    }
    for name in ("nmap", "sqlmap"):
        captured = _display(results[name]) or {}
        replacements[f"{name}_framework"] = _code_block(
            _format_framework_output(captured.get("framework_output"), name)
        )
        raw = captured.get("tool_output_excerpt")
        replacements[f"{name}_raw"] = _code_block(_format_nmap_xml(raw) if name == "nmap" else raw)
    for key, value in replacements.items():
        token = "{{" + key + "}}"
        if token not in source:
            raise ValueError(f"Missing expected report placeholder: {token}")
        source = source.replace(token, value)
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        import markdown  # type: ignore[import-untyped]
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        parser.exit(
            1,
            f"PDF dependencies unavailable: {exc}\n"
            "Install backend/requirements-dev.txt and WeasyPrint's native libraries.\n",
        )
    source_bytes = SOURCE.read_bytes()
    data_bytes = DATA.read_bytes()
    digest = hashlib.sha256(source_bytes + b"\0" + data_bytes).hexdigest()
    document_source = render_markdown(source_bytes.decode("utf-8"), json.loads(data_bytes))
    body = markdown.markdown(document_source, extensions=["fenced_code", "tables", "sane_lists"])
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Real result</title><meta name="author" content="Cerberus Framework">
<meta name="keywords" content="source-and-data-sha256:{html.escape(digest)}">
<style>{CSS}</style></head><body>{body}</body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=".real-result-", suffix=".pdf", dir=args.output.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        HTML(string=document, base_url=str(ROOT)).write_pdf(temporary, uncompressed_pdf=True)
        os.replace(temporary, args.output)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
    print(f"Wrote {args.output}")
    print(f"Report source/data SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
