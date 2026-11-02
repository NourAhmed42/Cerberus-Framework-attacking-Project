"""Guards for scripts/live_tests/run_all_tools.py.

These tests do not scan anything. They check that the runner refuses to start
without explicit confirmation and that its public targets are the approved ones.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts" / "live_tests"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runner_refuses_public_tests_without_confirmation():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "run_all_tools.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert "--confirm-public-tests" in result.stderr


def test_public_targets_are_the_approved_ones():
    public = _load("public_tool_results", SCRIPTS / "public_tool_results.py")
    assert public.NMAP_TARGET == "scanme.nmap.org"
    assert public.SQLMAP_TARGET.startswith("https://sekumart.sekuripy.hr/product.php?id=1")
    assert public.SUPPORTED_PROFILES == ("nmap", "sqlmap")
    assert "metasploit" in public.UNAVAILABLE_PROFILES
