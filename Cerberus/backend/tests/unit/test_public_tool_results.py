"""Hermetic tests for the public-results recorder. These tests never scan the Internet."""

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT / "scripts" / "live_tests" / "public_tool_results.py"
RENDERER_PATH = ROOT / "scripts" / "render_real_results.py"


def import_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = import_script("public_tool_results", RUNNER_PATH)
renderer = import_script("render_real_results", RENDERER_PATH)


def sql_command(tmp_path):
    directory = tmp_path / "cerberus-sqlmap-example"
    directory.mkdir()
    request = directory / "request.txt"
    request.write_bytes(
        (
            "GET /product.php?id=1 HTTP/1.1\r\n"
            "Host: sekumart.sekuripy.hr\r\n"
            f"User-Agent: {runner.USER_AGENT}\r\n\r\n"
        ).encode("ascii")
    )
    return [
        "sqlmap",
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
        runner.SQL_ANSWERS,
        f"--output-dir={directory / 'output'}",
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


@pytest.fixture
def isolated_asyncio_run(monkeypatch):
    """Exercise the synchronous CLI without clearing pytest's session event loop."""

    def run(coroutine):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coroutine)
        finally:
            loop.close()

    monkeypatch.setattr(runner.asyncio, "run", run)


def empty_data():
    return {
        "schema_version": 1,
        "updated_at": "none",
        "attempts": {"nmap": [], "sqlmap": []},
        "results": {
            name: {"latest": {"status": "not_tested"}, "last_success": None}
            for name in ("nmap", "sqlmap", "metasploit")
        },
    }


