#!/usr/bin/env python3
"""Run every Cerberus tool integration once and print a summary.

Works the same on Windows PowerShell and Mac zsh. Output goes to the terminal
(VS Code is fine), and every step is labelled:

  LOCAL LAB      temporary 127.0.0.1 target started by the script itself
  SIMULATED      the lab's Metasploit step (a fake RPC server, not real Metasploit)
  TESTS          automated unit tests, no database needed
  PUBLIC         real public site. Only with --include-public.
  LOCAL REAL     real Metasploit daemon on 127.0.0.1 (needs MSF_RPC_PASSWORD)

Public sites are contacted only with --include-public, and only the two
approved targets are used: scanme.nmap.org (Nmap) and the SekuMart product
id parameter (sqlmap). Rate limits are enforced by the runner itself.

Inputs (optional, environment variables):
  SQLMAP_PATH        full path to sqlmap.py, if sqlmap is not on PATH
  MSF_RPC_PASSWORD   password of the msfrpcd daemon (only for the real Metasploit step)
  MSF_RPC_PORT       msfrpcd port (default 55553)

Usage (run from the project root):
  Mac zsh:          ./backend/.venv/bin/python scripts/demo/run_everything.py
  Windows PowerShell: .\\backend\\.venv\\Scripts\\python.exe scripts\\demo\\run_everything.py
  Add --include-public to also run the public-site step.
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
LAB = ROOT / "scripts" / "live_tests" / "beginner_tools_lab.py"
RUNNER = ROOT / "scripts" / "live_tests" / "run_all_tools.py"
UNIT_TESTS = [
    "tests/unit/test_pentest_tools.py",
    "tests/unit/test_pentest_framework.py",
    "tests/unit/test_pentest_safety_regressions.py",
    "tests/unit/test_sqlmap_integration.py",
    "tests/unit/test_public_tool_results.py",
]


@dataclass
class Result:
    name: str
    label: str
    status: str  # PASS, FAIL, SKIP
    seconds: float
    note: str = ""


def banner(title: str) -> None:
    print("\n" + "=" * 72, flush=True)
    print(title, flush=True)
    print("=" * 72, flush=True)


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if not env.get("SECRET_KEY"):
        env["SECRET_KEY"] = secrets.token_hex(32)
    return env


def find_sqlmap() -> str | None:
    configured = os.environ.get("SQLMAP_PATH")
    if configured and Path(configured).exists():
        return configured
    return shutil.which("sqlmap")


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def preflight() -> dict[str, bool]:
    banner("STEP 0 - Checking what is installed")
    venv_ok = ".venv" in sys.executable
    nmap_ok = shutil.which("nmap") is not None
    sqlmap_path = find_sqlmap()
    msf_port = int(os.environ.get("MSF_RPC_PORT", "55553"))
    msf_password = bool(os.environ.get("MSF_RPC_PASSWORD"))
    msf_daemon = port_open("127.0.0.1", msf_port)
    db_up = port_open("127.0.0.1", 5432)

    def show(name: str, ok: bool, detail: str) -> None:
        print(f"  [{'OK' if ok else 'MISSING'}] {name}: {detail}", flush=True)

    show("Project Python (.venv)", venv_ok,
         sys.executable if venv_ok else "not the project .venv - use backend/.venv")
    show("Nmap", nmap_ok, shutil.which("nmap") or "install Nmap (nmap.org/download)")
    show("sqlmap", sqlmap_path is not None,
         sqlmap_path or "not found - set SQLMAP_PATH to the full path of sqlmap.py")
    show("Metasploit daemon", msf_daemon and msf_password,
         f"127.0.0.1:{msf_port} "
         + ("listening" if msf_daemon else "not listening")
         + ("; password set" if msf_password else "; MSF_RPC_PASSWORD not set"))
    show("PostgreSQL on 127.0.0.1:5432", db_up,
         "reachable (the demo does not write to it)" if db_up else "not running (not needed for this demo)")
    return {"nmap": nmap_ok, "sqlmap": sqlmap_path is not None, "msf": msf_daemon and msf_password}


def run_step(name: str, label: str, cmd: list[str], cwd: Path, timeout: int) -> Result:
    banner(f"{name} [{label}]")
    print("  Command: " + " ".join(cmd), flush=True)
    started = time.monotonic()
    try:
        completed = subprocess.run(cmd, cwd=cwd, env=child_env(), timeout=timeout)
        code = completed.returncode
    except subprocess.TimeoutExpired:
        return Result(name, label, "FAIL", time.monotonic() - started, f"timed out after {timeout}s")
    seconds = time.monotonic() - started
    if code == 0:
        return Result(name, label, "PASS", seconds, "exit 0")
    return Result(name, label, "FAIL", seconds, f"exit {code} - read the lines above")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--include-public", action="store_true",
                        help="also contact the two approved public sites (uses daily limits)")
    args = parser.parse_args()

    if not LAB.exists() or not RUNNER.exists():
        print("Run this from the project root (the folder that contains scripts/ and backend/).")
        return 2

    available = preflight()
    results: list[Result] = []

    # Step 1: local lab (temporary target on 127.0.0.1, started by the script)
    if available["nmap"] and available["sqlmap"]:
        results.append(run_step("Step 1 - Nmap, sqlmap, Metasploit (lab)",
                                "LOCAL LAB; Metasploit SIMULATED",
                                [sys.executable, str(LAB), "parallel"], ROOT, 900))
    else:
        results.append(Result("Step 1 - Nmap, sqlmap, Metasploit (lab)", "LOCAL LAB", "SKIP", 0.0,
                              "needs Nmap and sqlmap (see STEP 0)"))

    # Step 2: automated tests (no database)
    results.append(run_step("Step 2 - Automated tests", "TESTS",
                            [sys.executable, "-m", "pytest", "--noconftest", "-q", "-p", "no:warnings",
                             "-k", "not persist", *UNIT_TESTS], BACKEND, 900))

    # Step 3: public sites + real Metasploit (opt-in)
    if args.include_public:
        if available["msf"]:
            results.append(run_step("Step 3 - Public sites + real Metasploit",
                                    "PUBLIC + LOCAL REAL",
                                    [sys.executable, str(RUNNER), "--confirm-public-tests"], ROOT, 1200))
        else:
            results.append(Result("Step 3 - Public sites + real Metasploit", "PUBLIC", "SKIP", 0.0,
                                  "needs the msfrpcd daemon and MSF_RPC_PASSWORD (see STEP 0)"))
    else:
        results.append(Result("Step 3 - Public sites + real Metasploit", "PUBLIC + LOCAL REAL", "SKIP", 0.0,
                              "not run; add --include-public to contact scanme.nmap.org and SekuMart"))

    banner("SUMMARY")
    print(f"  {'Step':<40}{'Label':<36}{'Status':<8}{'Time':>7}  Note", flush=True)
    for r in results:
        print(f"  {r.name:<40}{r.label:<36}{r.status:<8}{r.seconds:6.1f}s  {r.note}", flush=True)
    failed = [r for r in results if r.status == "FAIL"]
    print("", flush=True)
    if failed:
        print(f"{len(failed)} step(s) failed. Fix the item marked MISSING above, then run again.", flush=True)
        return 1
    skipped = [r for r in results if r.status == "SKIP"]
    if skipped:
        print(f"Passed: every step that ran. {len(skipped)} step(s) were SKIPPED (reasons above).", flush=True)
    else:
        print("All steps passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
