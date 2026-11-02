"""Run the external-tool integrations in a disposable loopback-only lab.

Nmap and sqlmap are real local programs. Metasploit is ALWAYS an explicitly
labelled MessagePack RPC test double, not a real msfrpcd. No target, module or RPC
address can be supplied by the caller. The runner does not modify .env or
persist findings. It is a learning and verification aid, not a production
scanning command.
"""

import argparse
import asyncio
import importlib
import os
import secrets
import shutil
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
SCRIPT_DIR = Path(__file__).resolve().parent

MODULES = {
    "nmap": "nmap_scanner",
    "sqlmap": "sqlmap_scanner",
    "metasploit": "metasploit_scanner",
}
ALL_MODULES = tuple(MODULES.values())
MODES = (*MODULES, "all", "parallel")


class LabFailure(Exception):
    """A setup issue or an inconclusive/failed lab result."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify integrated tools against a temporary 127.0.0.1 lab. "
            "Metasploit is simulated; all runs are local-only."
        )
    )
    parser.add_argument(
        "mode",
        choices=MODES,
        help=(
            "nmap, sqlmap, metasploit (simulated), all (one sequential plan), "
            "or parallel (separate concurrent engagements)"
        ),
    )
    return parser


def _prepare_secret() -> bool:
    """Allow the standalone lab to start without altering the backend's secret."""
    from dotenv import dotenv_values

    secret: str | None
    if "SECRET_KEY" in os.environ:
        secret = os.environ["SECRET_KEY"]
    else:
        secret = dotenv_values(BACKEND_DIR / ".env").get("SECRET_KEY")
    if secret:
        return False
    # The lab never issues tokens. A fresh, process-only random value satisfies
    # application settings when the real backend has not been configured yet.
    os.environ["SECRET_KEY"] = secrets.token_hex(32)
    return True


def _load_lab() -> Any:
    """Load the existing tested lab after parsing --help and setting the secret."""
    try:
        ephemeral_secret = _prepare_secret()
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))
        lab = importlib.import_module("sqlmap_framework_smoke")
    except ModuleNotFoundError as exc:
        raise LabFailure(
            f"Missing Python package {exc.name!r}. Install backend/requirements.txt "
            "into backend/.venv and use that environment's Python."
        ) from exc
    except Exception as exc:
        raise LabFailure(
            f"Could not load backend settings ({type(exc).__name__}). "
            "Check backend/.env and any exported environment variables. "
            "If SECRET_KEY is set, it must be at least 32 random characters."
        ) from exc
    if ephemeral_secret:
        print("LAB ONLY: using a temporary process secret; backend/.env was not changed.")
    return lab


def _available(path: str, *, python_script_ok: bool = False) -> bool:
    path = (path or "").strip()
    if not path:
        return False
    if shutil.which(path):
        return True
    return python_script_ok and path.lower().endswith(".py") and Path(path).is_file()


def _check_requirements(names: tuple[str, ...], settings: Any) -> None:
    missing = []
    if "nmap_scanner" in names and not _available(settings.NMAP_PATH or "nmap"):
        missing.append("Nmap (install nmap or set NMAP_PATH to its full path)")
    if "sqlmap_scanner" in names and not _available(
        settings.SQLMAP_PATH or "sqlmap", python_script_ok=True
    ):
        missing.append("sqlmap (install sqlmap or set SQLMAP_PATH to sqlmap.py)")
    if missing:
        raise LabFailure("Missing required tool(s): " + "; ".join(missing))