def test_help_and_missing_confirmation_never_need_dependencies_or_change_data():
    before = (ROOT / "docs" / "real_results.json").read_bytes()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    help_result = subprocess.run(
        [sys.executable, "-S", str(RUNNER_PATH), "--help"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    refusal = subprocess.run(
        [sys.executable, "-S", str(RUNNER_PATH), "all"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "--confirm-public-tests" in help_result.stdout
    assert refusal.returncode != 0 and "require --confirm-public-tests" in refusal.stderr
    assert (ROOT / "docs" / "real_results.json").read_bytes() == before


def test_cli_rejects_arbitrary_targets():
    result = subprocess.run(
        [sys.executable, "-S", str(RUNNER_PATH), "nmap", "--target", "example.com"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "unrecognized arguments" in result.stderr


def test_sqlmap_guard_accepts_only_the_precise_request_and_arguments(tmp_path):
    command = sql_command(tmp_path)
    runner._guard_sqlmap(command)
    for replacement in ("--risk=3", "--technique=BT", "--threads=10", "--dump"):
        with pytest.raises(runner.RefreshError, match="refused before launch"):
            runner._guard_sqlmap(command + [replacement])
    altered = command.copy()
    altered[altered.index("--ignore-redirects")] = "--follow-redirects"
    with pytest.raises(runner.RefreshError):
        runner._guard_sqlmap(altered)
    request = Path(command[2])
    request.write_bytes(request.read_bytes().replace(b"sekumart.sekuripy.hr", b"other.example"))
    with pytest.raises(runner.RefreshError):
        runner._guard_sqlmap(command)


async def test_nmap_guard_refuses_extra_or_changed_arguments_before_delegate():
    calls = []

    async def delegate(cmd, timeout):
        calls.append(cmd)
        return 0, "output", ""

    capture = runner.CaptureRunner("nmap", delegate)
    await capture(["nmap", "--version"], 5)
    await capture(["nmap", *runner.NMAP_ARGS], 5)
    assert len(calls) == 2 and capture.scan_started
    with pytest.raises(runner.RefreshError, match="before launch"):
        await capture(["nmap", *runner.NMAP_ARGS[:-1], "other.example"], 5)
    with pytest.raises(runner.RefreshError, match="before launch"):
        await capture(["nmap", *runner.NMAP_ARGS, "--script", "*"], 5)
    assert len(calls) == 2


def test_rate_limit_is_recorded_before_scan_and_rejects_invalid_history(monkeypatch, tmp_path):
    data_path = tmp_path / "snapshot.json"
    monkeypatch.setattr(runner, "DATA", data_path)
    data = empty_data()
    now = datetime(2026, 10, 28, 1, tzinfo=UTC)
    runner._reserve_attempt(data, "nmap", now)
    assert json.loads(data_path.read_text())["attempts"]["nmap"] == [runner._timestamp(now)]
    data["attempts"]["nmap"] = [runner._timestamp(now)] * runner.LIMITS["nmap"]
    with pytest.raises(runner.RefreshError, match="24-hour"):
        runner._reserve_attempt(data, "nmap", now)
    data["attempts"]["nmap"] = [runner._timestamp(now - timedelta(hours=25))]
    runner._reserve_attempt(data, "nmap", now)
    assert data["attempts"]["nmap"] == [runner._timestamp(now)]
    data["attempts"]["nmap"] = ["not a timestamp"]
    with pytest.raises(runner.RefreshError, match="Invalid"):
        runner._reserve_attempt(data, "nmap", now)


def test_failed_latest_keeps_previous_real_capture_clearly_dated(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "DATA", tmp_path / "snapshot.json")
    data = empty_data()
    success = {
        "status": "captured",
        "at_utc": "2026-10-27T12:00:00+00:00",
        "target": runner.NMAP_TARGET,
        "version": "7.95",
        "framework_output": "REAL PREVIOUS RESULT",
    }
    runner._set_latest(data, "nmap", success)
    failure = {"status": "failed", "at_utc": "2026-10-28T12:00:00+00:00", "message": "timeout"}
    runner._set_latest(data, "nmap", failure)
    assert data["results"]["nmap"]["last_success"] == success
    assert renderer._display(data["results"]["nmap"]) == success
    description = renderer._status(data["results"]["nmap"])
    assert "FAILED" in description and "Previous successful capture" in description
    assert "2026-10-27" in description and "2026-10-28" in description
    no_previous = {"latest": failure, "last_success": None}
    assert renderer._display(no_previous) is failure
    assert "Failed attempt output" in renderer._status(no_previous)


def test_three_real_tool_report_uses_saved_local_capture():
    capture = {
        "at_utc": "2026-10-28T01:00:00+00:00",
        "target": "http://127.0.0.1:1234/vulnerable?id=1",
        "versions": {"nmap": "7.95", "sqlmap": "1.9", "metasploit": "6.5"},
        "plan": ["nmap_scanner", "sqlmap_scanner", "metasploit_scanner"],
        "nmap_probed_ports": [1234, 2345],
        "nmap_open_ports": [1234],
        "sqlmap_status": "detected",
        "sqlmap_method": "GET",
        "sqlmap_parameter": "id",
        "msf_scanned_ports": [1234, 2345],
        "msf_open_ports": [1234],
        "scope_refused": ["nmap_scanner", "sqlmap_scanner", "metasploit_scanner"],
        "rpc_timeout_seconds": 60,
        "first_console_create_seconds": 15.0,
        "consoles_left_after_successful_run": 0,
        "metasploit_console_excerpt": "REAL CONSOLE EXCERPT",
    }
    text = renderer._format_combined_local({"local_combined_check": capture})
    assert "disposable loopback lab" in text
    assert "Nmap probed ports: [1234, 2345]" in text
    assert "Nmap open ports: [1234]" in text
    assert "Metasploit scanned ports: [1234, 2345]" in text
    assert "REAL CONSOLE EXCERPT" in text
    assert "No genuine" in renderer._format_combined_local({})


def test_compact_framework_view_is_derived_from_captured_finding():
    original = [
        {
            "severity": "info",
            "title": "scan finished",
            "target": "scanme.nmap.org",
            "module_name": "nmap_scanner",
            "verified": False,
            "confidence": "high",
            "metadata": {
                "probed_ports": [22, 80],
                "open_ports": [80],
                "services": [{"port": 80, "service": "http", "product": "Apache", "version": "2"}],
            },
        }
    ]
    view = renderer._format_framework_output(json.dumps(original), "nmap")
    assert "[INFO] scan finished" in view
    assert "open TCP ports: [80]" in view and "80/tcp  http Apache 2" in view
    assert "verified: false" in view
    assert renderer._format_framework_output("not-json", "nmap") == "not-json"


def test_nmap_pdf_excerpt_preserves_selected_real_xml_values():
    raw = (
        '<status state="up" reason="user-set" />'
        '<address addr="45.33.32.156" addrtype="ipv4" />'
        '<ports><port protocol="tcp" portid="80"><state state="open" reason="syn-ack" />'
        '<service name="http" product="Apache" version="2.4.7" method="probed" conf="10">'
        "<cpe>cpe:/a:apache:http_server:2.4.7</cpe></service></port></ports>"
    )
    excerpt = renderer._format_nmap_xml(raw)
    assert 'addr="45.33.32.156"' in excerpt
    assert 'portid="80"' in excerpt and 'state="open"' in excerpt
    assert 'product="Apache"' in excerpt and 'version="2.4.7"' in excerpt
    assert "<cpe>" not in excerpt  # Omitted, not edited into a different claim.


def test_local_metasploit_result_does_not_become_a_public_capture():
    entry = {
        "latest": {"status": "not_tested"},
        "last_success": None,
        "local_standalone_check": {
            "at_utc": "2026-10-27T22:46:44+00:00",
            "version": "example-version",
            "target": "127.0.0.1:12345",
            "tool_status": "PASS",
            "integration_status": "FAILED",
            "tool_output_excerpt": "LOCAL EXAMPLE OUTPUT",
        },
    }
    view = renderer._format_metasploit_local(entry)
    assert "LOCAL EXAMPLE OUTPUT" in view and "Cerberus connection: FAILED" in view
    assert "NOT TESTED" in renderer._status(entry)
    assert renderer._format_metasploit_local({}) == "No real local standalone check recorded."


def test_renderer_escapes_untrusted_output_inside_long_fences():
    import markdown

    block = renderer._code_block('```\n<img src="https://attacker.example/x">\n```')
    rendered = markdown.markdown(block, extensions=["fenced_code"])
    assert "<img " not in rendered
    assert "&lt;img" in rendered


def test_registered_tools_are_covered_and_pdf_matches_source_and_data():
    from app.ai_engine.pentest import default_tool_registry

    registered = {item["name"] for item in default_tool_registry().list_metadata()}
    source = (ROOT / "docs" / "REAL_RESULTS.md").read_bytes()
    data_bytes = (ROOT / "docs" / "real_results.json").read_bytes()
    names = set(re.findall(r"<!-- tool:([a-z0-9_-]+) -->", source.decode()))
    assert names == registered == set(json.loads(data_bytes)["results"])
    assert registered == set(runner.SUPPORTED_PROFILES + runner.UNAVAILABLE_PROFILES)
    assert not (set(runner.SUPPORTED_PROFILES) & set(runner.UNAVAILABLE_PROFILES))
    assert set(runner.LIMITS) == set(runner.SUPPORTED_PROFILES)
    digest = hashlib.sha256(source + b"\0" + data_bytes).hexdigest().encode()
    pdf = (ROOT / "docs" / "real result.pdf").read_bytes()
    assert b"source-and-data-sha256:" + digest in pdf


async def test_framework_collection_uses_guarded_profiles_without_real_network(monkeypatch):
    from app.core.config import settings

    fields = (
        "NMAP_ENABLED",
        "SQLMAP_ENABLED",
        "MSF_ENABLED",
        "PENTEST_MODULE_TIMEOUT",
        "PENTEST_HTTP_TIMEOUT",
        "PENTEST_REQUEST_DELAY",
        "PENTEST_USER_AGENT",
        "NMAP_TIMEOUT",
        "SQLMAP_TIMEOUT",
    )
    for name in fields:
        monkeypatch.setattr(settings, name, getattr(settings, name))
    framework = runner._prepare_framework()
    xml = (
        '<nmaprun version="7.95"><host><status state="up"/>'
        '<address addr="45.33.32.156" addrtype="ipv4"/><ports>'
        '<port protocol="tcp" portid="80"><state state="open"/>'
        '<service name="http"/></port></ports></host>'
        '<runstats><finished exit="success"/><hosts up="1" down="0" total="1"/>'
        "</runstats></nmaprun>"
    )
    sql = (
        "sqlmap identified the following injection point(s) with a total of 12 HTTP(s) requests:\n"
        "---\nParameter: id (GET)\n    Type: error-based\n"
        "    Title: Example error technique\n    Payload: id=1 AND 1=1\n---\n"
        "back-end DBMS: MySQL\n"
    )
    calls = []

    async def nmap_delegate(cmd, timeout):
        calls.append(("nmap", cmd))
        return (0, "Nmap version 7.95\n", "") if cmd[-1] == "--version" else (0, xml, "")

    async def sqlmap_delegate(cmd, timeout):
        calls.append(("sqlmap", cmd))
        return (0, "1.9.6#stable\n", "") if cmd[-1] == "--version" else (0, sql, "")

    framework.nmap_runner = nmap_delegate
    framework.sqlmap_runner = sqlmap_delegate
    nmap = await runner._collect("nmap", framework)
    sqlmap = await runner._collect("sqlmap", framework)
    assert nmap["status"] == "captured" and '"open_ports": [' in nmap["framework_output"]
    assert '<port protocol="tcp" portid="80">' in nmap["tool_output_excerpt"]
    assert sqlmap["status"] == "captured" and '"severity": "high"' in sqlmap["framework_output"]
    assert "Parameter: id (GET)" in sqlmap["tool_output_excerpt"]
    assert [name for name, _ in calls] == ["nmap", "nmap", "sqlmap", "sqlmap"]


def test_failed_refresh_is_recorded_without_erasing_prior_success(
    monkeypatch, tmp_path, isolated_asyncio_run
):
    data_path = tmp_path / "results.json"
    data = empty_data()
    previous = {
        "status": "captured",
        "at_utc": "2026-10-27T12:00:00+00:00",
        "message": "previous real result",
    }
    data["results"]["nmap"] = {"latest": previous, "last_success": previous}
    data_path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(runner, "DATA", data_path)
    monkeypatch.setattr(runner, "_pdf_ready", lambda: None)
    monkeypatch.setattr(runner, "_available", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        runner,
        "_prepare_framework",
        lambda: SimpleNamespace(settings=SimpleNamespace(NMAP_PATH="nmap")),
    )

    async def failed_collect(name, framework):
        raise TimeoutError("test timeout")

    monkeypatch.setattr(runner, "_collect", failed_collect)
    renders = []
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: renders.append(args) or SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(sys, "argv", ["runner", "nmap", "--confirm-public-tests"])
    assert runner.main() == 1
    saved = json.loads(data_path.read_text())
    assert saved["results"]["nmap"]["latest"]["status"] == "failed"
    assert saved["results"]["nmap"]["last_success"] == previous
    assert len(renders) == 1


def test_explicit_all_refresh_runs_two_profiles_and_rebuilds(
    monkeypatch, tmp_path, isolated_asyncio_run
):
    data_path = tmp_path / "results.json"
    data_path.write_text(json.dumps(empty_data()), encoding="utf-8")
    monkeypatch.setattr(runner, "DATA", data_path)
    monkeypatch.setattr(runner, "_pdf_ready", lambda: None)
    monkeypatch.setattr(runner, "_available", lambda *args, **kwargs: True)
    framework = SimpleNamespace(settings=SimpleNamespace(NMAP_PATH="nmap", SQLMAP_PATH="sqlmap"))
    monkeypatch.setattr(runner, "_prepare_framework", lambda: framework)
    calls = []

    async def fake_collect(name, framework):
        calls.append(name)
        await asyncio.sleep(0)
        return {
            "status": "captured",
            "at_utc": runner._timestamp(runner._utc_now()),
            "message": "OK",
        }

    monkeypatch.setattr(runner, "_collect", fake_collect)
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0)
    )
    monkeypatch.setattr(sys, "argv", ["runner", "all", "--confirm-public-tests"])
    assert runner.main() == 0
    saved = json.loads(data_path.read_text())
    assert calls == ["nmap", "sqlmap"]
    assert saved["results"]["nmap"]["latest"]["status"] == "captured"
    assert saved["results"]["sqlmap"]["latest"]["status"] == "captured"
    assert saved["results"]["metasploit"]["latest"]["status"] == "not_tested"
    assert len(saved["attempts"]["nmap"]) == len(saved["attempts"]["sqlmap"]) == 1


def test_ipv6_metasploit_capture_is_shown_only_as_a_local_check():
    entry = {
        "latest": {"status": "not_tested"},
        "local_integration_check": {"target": "127.0.0.1:1234"},
        "local_ipv6_check": {
            "at_utc": "2026-10-28T01:59:00+00:00",
            "target": "[::1]:4321",
            "finding_title": "IPv6 local test",
            "open_ports": [4321],
            "tool_output_excerpt": "[+] ::1:4321 - TCP OPEN",
        },
    }
    display = renderer._format_metasploit_local(entry)
    assert "Separate genuine IPv6 loopback" in display
    assert "[::1]:4321" in display and "TCP OPEN" in display
    assert "NOT TESTED" in renderer._status(entry)


def test_new_genuine_local_metasploit_capture_never_becomes_a_public_result():
    data = json.loads((ROOT / "docs" / "real_results.json").read_text())
    entry = data["results"]["metasploit"]
    current = entry["local_integration_check"]
    history = entry["local_standalone_check"]
    assert entry["latest"]["status"] == "not_tested"
    assert entry["last_success"] is None
    assert current["integration_status"].startswith("PASS")
    assert current["target"].startswith("127.0.0.1:")
    assert str(current["open_ports"][0]) in current["tool_output_excerpt"]
    assert "TCP OPEN" in current["tool_output_excerpt"]
    assert history["integration_status"].startswith("FAILED")
    display = renderer._format_metasploit_local(entry)
    assert "Cerberus connection: PASS" in display
    assert current["finding_title"] in display
    assert "NOT TESTED" in renderer._status(entry)
