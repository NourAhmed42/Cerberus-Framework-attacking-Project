"""Capture real results from two fixed, publicly authorized practice sites.

No target, ports, scripts, or payload options can be supplied on the CLI. The
runner requires explicit confirmation and never runs automatically on import,
from pytest, or in the background. Metasploit is intentionally not included:
these fixed public profiles do not authorize a Metasploit TCP scan.
"""

import argparse
import asyncio
import contextlib
import importlib.util
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATA = ROOT / "docs" / "real_results.json"
RENDERER = ROOT / "scripts" / "render_real_results.py"
NMAP_TARGET = "scanme.nmap.org"
SQLMAP_TARGET = "https://sekumart.sekuripy.hr/product.php?id=1"
USER_AGENT = "Cerberus-Public-Practice-Example/1.0"
SUPPORTED_PROFILES = ("nmap", "sqlmap")
UNAVAILABLE_PROFILES = ("metasploit",)  # no public target here authorizes this profile
LIMITS = {"nmap": 10, "sqlmap": 6}  # per saved state file, rolling 24 hours

NMAP_ARGS = [
    "-sT",
    "-Pn",
    "-T2",
    "-p",
    "22,80,443",
    "-sV",
    "--version-light",
    "-oX",
    "-",
    NMAP_TARGET,
]
SQL_ANSWERS = (
    "--answers=extending provided=N,refresh=N,follow=N,"
    "keep testing the others=Y,custom injection marker=N,automatically bypass=N"
)


class RefreshError(Exception):
    """A safe refusal, setup problem, or failed public check."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat(timespec="seconds")  # noqa: UP017


def _available(path: str, *, python_script_ok: bool = False) -> bool:
    configured = (path or "").strip()
    if not configured:
        return False
    if shutil.which(configured):
        return True
    return python_script_ok and configured.lower().endswith(".py") and Path(configured).is_file()


def _load_data() -> dict[str, Any]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if (
        data.get("schema_version") != 1
        or not isinstance(data.get("results"), dict)
        or not isinstance(data.get("attempts"), dict)
        or not set(SUPPORTED_PROFILES + UNAVAILABLE_PROFILES).issubset(data["results"])
    ):
        raise RefreshError("The results file has an unsupported or incomplete format.")
    return data


def _save_data(data: dict[str, Any]) -> None:
    """Replace the snapshot atomically; never edit backend/.env or app data."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=DATA.parent, prefix=".real-results-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, DATA)
    finally:
        if temporary is not None:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()


def _reserve_attempt(data: dict[str, Any], name: str, now: datetime) -> None:
    """A per-file cap; it cannot count scans performed elsewhere."""
    recorded = data["attempts"].get(name, [])
    if not isinstance(recorded, list):
        raise RefreshError(f"Invalid saved {name} rate-limit history.")
    recent: list[str] = []
    for value in recorded:
        try:
            instant = datetime.fromisoformat(value)
            if instant.tzinfo is None or instant > now + timedelta(minutes=1):
                raise ValueError
        except (ValueError, TypeError):
            raise RefreshError(
                f"Invalid saved {name} attempt timestamp; no scan started."
            ) from None
        if now - timedelta(hours=24) < instant:
            recent.append(value)
    if len(recent) >= LIMITS[name]:
        raise RefreshError(
            f"The local 24-hour {name} limit has been reached; no additional scan was started."
        )
    recent.append(_timestamp(now))
    data["attempts"][name] = recent
    _save_data(data)  # Reserve before starting, even if a run is interrupted.


def _prepare_framework() -> Any:
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND / ".env", override=False)
        if not os.environ.get("SECRET_KEY"):
            os.environ["SECRET_KEY"] = secrets.token_hex(32)
            print("Using a temporary process-only settings secret; backend/.env is unchanged.")
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        from app.ai_engine.pentest import ExecutionEngine, PentestContext, ScopeConfig
        from app.ai_engine.pentest.tools.nmap_adapter import (
            _default_subprocess_runner as nmap_runner,
        )
        from app.ai_engine.pentest.tools.sqlmap_adapter import (
            _default_subprocess_runner as sqlmap_runner,
        )
        from app.core.config import settings

        import structlog

        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    except Exception as exc:
        raise RefreshError(
            f"Cannot load the backend ({type(exc).__name__}). Install the project's backend "
            "requirements and check that any configured SECRET_KEY has at least 32 characters."
        ) from exc
    settings.NMAP_ENABLED = True
    settings.SQLMAP_ENABLED = True
    settings.MSF_ENABLED = False
    settings.PENTEST_MODULE_TIMEOUT = 160
    settings.PENTEST_HTTP_TIMEOUT = 10
    settings.PENTEST_REQUEST_DELAY = 0.3
    settings.PENTEST_USER_AGENT = USER_AGENT
    settings.NMAP_TIMEOUT = 110
    settings.SQLMAP_TIMEOUT = 125
    return SimpleNamespace(
        ExecutionEngine=ExecutionEngine,
        PentestContext=PentestContext,
        ScopeConfig=ScopeConfig,
        nmap_runner=nmap_runner,
        sqlmap_runner=sqlmap_runner,
        settings=settings,
    )