def _validate_findings(names: tuple[str, ...], findings: list[Any], port: int) -> list[str]:
    """A skipped INFO result or an empty list is not proof of success."""
    failures = [
        f"{item.module_name}: {item.title}" for item in findings if item.severity.value == "error"
    ]
    if failures:
        raise LabFailure("The lab returned an ERROR finding: " + "; ".join(failures))
    messages = []
    for name in names:
        relevant = [item for item in findings if item.module_name == name]
        if name == "nmap_scanner":
            if not any(port in item.metadata.get("open_ports", []) for item in relevant):
                raise LabFailure("Nmap did not confirm the lab's open port; see any output above.")
            messages.append(f"PASS: real Nmap found the local lab's open port {port}.")
        elif name == "sqlmap_scanner":
            if not any(
                item.severity.value == "high" and item.metadata.get("parameter") == "id"
                for item in relevant
            ):
                raise LabFailure("sqlmap did not confirm SQL injection in the lab's id parameter.")
            messages.append("PASS: real sqlmap detected the lab's intentional SQL injection in id.")
        elif name == "metasploit_scanner":
            if not any(port in item.metadata.get("open_ports", []) for item in relevant):
                raise LabFailure("The simulated Metasploit response was not parsed as expected.")
            messages.append(
                "PASS: the Metasploit adapter parsed a SIMULATED response (not msfrpcd)."
            )
        else:
            raise LabFailure(f"Unknown lab module: {name}")
    return messages


async def _exercise(mode: str, lab: Any) -> None:
    names = ALL_MODULES if mode in {"all", "parallel"} else (MODULES[mode],)
    _check_requirements(names, lab.settings)

    # These changes exist only inside this process. The fake RPC settings below
    # override any real RPC configuration before the module can connect.
    lab.settings.NMAP_ENABLED = "nmap_scanner" in names
    lab.settings.SQLMAP_ENABLED = "sqlmap_scanner" in names
    lab.settings.MSF_ENABLED = "metasploit_scanner" in names
    lab.settings.PENTEST_REQUEST_DELAY = 0.0
    lab.settings.PENTEST_MODULE_TIMEOUT = 90

    server = ThreadingHTTPServer(("127.0.0.1", 0), lab.LabHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_address[1]
    fake_rpc = None
    try:
        if lab.settings.MSF_ENABLED:
            fake_rpc = lab.FakeMetasploitRpc(port)
            fake_rpc.start()
            lab.settings.MSF_RPC_HOST = "127.0.0.1"
            lab.settings.MSF_RPC_PORT = fake_rpc.port
            lab.settings.MSF_RPC_PASSWORD = "test-only-password"
            lab.settings.MSF_RPC_SSL = False

        print(f"LOCAL LAB: 127.0.0.1:{port} (temporary, intentionally vulnerable)")
        print("Metasploit, when selected, is SIMULATED; no real msfrpcd is tested.")
        engine = lab.ExecutionEngine()
        if mode == "all":
            print(
                "MODE: one engagement, modules run sequentially: Nmap -> sqlmap -> simulated Metasploit."
            )
            context = lab._context(port, "vulnerable?id=1")
            plan = [lab.ScheduledModule(module_name=name) for name in names]
            report = await lab.ExecutionScheduler(engine).run(plan, context)
            if report.cancelled or report.errors or report.modules_run != len(names):
                raise LabFailure("The sequential plan did not complete all requested modules.")
            findings = report.findings
        elif mode == "parallel":
            print(
                "MODE: three independent engagements run concurrently against the same local lab."
            )
            contexts = [lab._context(port, "vulnerable?id=1") for _ in names]
            if len({id(ctx.shared_state) for ctx in contexts}) != len(contexts):
                raise LabFailure("The concurrent engagements unexpectedly share state.")
            results = await asyncio.gather(
                *(engine.execute(name, ctx) for name, ctx in zip(names, contexts, strict=True))
            )
            findings = [item for group in results for item in group]
        else:
            print(f"MODE: individual {mode} integration.")
            findings = await engine.execute(names[0], lab._context(port, "vulnerable?id=1"))
        for message in _validate_findings(names, findings, port):
            print(message)
    finally:
        if fake_rpc is not None:
            fake_rpc.stop()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
    print("DONE: temporary local servers stopped; results were not saved to the app database.")


def main() -> int:
    args = _parser().parse_args()
    try:
        lab = _load_lab()
        # Keep the beginner output readable; warnings and errors remain visible.
        import logging

        import structlog

        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
        asyncio.run(_exercise(args.mode, lab))
    except LabFailure as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Local lab cleanup was requested.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
