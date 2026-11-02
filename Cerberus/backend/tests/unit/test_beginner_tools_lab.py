"""Tests for the beginner runner's local-only and fail-closed behavior."""

import asyncio
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPO_ROOT / "scripts" / "live_tests" / "beginner_tools_lab.py"
spec = importlib.util.spec_from_file_location("beginner_tools_lab", RUNNER_PATH)
assert spec and spec.loader
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def finding(module, severity="info", *, title="result", **metadata):
    return SimpleNamespace(
        module_name=module,
        severity=SimpleNamespace(value=severity),
        title=title,
        metadata=metadata,
    )


def valid_findings(port=12345):
    return [
        finding("nmap_scanner", open_ports=[port]),
        finding("sqlmap_scanner", "high", parameter="id"),
        finding("metasploit_scanner", open_ports=[port]),
    ]


def test_cli_help_works_without_site_packages():
    result = subprocess.run(
        [sys.executable, "-S", str(RUNNER_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "simulated" in result.stdout.lower()
    assert "parallel" in result.stdout and "all" in result.stdout


def test_cli_rejects_target_override():
    result = subprocess.run(
        [sys.executable, "-S", str(RUNNER_PATH), "nmap", "--target", "example.com"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr


def test_modes_identify_exact_integrations():
    assert lab.ALL_MODULES == ("nmap_scanner", "sqlmap_scanner", "metasploit_scanner")
    assert set(lab.MODES) == {"nmap", "sqlmap", "metasploit", "all", "parallel"}


def test_registered_tools_are_listed_and_pdf_matches_guide_source():
    from app.ai_engine.pentest import default_tool_registry

    registered = {item["name"] for item in default_tool_registry().list_metadata()}
    source = (REPO_ROOT / "docs" / "HOW_TO_RUN_THE_TOOLS_AS_BEGINNER.md").read_bytes()
    documented = set(re.findall(r"<!-- tool:([a-z0-9_-]+) -->", source.decode("utf-8")))
    assert registered == documented, "Update the beginner guide when registered tools change."
    pdf = (REPO_ROOT / "docs" / "how to run the tools as beginner.pdf").read_bytes()
    marker = b"source-sha256:" + hashlib.sha256(source).hexdigest().encode("ascii")
    assert marker in pdf, "Regenerate the beginner PDF after changing its Markdown source."


def test_availability_accepts_python_script_without_execute_permission(monkeypatch, tmp_path):
    script = tmp_path / "sqlmap.py"
    script.write_text("# harmless stub\n", encoding="utf-8")
    assert lab._available(sys.executable)
    # Windows may consider any existing file executable; force the fallback.
    monkeypatch.setattr(lab.shutil, "which", lambda path: None)
    assert not lab._available(str(script))
    assert lab._available(str(script), python_script_ok=True)
    assert not lab._available(str(tmp_path / "absent.py"), python_script_ok=True)


def test_missing_binaries_are_reported_but_simulation_needs_neither():
    settings = SimpleNamespace(NMAP_PATH="missing-cerberus-nmap", SQLMAP_PATH="missing-sqlmap")
    lab._check_requirements(("metasploit_scanner",), settings)
    with pytest.raises(lab.LabFailure, match=r"Nmap.*sqlmap"):
        lab._check_requirements(lab.ALL_MODULES, settings)


def test_process_secret_generated_without_modifying_env_file(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "BACKEND_DIR", tmp_path)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert lab._prepare_secret()
    assert len(os.environ["SECRET_KEY"]) == 64
    assert not (tmp_path / ".env").exists()


def test_existing_backend_or_exported_secret_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "BACKEND_DIR", tmp_path)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text("SECRET_KEY=" + "b" * 64 + "\n", encoding="utf-8")
    original = dotenv.read_bytes()
    assert not lab._prepare_secret()
    assert "SECRET_KEY" not in os.environ
    assert dotenv.read_bytes() == original
    monkeypatch.setenv("SECRET_KEY", "e" * 64)
    assert not lab._prepare_secret()
    assert os.environ["SECRET_KEY"] == "e" * 64
    assert dotenv.read_bytes() == original


def test_success_requires_expected_result_for_each_tool():
    results = lab._validate_findings(lab.ALL_MODULES, valid_findings(), 12345)
    assert len(results) == 3
    assert "real Nmap" in results[0]
    assert "real sqlmap" in results[1]
    assert "SIMULATED" in results[2]
    with pytest.raises(lab.LabFailure, match="Nmap did not confirm"):
        lab._validate_findings(("nmap_scanner",), [finding("nmap_scanner")], 12345)
    with pytest.raises(lab.LabFailure, match="sqlmap did not confirm"):
        lab._validate_findings(("sqlmap_scanner",), [finding("sqlmap_scanner")], 12345)
    with pytest.raises(lab.LabFailure, match="simulated Metasploit"):
        lab._validate_findings(("metasploit_scanner",), [finding("metasploit_scanner")], 12345)


def test_positive_plus_error_is_not_reported_as_success():
    findings = valid_findings() + [finding("sqlmap_scanner", "error", title="incomplete")]
    with pytest.raises(lab.LabFailure, match="ERROR finding.*incomplete"):
        lab._validate_findings(lab.ALL_MODULES, findings, 12345)


@pytest.mark.parametrize("mode", lab.MODES)
async def test_orchestration_is_local_and_uses_fake_rpc(monkeypatch, capsys, mode):
    """Stub tool execution here; the separate live lab tests the real binaries."""
    monkeypatch.setattr(lab, "_check_requirements", lambda names, settings: None)
    settings = SimpleNamespace(
        MSF_RPC_HOST="external.example.invalid",
        MSF_RPC_PORT=65535,
        MSF_RPC_PASSWORD="original-not-used",
        MSF_RPC_SSL=True,
    )
    state = SimpleNamespace(active=0, peak=0, calls=[], scheduler=False, rpcs=[])

    class Handler(BaseHTTPRequestHandler):
        pass

    class FakeRpc:
        def __init__(self, port):
            self.scanned_port = port
            self.port = 43210
            self.started = False
            self.stopped = False
            state.rpcs.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    class Engine:
        async def execute(self, name, context):
            state.calls.append((name, context))
            state.active += 1
            state.peak = max(state.peak, state.active)
            await asyncio.sleep(0.01)
            state.active -= 1
            if name == "sqlmap_scanner":
                return [finding(name, "high", parameter="id")]
            if name == "metasploit_scanner":
                assert settings.MSF_RPC_HOST == "127.0.0.1"
                assert settings.MSF_RPC_PORT == 43210
                assert settings.MSF_RPC_PASSWORD == "test-only-password"
                assert settings.MSF_RPC_SSL is False
            return [finding(name, open_ports=[context.port])]

    class Scheduler:
        def __init__(self, engine):
            self.engine = engine

        async def run(self, plan, context):
            state.scheduler = True
            findings = []
            for item in plan:
                findings.extend(await self.engine.execute(item.module_name, context))
            return SimpleNamespace(
                cancelled=False, errors=[], modules_run=len(plan), findings=findings
            )

    fake_lab = SimpleNamespace(
        settings=settings,
        LabHandler=Handler,
        FakeMetasploitRpc=FakeRpc,
        ExecutionEngine=Engine,
        ExecutionScheduler=Scheduler,
        ScheduledModule=lambda module_name: SimpleNamespace(module_name=module_name),
        _context=lambda port, path: SimpleNamespace(port=port, shared_state={}),
    )
    await lab._exercise(mode, fake_lab)
    output = capsys.readouterr().out
    assert "LOCAL LAB: 127.0.0.1:" in output
    assert "SIMULATED" in output and "DONE:" in output
    expected = lab.ALL_MODULES if mode in {"all", "parallel"} else (lab.MODULES[mode],)
    assert [name for name, _ in state.calls] == list(expected)
    assert state.scheduler is (mode == "all")
    assert settings.NMAP_ENABLED is ("nmap_scanner" in expected)
    assert settings.SQLMAP_ENABLED is ("sqlmap_scanner" in expected)
    assert settings.MSF_ENABLED is ("metasploit_scanner" in expected)
    if "metasploit_scanner" in expected:
        assert len(state.rpcs) == 1 and state.rpcs[0].started and state.rpcs[0].stopped
    else:
        assert not state.rpcs
    contexts = [ctx for _, ctx in state.calls]
    if mode == "all":
        assert state.peak == 1 and len({id(ctx.shared_state) for ctx in contexts}) == 1
    if mode == "parallel":
        assert state.peak == 3 and len({id(ctx.shared_state) for ctx in contexts}) == 3


def test_missing_package_prints_friendly_error_without_importing_framework():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-S", str(RUNNER_PATH), "metasploit"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Missing Python package" in result.stderr
    assert "requirements.txt" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_binaries_produce_nonzero_exit_without_launching_servers():
    env = os.environ.copy()
    env.update(
        SECRET_KEY="a" * 64,
        NMAP_PATH="missing-cerberus-nmap",
        SQLMAP_PATH="missing-cerberus-sqlmap",
    )
    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "all"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1
    assert "Missing required tool(s)" in result.stderr
    assert "Nmap" in result.stderr and "sqlmap" in result.stderr
    assert "LOCAL LAB:" not in result.stdout