def _guard_sqlmap(cmd: list[str]) -> None:
    """Fail before spawning if a future adapter changes the fixed safe profile."""
    try:
        index = cmd.index("-r")
        if index not in (1, 2):
            raise ValueError
        request = Path(cmd[index + 1])
        expected_request = (
            "GET /product.php?id=1 HTTP/1.1\r\n"
            "Host: sekumart.sekuripy.hr\r\n"
            f"User-Agent: {USER_AGENT}\r\n\r\n"
        ).encode("ascii")
        if request.name != "request.txt" or request.read_bytes() != expected_request:
            raise ValueError
        expected = [
            "-r",
            str(request),
            "--batch",
            "--ignore-stdin",
            "--disable-coloring",
            "--ignore-proxy",
            "--ignore-redirects",
            "--drop-set-cookie",
            "--skip-waf",
            "--abort-code=401,403",
            SQL_ANSWERS,
            f"--output-dir={request.parent / 'output'}",
            "--param-filter=GET",
            "--level=1",
            "--risk=1",
            "--technique=E",
            "--threads=1",
            "--delay=0.3",
            "--timeout=10.0",
            "--retries=0",
            "-p",
            "id",
            "--force-ssl",
        ]
        if cmd[index:] != expected:
            raise ValueError
    except (ValueError, IndexError, OSError):
        raise RefreshError(
            "Unexpected sqlmap target or arguments; scan refused before launch."
        ) from None


class CaptureRunner:
    """Delegate to the actual adapter subprocess while capturing its output."""

    def __init__(self, name: str, delegate: Any):
        self.name = name
        self.delegate = delegate
        self.version = "unknown"
        self.stdout = ""
        self.stderr = ""
        self.returncode: int | None = None
        self.scan_started = False

    async def __call__(self, cmd: list[str], timeout: float) -> tuple[int, str, str]:
        is_version = len(cmd) in (2, 3) and cmd[-1] == "--version"
        if not is_version:
            if self.name == "nmap" and cmd[1:] != NMAP_ARGS:
                raise RefreshError(
                    "Unexpected Nmap target or arguments; scan refused before launch."
                )
            if self.name == "sqlmap":
                _guard_sqlmap(cmd)
            self.scan_started = True
        rc, stdout, stderr = await self.delegate(cmd, timeout)
        if is_version:
            self.version = (
                (stdout or stderr).splitlines()[0].strip() if (stdout or stderr) else "unknown"
            )
        else:
            self.returncode = rc
            self.stdout = stdout
            self.stderr = stderr
        return rc, stdout, stderr


def _nmap_excerpt(output: str) -> tuple[str, bool]:
    try:
        root = ET.fromstring(output)  # noqa: S314 — local Nmap XML, fixed public target
        hosts = root.find("./runstats/hosts")
        finished = root.find("./runstats/finished")
        up = hosts is not None and int(hosts.attrib.get("up", "0")) > 0
        completed = finished is not None and finished.attrib.get("exit") == "success"
        selected = root.findall("./host/status") + root.findall("./host/address")
        selected += root.findall("./host/ports")
        if finished is not None:
            selected.append(finished)
        for element in selected:
            ET.indent(element, space="  ")
        excerpt = "\n".join(ET.tostring(element, encoding="unicode") for element in selected)
        return excerpt[:12000] or "No host/port elements were returned.", bool(up and completed)
    except (ET.ParseError, ValueError):
        return "The Nmap XML output could not be parsed.", False


def _sqlmap_excerpt(output: str) -> str:
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if "sqlmap identified the following injection point" in line.lower() or (
            "sqlmap resumed the following injection point" in line.lower()
        ):
            end = min(i + 35, len(lines))
            for j in range(i, end):
                if "back-end DBMS:" in lines[j]:
                    end = j + 1
                    break
            return "\n".join(lines[i:end])[:12000]
    return "\n".join(lines[-18:])[:12000] or "No console output was captured."


def _finding_output(findings: list[Any]) -> str:
    selected = []
    for item in findings:
        data = item.to_dict()
        selected.append(
            {
                key: data[key]
                for key in (
                    "module_name",
                    "severity",
                    "title",
                    "target",
                    "confidence",
                    "verified",
                    "cwe_id",
                    "metadata",
                )
            }
        )
    return json.dumps(selected, indent=2, ensure_ascii=False)[:12000]


