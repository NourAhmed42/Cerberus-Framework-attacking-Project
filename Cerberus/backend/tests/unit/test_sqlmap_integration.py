"""Hermetic tests for the sqlmap adapter, module, and tool coexistence.

These tests use sqlmap/Nmap runners and a MessagePack Metasploit test double.
They do not claim to test a real Metasploit Framework msfrpcd. The separate
loopback smoke script exercises real sqlmap and, when installed, real Nmap.
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai_engine.pentest import (
    ExecutionEngine,
    ExecutionScheduler,
    OutOfScopeError,
    PentestContext,
    ScheduledModule,
    ScopeConfig,
    SQLMapAdapter,
    default_registry,
    default_tool_registry,
    finding_to_vulnerability_dict,
    persist_findings,
)
from app.ai_engine.pentest.core import SeverityLevel
from app.ai_engine.pentest.core.exceptions import RoEViolationError, ToolUnavailableError
from app.ai_engine.pentest.tools.sqlmap_adapter import _default_subprocess_runner
from app.core.config import settings
from app.db.models.engagement import Engagement, EngagementStatus
from app.db.models.user import User
from app.db.models.vulnerability import Vulnerability, VulnerabilityEvidence
from tests.unit.test_pentest_tools import FakeMsfrpcd, FakeNmap

POSITIVE = """\
sqlmap identified the following injection point(s) with a total of 13 HTTP(s) requests:
---
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: id=1 AND 1234=1234
    Type: error-based
    Title: Example error-based detection
    Payload: id=1 AND example
