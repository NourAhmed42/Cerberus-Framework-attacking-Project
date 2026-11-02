"""Run all three real tools at the same time, each in its own engagement.

Three engagements run concurrently in one event loop:

* Nmap     -> scanme.nmap.org only (operator permits Nmap; ~10 per 24 h limit)
* sqlmap   -> SekuMart product page, parameter id only (operator's practice site)
* Metasploit -> a temporary listener on 127.0.0.1 (local lab; no public site permits it)

No target can be supplied on the command line. The two public profiles are the
same fixed profiles used by public_tool_results.py, including its command guards
and rate limits. Metasploit needs a real msfrpcd running on loopback; if it is not
reachable the Metasploit result is reported as failed, not as passed.

Requires --confirm-public-tests because two of the three engagements use public sites.
"""

import argparse
import asyncio
import importlib.util
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "docs" / "all_tools_result"
RENDERER = ROOT / "scripts" / "render_real_results.py"


def _load_public_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "public_tool_results", HERE / "public_tool_results.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PTR = _load_public_module()


class LocalListener:
    """A TCP listener on 127.0.0.1 that accepts and closes connections (lab target)."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            try:
                conn, _ = self.sock.accept()
                conn.close()
            except OSError:
                return

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


async def _collect_metasploit(framework: Any, port: int) -> dict[str, Any]:
    started = PTR._utc_now()
    scope = framework.ScopeConfig(
        allowed_targets=["127.0.0.1"], allowed_ports=[port], max_impact="proof_of_concept"
    )
    context = framework.PentestContext(
        target=f"http://127.0.0.1:{port}/",
        scope=scope,
        config={
            "msf_module": "auxiliary/scanner/portscan/tcp",
            "msf_options": {"PORTS": str(port)},
        },
    )
    findings = await framework.ExecutionEngine().execute("metasploit_scanner", context)
    errors = [f.title for f in findings if f.severity.value == "error"]
    scan = [f for f in findings if f.metadata.get("msf_module") == "auxiliary/scanner/portscan/tcp"]
    open_ports = scan[0].metadata.get("open_ports") if scan else None
    success = bool(scan) and not errors and open_ports == [port]
    message = (
        "The real Metasploit daemon scanned the local listener and reported the open port."
        if success
        else "Metasploit did not return the expected open port. Errors: "
        + ("; ".join(errors) if errors else "none recorded")
    )
    return {
        "status": "captured" if success else "failed",
        "started_utc": PTR._timestamp(started),
        "at_utc": PTR._timestamp(PTR._utc_now()),
        "target": f"127.0.0.1:{port} (local loopback lab)",
        "message": message,
        "framework_output": PTR._finding_output(findings),
        "open_ports": open_ports,
        "expected_port": port,
    }


async def _run_all(framework: Any, data: dict[str, Any]) -> dict[str, Any]:
    listener = LocalListener()
    try:
        nmap_task = PTR._collect("nmap", framework)
        sqlmap_task = PTR._collect("sqlmap", framework)
        msf_task = _collect_metasploit(framework, listener.port)
        nmap_res, sqlmap_res, msf_res = await asyncio.gather(
            nmap_task, sqlmap_task, msf_task, return_exceptions=True
        )
    finally:
        listener.close()

    def normalize(name: str, value: Any) -> dict[str, Any]:
        if isinstance(value, BaseException):
            return {
                "status": "failed",
                "at_utc": PTR._timestamp(PTR._utc_now()),
                "message": f"{type(value).__name__}: {value}",
                "framework_output": "No completed framework output was captured.",
            }
        return value

    return {
        "nmap": normalize("nmap", nmap_res),
        "sqlmap": normalize("sqlmap", sqlmap_res),
        "metasploit": normalize("metasploit", msf_res),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-public-tests",
        action="store_true",
        help="confirm you reviewed the current operators' scope and rate limits",
    )
    args = parser.parse_args()
    if not args.confirm_public_tests:
        parser.error("this run uses public sites; add --confirm-public-tests after reviewing their policies")

    try:
        PTR._pdf_ready()
        data = PTR._load_data()
        framework = PTR._prepare_framework()
        framework.settings.MSF_ENABLED = True
        framework.settings.MSF_RPC_HOST = "127.0.0.1"
        framework.settings.MSF_RPC_SSL = False
        framework.settings.MSF_RPC_TIMEOUT = 60

        for name in ("nmap", "sqlmap"):
            configured = framework.settings.NMAP_PATH if name == "nmap" else framework.settings.SQLMAP_PATH
            fallback = "nmap" if name == "nmap" else "sqlmap"
            if not PTR._available(configured or fallback, python_script_ok=name == "sqlmap"):
                raise PTR.RefreshError(f"{name} executable is missing; nothing was started.")
            PTR._reserve_attempt(data, name, PTR._utc_now())
        PTR._save_data(data)

        print("Starting three engagements at the same time: Nmap, sqlmap, Metasploit...", flush=True)
        results = asyncio.run(_run_all(framework, data))

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        started = PTR._timestamp(PTR._utc_now())
        summary = {"run_at_utc": started, "engagements_concurrent": True, "results": results}
        (OUTPUT_DIR / "run-all-tools.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        for name in ("nmap", "sqlmap"):
            PTR._set_latest(data, name, results[name])
        meta = data["results"].setdefault("metasploit", {})
        meta["local_all_tools_run"] = results["metasploit"] | {"tool": "metasploit"}
        data["updated_at"] = started
        PTR._save_data(data)

        for name, res in results.items():
            print(f"{name}: {res['status'].upper()} — {res['message']}")

        rendered = subprocess.run([sys.executable, str(RENDERER)], check=False)
        if rendered.returncode:
            print("FAILED: results were saved, but the real-results PDF could not be rebuilt.", file=sys.stderr)
            return 1
        return 0 if all(r["status"] == "captured" for r in results.values()) else 1
    except (PTR.RefreshError, OSError, json.JSONDecodeError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Reserved public attempts remain counted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