async def _collect(name: str, framework: Any) -> dict[str, Any]:
    started = _utc_now()
    if name == "nmap":
        capture = CaptureRunner(name, framework.nmap_runner)
        target = f"http://{NMAP_TARGET}/"
        context = framework.PentestContext(
            target=target,
            scope=framework.ScopeConfig(
                allowed_targets=[NMAP_TARGET], allowed_ports=[22, 80, 443], request_delay=0.3
            ),
            config={
                "nmap_ports": [22, 80, 443],
                "nmap_service_version": True,
                "nmap_timing": 2,
                "nmap_scripts": [],
                "nmap_timeout": 110,
                "nmap_runner": capture,
            },
        )
    elif name == "sqlmap":
        capture = CaptureRunner(name, framework.sqlmap_runner)
        target = SQLMAP_TARGET
        context = framework.PentestContext(
            target=target,
            scope=framework.ScopeConfig(
                allowed_targets=["sekumart.sekuripy.hr"], allowed_ports=[443], request_delay=0.3
            ),
            config={
                "sqlmap_parameters": ["id"],
                "sqlmap_level": 1,
                "sqlmap_techniques": "E",
                "sqlmap_delay": 0.3,
                "sqlmap_timeout": 125,
                "sqlmap_runner": capture,
            },
        )
    else:
        raise RefreshError(f"No approved public collector exists for {name}.")
    findings = await framework.ExecutionEngine().execute(f"{name}_scanner", context)
    errors = [item.title for item in findings if item.severity.value == "error"]
    genuine = any(item.metadata.get("tool") == name for item in findings)
    if name == "nmap":
        excerpt, completed = _nmap_excerpt(capture.stdout)
    else:
        excerpt = _sqlmap_excerpt(capture.stdout)
        records = context.shared_state.get("sqlmap_results", [])
        completed = bool(records and records[-1].get("status") in {"detected", "not_detected"})
        # A completed negative has no 'tool' metadata but is still a real result.
        genuine = genuine or bool(records)
    success = (
        capture.scan_started and capture.returncode == 0 and completed and genuine and not errors
    )
    if success:
        message = "The real tool completed and the framework returned a recognizable result."
    else:
        message = "The real check was skipped, incomplete, or failed; it is not a clean result."
        if errors:
            message += " Framework errors: " + "; ".join(errors)
    return {
        "status": "captured" if success else "failed",
        "at_utc": _timestamp(_utc_now()),
        "started_utc": _timestamp(started),
        "target": target,
        "version": capture.version,
        "message": message,
        "framework_output": _finding_output(findings),
        "tool_output_excerpt": excerpt,
    }


def _pdf_ready() -> None:
    try:
        if importlib.util.find_spec("markdown") is None:
            raise ImportError("Markdown is missing")
        __import__("markdown")
        __import__("weasyprint")
    except (ImportError, OSError) as exc:
        raise RefreshError(
            "PDF dependencies are unavailable. Install backend/requirements-dev.txt "
            "and WeasyPrint's native libraries before starting public tests."
        ) from exc


def _set_latest(data: dict[str, Any], name: str, result: dict[str, Any]) -> None:
    entry = data["results"][name]
    entry["latest"] = result
    if result["status"] == "captured":
        entry["last_success"] = result
    data["updated_at"] = result.get("at_utc", _timestamp(_utc_now()))
    _save_data(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=(*SUPPORTED_PROFILES, "all"))
    parser.add_argument(
        "--confirm-public-tests",
        action="store_true",
        help="confirm you reviewed the current operators' scope and rate limits",
    )
    args = parser.parse_args()
    if not args.confirm_public_tests:
        parser.error(
            "public tests require --confirm-public-tests after reviewing the site policies"
        )
    try:
        _pdf_ready()  # Do not scan if the report cannot be built.
        data = _load_data()
        framework = _prepare_framework()
        profiles = SUPPORTED_PROFILES if args.mode == "all" else (args.mode,)
        all_ok = True
        for name in profiles:
            configured = (
                framework.settings.NMAP_PATH if name == "nmap" else framework.settings.SQLMAP_PATH
            )
            fallback = "nmap" if name == "nmap" else "sqlmap"
            try:
                if not _available(configured or fallback, python_script_ok=name == "sqlmap"):
                    raise RefreshError(f"{name} executable is missing; no scan was started.")
                _reserve_attempt(data, name, _utc_now())
                print(
                    f"Running the fixed {name} public-practice profile; please wait...", flush=True
                )
                result = asyncio.run(_collect(name, framework))
            except Exception as exc:
                result = {
                    "status": "failed",
                    "at_utc": _timestamp(_utc_now()),
                    "target": NMAP_TARGET if name == "nmap" else SQLMAP_TARGET,
                    "version": "unknown",
                    "message": f"{type(exc).__name__}: {exc}",
                    "framework_output": "No completed framework output was captured.",
                    "tool_output_excerpt": "No completed real tool output was captured.",
                }
            _set_latest(data, name, result)
            print(f"{name}: {result['status'].upper()} — {result['message']}")
            all_ok = all_ok and result["status"] == "captured"
        rendered = subprocess.run([sys.executable, str(RENDERER)], check=False)
        if rendered.returncode:
            print("FAILED: captures were saved, but the PDF could not be rebuilt.", file=sys.stderr)
            print(
                "Run scripts/render_real_results.py after fixing PDF dependencies; do not rescan."
            )
            return 1
        print("Updated docs/real result.pdf. Metasploit remains NOT TESTED on public sites.")
        return 0 if all_ok else 1
    except (RefreshError, OSError, json.JSONDecodeError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. A reserved public attempt remains counted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