---
back-end DBMS: SQLite
"""
NEGATIVE = (
    "[WARNING] GET parameter 'id' does not seem to be injectable\n"
    "[CRITICAL] all tested parameters do not appear to be injectable.\n"
)


class FakeSQLMap:
    """Captures the actual command and private request file before cleanup."""

    def __init__(self, output: str = POSITIVE, exit_code: int = 0, wait: float = 0.0):
        self.output = output
        self.exit_code = exit_code
        self.wait = wait
        self.commands: list[list[str]] = []
        self.requests: list[str] = []
        self.workdirs: list[Path] = []
        self.started = asyncio.Event()

    async def __call__(self, cmd: list[str], timeout: float) -> tuple[int, str, str]:
        self.commands.append(list(cmd))
        if "--version" in cmd:
            return 0, "1.9.6#stable\n", ""
        request_path = Path(cmd[cmd.index("-r") + 1])
        self.workdirs.append(request_path.parent)
        self.requests.append(request_path.read_text(encoding="ascii"))
        self.started.set()
        if self.wait:
            await asyncio.sleep(self.wait)
        output = self.output
        if "--param-filter=POST" in cmd:
            output = output.replace("Parameter: id (GET)", "Parameter: id (POST)")
        return self.exit_code, output, ""


@pytest.fixture
def fake_sqlmap(monkeypatch):
    monkeypatch.setattr(settings, "SQLMAP_ENABLED", True)
    monkeypatch.setattr(settings, "SQLMAP_PATH", "sqlmap")
    monkeypatch.setattr(settings, "SQLMAP_TIMEOUT", 10)
    monkeypatch.setattr(settings, "PENTEST_REQUEST_DELAY", 0.0)
    return FakeSQLMap()


def context(target: str = "http://127.0.0.1:8000/test?id=1", **config) -> PentestContext:
    return PentestContext(
        target=target,
        scope=ScopeConfig(allowed_targets=["127.0.0.1"], allowed_ports=[8000]),
        config=config,
    )


def test_registry_discovers_all_three_tools_and_modules():
    tools, modules = default_tool_registry(), default_registry()
    assert tools.get("sqlmap") is SQLMapAdapter
    assert {"sqlmap", "nmap", "metasploit"} <= {item["name"] for item in tools.list_metadata()}
    assert all(
        modules.get(name) for name in ("sqlmap_scanner", "nmap_scanner", "metasploit_scanner")
    )
    assert not SQLMapAdapter.enabled_by_default
    assert any(item.name == "sqlmap_scanner" for item in modules.by_technique("T1595.002"))


async def test_sqlmap_version_and_disconnect(fake_sqlmap):
    adapter = SQLMapAdapter(runner=fake_sqlmap)
    info = await adapter.connect()
    assert info["version"] == "1.9.6#stable"
    assert adapter.is_connected()
    await adapter.disconnect()
    assert not adapter.is_connected()


async def test_sqlmap_missing_binary_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "SQLMAP_PATH", "cerberus-sqlmap-does-not-exist")
    with pytest.raises(ToolUnavailableError):
        await SQLMapAdapter().connect()


async def test_disabled_and_missing_binary_are_fail_soft(fake_sqlmap, monkeypatch):
    engine = ExecutionEngine()
    monkeypatch.setattr(settings, "SQLMAP_ENABLED", False)
    disabled = await engine.execute("sqlmap_scanner", context(sqlmap_runner=fake_sqlmap))
    assert disabled[0].severity == SeverityLevel.INFO
    assert "disabled" in disabled[0].title
    assert not fake_sqlmap.commands
    monkeypatch.setattr(settings, "SQLMAP_ENABLED", True)
    monkeypatch.setattr(settings, "SQLMAP_PATH", "cerberus-sqlmap-does-not-exist")
    missing = await engine.execute("sqlmap_scanner", context())
    assert missing[0].severity == SeverityLevel.INFO
    assert "unavailable" in missing[0].title


async def test_get_detection_and_evidence_are_normalized(fake_sqlmap):
    ctx = context(sqlmap_runner=fake_sqlmap, sqlmap_parameters=["id"])
    events = []
    engine = ExecutionEngine(audit_sink=lambda event, payload: events.append((event, payload)))
    findings = await engine.execute("sqlmap_scanner", ctx)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == SeverityLevel.HIGH
    assert finding.cwe_id == "CWE-89"
    assert finding.technique_id == "T1595.002"
    assert finding.metadata["parameter"] == "id"
    assert finding.metadata["method"] == "GET"
    assert finding.metadata["dbms"] == "SQLite"
    assert len(finding.metadata["techniques"]) == 2
    assert finding.is_actionable() and not finding.verified
    assert finding.evidence[0].calculate_hash()
    assert "Payload:" not in str(finding.to_dict())
    assert [event for event, _ in events] == ["pentest.module_started", "pentest.module_completed"]
    assert ctx.get_shared("sqlmap_results")[0]["status"] == "detected"
    assert "?" not in ctx.get_shared("sqlmap_results")[0]["target"]
    assert finding_to_vulnerability_dict(finding)["category"] == "SQL Injection"
    assert all(not directory.exists() for directory in fake_sqlmap.workdirs)


async def test_safe_arguments_and_private_auth_request(fake_sqlmap):
    ctx = context(sqlmap_runner=fake_sqlmap, sqlmap_parameters="id", sqlmap_delay=0.5)
    ctx.scope.request_delay = 0.75
    ctx.auth_token = "secret-bearer-token"
    ctx.auth_cookies = {"session": "secret-session-cookie"}
    results = await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert results[0].severity == SeverityLevel.HIGH
    command = fake_sqlmap.commands[-1]
    assert {
        "--batch",
        "--ignore-stdin",
        "--ignore-redirects",
        "--ignore-proxy",
        "--drop-set-cookie",
        "--skip-waf",
        "--risk=1",
        "--level=1",
        "--threads=1",
        "--param-filter=GET",
        "--technique=BE",
        "--delay=0.75",
    } <= set(command)
    assert any(
        "extending provided=N" in arg
        and "refresh=N" in arg
        and "custom injection marker=N" in arg
        and "automatically bypass=N" in arg
        for arg in command
    )
    assert command[command.index("-p") + 1] == "id"
    assert "--dump" not in command and "--os-shell" not in command
    assert "secret-bearer-token" not in str(command)
    assert "secret-session-cookie" not in str(command)
    assert "Authorization: Bearer secret-bearer-token" in fake_sqlmap.requests[0]
    assert "Cookie: session=secret-session-cookie" in fake_sqlmap.requests[0]
    assert "secret-bearer-token" not in str(results[0].to_dict())
    assert "secret-session-cookie" not in str(ctx.shared_state)
    assert not fake_sqlmap.workdirs[0].exists()


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize(
    "parameter",
    ["cookie", "COOKIE", "host", "ua", "useragent", "user-agent", "ref", "referer", "referrer"],
)
async def test_header_alias_parameters_do_not_select_headers(fake_sqlmap, method, parameter):
    fake_sqlmap.output = POSITIVE.replace(
        "Parameter: id (GET)", f"Parameter: {parameter} ({method})"
    )
    params = f"{parameter}=1&other=unchanged&{method}=method_value"
    url = "http://127.0.0.1:8000/test"
    config = {"sqlmap_runner": fake_sqlmap, "sqlmap_parameters": [parameter]}
    if method == "GET":
        url += "?" + params
    else:
        config.update({"sqlmap_method": "POST", "sqlmap_data": params})
    ctx = context(url, **config)
    ctx.scope.max_impact = "limited"
    ctx.auth_headers = {"Cookie": "session=trust*ed", "User-Agent": "trust*ed-agent"}
    finding = (await ExecutionEngine().execute("sqlmap_scanner", ctx))[0]
    assert finding.severity == SeverityLevel.HIGH
    command = fake_sqlmap.commands[-1]
    assert f"--param-filter={method}" in command
    assert "-p" not in command
    assert f"--skip=other,{method}" in command
    assert any("custom injection marker=N" in arg for arg in command)
    assert "Cookie: session=trust*ed" in fake_sqlmap.requests[-1]
    assert "User-Agent: trust*ed-agent" in fake_sqlmap.requests[-1]
    assert "trust*ed" not in str(command)


async def test_header_alias_can_be_only_parameter(fake_sqlmap):
    fake_sqlmap.output = POSITIVE.replace("Parameter: id (GET)", "Parameter: cookie (GET)")
    ctx = context("http://127.0.0.1:8000/test?cookie=1", sqlmap_runner=fake_sqlmap)
    finding = (await ExecutionEngine().execute("sqlmap_scanner", ctx))[0]
    assert finding.severity == SeverityLevel.HIGH
    command = fake_sqlmap.commands[-1]
    assert "-p" not in command
    assert not any(item.startswith("--skip=") for item in command)


async def test_negative_requires_every_selected_parameter_to_have_a_completed_result(fake_sqlmap):
    ctx = context(
        "http://127.0.0.1:8000/test?id=1&other=2",
        sqlmap_runner=fake_sqlmap,
        sqlmap_parameters=["id", "other"],
    )
    engine = ExecutionEngine()
    fake_sqlmap.output = "[CRITICAL] all tested parameters do not appear to be injectable.\n"
    assert SQLMapAdapter.parse_output(fake_sqlmap.output)["status"] == "inconclusive"
    assert (await engine.execute("sqlmap_scanner", ctx))[0].severity == SeverityLevel.ERROR

    fake_sqlmap.output = NEGATIVE  # Only id completed; other was skipped.
    partial = (await engine.execute("sqlmap_scanner", ctx))[0]
    assert partial.severity == SeverityLevel.ERROR and "inconclusive" in partial.title

    fake_sqlmap.output = NEGATIVE.replace(
        "[CRITICAL]", "[WARNING] GET parameter 'other' does not seem to be injectable\n[CRITICAL]"
    )
    complete = (await engine.execute("sqlmap_scanner", ctx))[0]
    assert complete.severity == SeverityLevel.INFO
    assert "No SQL injection identified" in complete.title

    fake_sqlmap.output = fake_sqlmap.output.replace("parameter 'other'", "parameter 'OTHER'")
    assert (await engine.execute("sqlmap_scanner", ctx))[0].severity == SeverityLevel.ERROR


async def test_positive_detection_reports_other_skipped_parameters(fake_sqlmap):
    ctx = context(
        "http://127.0.0.1:8000/test?id=1&other=2",
        sqlmap_runner=fake_sqlmap,
        sqlmap_parameters=["id", "other"],
    )
    findings = await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert any(item.severity == SeverityLevel.HIGH for item in findings)
    assert any(
        item.severity == SeverityLevel.ERROR and "partially completed" in item.title
        for item in findings
    )
    assert ctx.shared_state["sqlmap_results"][0]["incomplete_parameters"] == ["other"]

    fake_sqlmap.output = (
        "[WARNING] GET parameter 'other' does not seem to be injectable\n" + POSITIVE
    )
    complete = await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert len(complete) == 1 and complete[0].severity == SeverityLevel.HIGH


async def test_no_parameters_skips_before_connect(fake_sqlmap):
    ctx = context("http://127.0.0.1:8000/test", sqlmap_runner=fake_sqlmap)
    results = await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert results[0].severity == SeverityLevel.INFO
    assert "no parameters" in results[0].title
    assert not fake_sqlmap.commands


async def test_negative_is_not_a_guarantee_of_safety(fake_sqlmap):
    fake_sqlmap.output = NEGATIVE
    ctx = context(sqlmap_runner=fake_sqlmap)
    finding = (await ExecutionEngine().execute("sqlmap_scanner", ctx))[0]
    assert finding.severity == SeverityLevel.INFO
    assert "does not prove" in finding.description
    assert not finding.is_actionable()
    assert ctx.shared_state["sqlmap_results"][0]["status"] == "not_detected"


@pytest.mark.parametrize(
    "output", ["", "[CRITICAL] unable to connect to the target URL", "sqlmap failed"]
)
async def test_exit_zero_without_completed_result_is_inconclusive(fake_sqlmap, output):
    fake_sqlmap.output = output
    finding = (
        await ExecutionEngine().execute("sqlmap_scanner", context(sqlmap_runner=fake_sqlmap))
    )[0]
    assert finding.severity == SeverityLevel.ERROR
    assert "inconclusive" in finding.title
    assert all(not directory.exists() for directory in fake_sqlmap.workdirs)


async def test_nonzero_exit_is_error_and_cleans_up(fake_sqlmap):
    fake_sqlmap.exit_code = 2
    finding = (
        await ExecutionEngine().execute("sqlmap_scanner", context(sqlmap_runner=fake_sqlmap))
    )[0]
    assert finding.severity == SeverityLevel.ERROR
    assert "failed" in finding.title
    assert all(not directory.exists() for directory in fake_sqlmap.workdirs)


@pytest.mark.parametrize(
    "target",
    [
        "file:///etc/passwd?id=1",
        "http://user:password@127.0.0.1/test?id=1",
        "http://127.0.0.1:99999/test?id=1",
        "http://127.0.0.1/test?id=1#fragment",
        "http://127.0.0.1/test?id=1*",
        "http://127.0.0.1/test?id=1%2A",
        "http://127.0.0.1/test?id=1%252A",
        "http://127.0.0.1/approved/%252e%252e/private?id=1",
        "http://127.0.0.1/approved%5Cprivate?id=1",
        "http://127.0.0.1/test?id=%0d%0aHost:evil",
        "http://127.0.0.1/test?id=1\r\nHost:evil",
        "http://127.0.0.1/test?--os-shell=1",
    ],
)
def test_unsafe_urls_or_parameter_names_are_refused(target):
    with pytest.raises(ValueError):
        SQLMapAdapter.parameter_names(target, "GET", None)


async def test_scope_substring_spoof_is_rejected_before_tool(fake_sqlmap):
    ctx = PentestContext(
        target="http://unapproved.example/test?id=1&next=approved.example",
        scope=ScopeConfig(allowed_targets=["approved.example"]),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(OutOfScopeError):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


async def test_implicit_default_port_must_be_in_scope(fake_sqlmap):
    ctx = PentestContext(
        target="http://127.0.0.1/test?id=1",
        scope=ScopeConfig(allowed_targets=["127.0.0.1"], allowed_ports=[443]),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(RoEViolationError):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


async def test_scope_and_exclusion_refuse_out_of_scope_before_tool(fake_sqlmap):
    engine = ExecutionEngine()
    denied = context("http://elsewhere.example:8000/test?id=1", sqlmap_runner=fake_sqlmap)
    with pytest.raises(OutOfScopeError):
        await engine.execute("sqlmap_scanner", denied)
    excluded = PentestContext(
        target="http://example.com/test?id=1",
        scope=ScopeConfig(allowed_targets=["example.com"], excluded_targets=["EXAMPLE.COM"]),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(OutOfScopeError):
        await engine.execute("sqlmap_scanner", excluded)
    assert not fake_sqlmap.commands


@pytest.mark.parametrize(
    "excluded", ["127.0.0.1", "127.0.0.0/8", "http://127.0.0.1:8000/private", "::1"]
)
async def test_hostname_with_ip_exclusion_is_refused_without_running_tool(fake_sqlmap, excluded):
    ctx = PentestContext(
        target="http://localhost:8000/test?id=1",
        scope=ScopeConfig(
            allowed_targets=["localhost"], excluded_targets=[excluded], allowed_ports=[8000]
        ),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(OutOfScopeError):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


async def test_encoded_path_cannot_bypass_a_path_only_exclusion(fake_sqlmap):
    ctx = PentestContext(
        target="http://127.0.0.1:8000/%70rivate?id=1",
        scope=ScopeConfig(
            allowed_targets=["127.0.0.1"], excluded_targets=["/private"], allowed_ports=[8000]
        ),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(OutOfScopeError):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


async def test_wildcard_exclusion_is_refused_rather_than_ignored(fake_sqlmap):
    ctx = PentestContext(
        target="http://localhost:8000/test?id=1",
        scope=ScopeConfig(
            allowed_targets=["localhost"], excluded_targets=["*.localhost"], allowed_ports=[8000]
        ),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(OutOfScopeError):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


@pytest.mark.parametrize("host", ["127.0.0.1", "[::ffff:127.0.0.1]"])
async def test_literal_ip_in_excluded_network_is_refused(fake_sqlmap, host):
    ctx = PentestContext(
        target=f"http://{host}:8000/test?id=1",
        scope=ScopeConfig(
            allowed_targets=[host], excluded_targets=["127.0.0.0/8"], allowed_ports=[8000]
        ),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(OutOfScopeError):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


async def test_unrelated_network_exclusion_allows_approved_literal_ip(fake_sqlmap):
    ctx = context(sqlmap_runner=fake_sqlmap)
    ctx.scope.excluded_targets = ["10.0.0.0/8"]
    assert (await ExecutionEngine().execute("sqlmap_scanner", ctx))[
        0
    ].severity == SeverityLevel.HIGH


async def test_qualified_ip_exclusion_preserves_path_boundary(fake_sqlmap):
    ctx = context(sqlmap_runner=fake_sqlmap)
    ctx.scope.excluded_targets = ["http://127.0.0.1:8000/private"]
    assert (await ExecutionEngine().execute("sqlmap_scanner", ctx))[
        0
    ].severity == SeverityLevel.HIGH


@pytest.mark.parametrize("window", [{}, {"start": "2000-01-01", "end": "2000-01-02"}])
async def test_configured_testing_window_is_refused_until_enforced(fake_sqlmap, window):
    ctx = context(sqlmap_runner=fake_sqlmap)
    ctx.scope.testing_window = window
    with pytest.raises(RoEViolationError, match="testing_window"):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


async def test_scope_path_is_not_approved_by_a_query_string(fake_sqlmap):
    ctx = PentestContext(
        target="http://example.com/else?id=1&next=example.com/approved",
        scope=ScopeConfig(allowed_targets=["example.com/approved"]),
        config={"sqlmap_runner": fake_sqlmap},
    )
    with pytest.raises(OutOfScopeError):
        await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert not fake_sqlmap.commands


async def test_post_and_higher_level_require_impact_authorization(fake_sqlmap):
    engine = ExecutionEngine()
    post_ctx = context(
        "http://127.0.0.1:8000/test",
        sqlmap_runner=fake_sqlmap,
        sqlmap_method="POST",
        sqlmap_data="id=1",
    )
    denied_post = await engine.execute("sqlmap_scanner", post_ctx)
    assert denied_post[0].severity == SeverityLevel.ERROR
    assert "POST" in denied_post[0].title
    level_ctx = context(sqlmap_runner=fake_sqlmap, sqlmap_level=2)
    denied_level = await engine.execute("sqlmap_scanner", level_ctx)
    assert denied_level[0].severity == SeverityLevel.ERROR
    assert "level" in denied_level[0].title
    assert not fake_sqlmap.commands


async def test_authorized_post_form_and_level(fake_sqlmap):
    ctx = context(
        "http://127.0.0.1:8000/test",
        sqlmap_runner=fake_sqlmap,
        sqlmap_method="POST",
        sqlmap_data="id=1&token=private-form-value",
        sqlmap_parameters=["id"],
        sqlmap_level=2,
        sqlmap_techniques="B",
    )
    ctx.scope.max_impact = "limited"
    results = await ExecutionEngine().execute("sqlmap_scanner", ctx)
    assert results[0].severity == SeverityLevel.HIGH
    assert results[0].metadata["method"] == "POST"
    command = fake_sqlmap.commands[-1]
    assert "--param-filter=POST" in command
    assert "--level=2" in command and "--technique=B" in command
    assert "private-form-value" not in str(command)
    assert "private-form-value" in fake_sqlmap.requests[0]
    assert "private-form-value" not in str(results[0].to_dict())
    assert all(not directory.exists() for directory in fake_sqlmap.workdirs)


@pytest.mark.parametrize("technique", ["U", "T", "S", "BEUSTQ", "--dump", ""])
async def test_unsupported_techniques_never_launch_scan(fake_sqlmap, technique):
    ctx = context(sqlmap_runner=fake_sqlmap, sqlmap_techniques=technique)
    finding = (await ExecutionEngine().execute("sqlmap_scanner", ctx))[0]
    assert finding.severity == SeverityLevel.ERROR
    assert all("-r" not in command for command in fake_sqlmap.commands)


@pytest.mark.parametrize(
    "headers",
    [{"Host": "elsewhere.example"}, {"X-Test": "safe\r\nHost: evil"}, {"X-Original-URL": "/admin"}],
)
async def test_unsafe_headers_never_launch_scan(fake_sqlmap, headers):
    ctx = context(sqlmap_runner=fake_sqlmap)
    ctx.auth_headers = headers
    finding = (await ExecutionEngine().execute("sqlmap_scanner", ctx))[0]
    assert finding.severity == SeverityLevel.ERROR
    assert all("-r" not in command for command in fake_sqlmap.commands)


async def test_arbitrary_options_are_refused_before_connect(fake_sqlmap):
    ctx = context(sqlmap_runner=fake_sqlmap, sqlmap_args=["--dump"])
    finding = (await ExecutionEngine().execute("sqlmap_scanner", ctx))[0]
    assert finding.severity == SeverityLevel.ERROR
    assert not fake_sqlmap.commands


async def test_unknown_parameter_is_refused_before_connect(fake_sqlmap):
    ctx = context(sqlmap_runner=fake_sqlmap, sqlmap_parameters=["not-in-request"])
    finding = (await ExecutionEngine().execute("sqlmap_scanner", ctx))[0]
    assert finding.severity == SeverityLevel.ERROR
    assert not fake_sqlmap.commands


async def test_unrequested_or_malformed_summary_is_inconclusive(fake_sqlmap):
    fake_sqlmap.output = POSITIVE.replace("Parameter: id (GET)", "Parameter: other (GET)")
    finding = (
        await ExecutionEngine().execute("sqlmap_scanner", context(sqlmap_runner=fake_sqlmap))
    )[0]
    assert finding.severity == SeverityLevel.ERROR
    assert "inconclusive" in finding.title
    malformed = POSITIVE.replace("    Title:", "    Unexpected:")
    assert SQLMapAdapter.parse_output(malformed)["status"] == "inconclusive"


async def test_timeout_and_cancellation_cleanup(fake_sqlmap):
    class TimeoutRunner(FakeSQLMap):
        async def __call__(self, cmd, timeout):
            if "--version" in cmd:
                return await super().__call__(cmd, timeout)
            self.workdirs.append(Path(cmd[cmd.index("-r") + 1]).parent)
            raise TimeoutError

    runner = TimeoutRunner()
    finding = (await ExecutionEngine().execute("sqlmap_scanner", context(sqlmap_runner=runner)))[0]
    assert finding.severity == SeverityLevel.ERROR
    assert all(not directory.exists() for directory in runner.workdirs)

    fake_sqlmap.wait = 30
    task = asyncio.create_task(
        ExecutionEngine().execute("sqlmap_scanner", context(sqlmap_runner=fake_sqlmap))
    )
    await asyncio.wait_for(fake_sqlmap.started.wait(), timeout=5)
    assert fake_sqlmap.workdirs[0].exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not fake_sqlmap.workdirs[0].exists()


@pytest.mark.skipif(os.name == "nt", reason="process liveness check uses POSIX signals")
async def test_real_subprocess_is_reaped_on_timeout_and_cancellation(tmp_path):
    for cancel in (False, True):
        pid_path = tmp_path / f"child-{cancel}.pid"
        code = (
            "import os,time,pathlib; "
            f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid())); "
            "time.sleep(30)"
        )
        task = asyncio.create_task(_default_subprocess_runner([sys.executable, "-c", code], 2))
        for _ in range(100):
            if pid_path.exists():
                break
            await asyncio.sleep(0.02)
        assert pid_path.exists()
        pid = int(pid_path.read_text())
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(TimeoutError):
                await task
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.fixture
def fake_metasploit(monkeypatch):
    service = FakeMsfrpcd()
    service.start()
    monkeypatch.setattr(settings, "MSF_ENABLED", True)
    monkeypatch.setattr(settings, "MSF_RPC_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "MSF_RPC_PORT", service.port)
    monkeypatch.setattr(settings, "MSF_RPC_PASSWORD", "test-rpc-password")
    monkeypatch.setattr(settings, "MSF_RPC_SSL", False)
    yield service
    service.stop()


async def test_three_tools_coexist_in_one_sequential_plan(
    fake_sqlmap, fake_metasploit, monkeypatch
):
    monkeypatch.setattr(settings, "NMAP_ENABLED", True)
    nmap = FakeNmap()
    ctx = PentestContext(
        target="http://127.0.0.1:80/test?id=1",
        scope=ScopeConfig(allowed_targets=["127.0.0.1"], allowed_ports=[80, 443]),
        config={
            "sqlmap_runner": fake_sqlmap,
            "nmap_runner": nmap,
            "msf_options": {"PORTS": "80,443"},
        },
    )
    names = ["nmap_scanner", "sqlmap_scanner", "metasploit_scanner"]
    report = await ExecutionScheduler().run(
        [ScheduledModule(module_name=name) for name in names], ctx
    )
    assert report.modules_run == 3
    assert {item.module_name for item in report.findings} == set(names)
    assert all(item.severity != SeverityLevel.ERROR for item in report.findings)
    assert next(
        item for item in report.findings if item.module_name == "sqlmap_scanner"
    ).is_actionable()
    assert ctx.shared_state["nmap_open_ports"] == [80, 443]
    assert ctx.shared_state["sqlmap_results"][0]["injections"][0]["parameter"] == "id"
    assert fake_metasploit.written
    assert all(not directory.exists() for directory in fake_sqlmap.workdirs)


async def test_different_tools_in_independent_parallel_engagements(
    fake_sqlmap, fake_metasploit, monkeypatch
):
    monkeypatch.setattr(settings, "NMAP_ENABLED", True)
    fake_sqlmap.wait = 0.05
    nmap = FakeNmap()
    contexts = [
        PentestContext(
            target="http://127.0.0.1:80/test?id=1",
            scope=ScopeConfig(allowed_targets=["127.0.0.1"], allowed_ports=[80, 443]),
            config={"sqlmap_runner": fake_sqlmap, "nmap_runner": nmap},
        )
        for _ in range(3)
    ]
    engine = ExecutionEngine()
    results = await asyncio.gather(
        engine.execute("nmap_scanner", contexts[0]),
        engine.execute("sqlmap_scanner", contexts[1]),
        engine.execute("metasploit_scanner", contexts[2]),
    )
    assert all(
        findings and all(item.severity != SeverityLevel.ERROR for item in findings)
        for findings in results
    )
    assert results[0][0].metadata["open_ports"] == [80, 443]
    assert results[1][0].is_actionable()
    assert results[2][0].metadata["open_ports"] == [80, 443]
    assert len({ctx.engagement_id for ctx in contexts}) == 3
    assert all(not directory.exists() for directory in fake_sqlmap.workdirs)


async def test_independent_parallel_scans_have_isolated_workdirs_and_state(fake_sqlmap):
    fake_sqlmap.wait = 0.05
    first = context(sqlmap_runner=fake_sqlmap)
    second = context("http://127.0.0.1:8000/other?id=1", sqlmap_runner=fake_sqlmap)
    results = await asyncio.gather(
        ExecutionEngine().execute("sqlmap_scanner", first),
        ExecutionEngine().execute("sqlmap_scanner", second),
    )
    assert all(result[0].severity == SeverityLevel.HIGH for result in results)
    assert len(set(fake_sqlmap.workdirs)) == 2
    assert all(not directory.exists() for directory in fake_sqlmap.workdirs)
    assert first.shared_state is not second.shared_state
    assert first.shared_state["sqlmap_results"][0]["target"].endswith("/test")
    assert second.shared_state["sqlmap_results"][0]["target"].endswith("/other")


async def test_sqlmap_persist_findings_and_evidence(db_session, fake_sqlmap):
    user = User(
        id=str(uuid.uuid4()),
        full_name="SQLMap Test User",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        company_name="Example",
        job_title="Tester",
        hashed_password="test-hash",
    )
    db_session.add(user)
    await db_session.flush()
    engagement = Engagement(
        id=str(uuid.uuid4()),
        engagement_number=f"SQL-{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        project_name="SQLMap Test",
        organization_name="Example",
        status=EngagementStatus.RED_TEAM_IN_PROGRESS,
    )
    db_session.add(engagement)
    await db_session.flush()
    findings = await ExecutionEngine().execute("sqlmap_scanner", context(sqlmap_runner=fake_sqlmap))
    assert await persist_findings(db_session, engagement.id, findings) == 1
    rows = (await db_session.execute(select(Vulnerability))).scalars().all()
    evidence = (await db_session.execute(select(VulnerabilityEvidence))).scalars().all()
    assert rows[0].category == "SQL Injection"
    assert rows[0].raw_technical_data["metadata"]["tool"] == "sqlmap"
    assert len(evidence) == 1 and "hash" in evidence[0].content
