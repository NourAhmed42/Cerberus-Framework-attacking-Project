# Nmap: integration and how to use

**Updated: 2 November 2026 (Cairo) · Nmap 7.95 used in the captures**

> **Authorization first.** Scan only systems you own or have written permission to scan. Nmap is permitted on one public site in this project: `scanme.nmap.org`. Its operator allows about 12 scans per day and forbids exploits and denial of service.

## 1. What was added

| File | Role |
|---|---|
| `backend/app/ai_engine/pentest/tools/nmap_adapter.py` | Runs the real `nmap` program and reads its XML output. Changed: only the `banner` and `ssl-cert` NSE scripts are allowed. |
| `backend/app/ai_engine/pentest/modules/tools/nmap_scanner.py` | The framework module `nmap_scanner`. Checks scope, ports and scripts, then records findings. Changed. |
| `backend/app/core/config.py` and `backend/.env.example` | `NMAP_ENABLED`, `NMAP_PATH`, `NMAP_TIMEOUT` |
| `backend/tests/unit/test_pentest_tools.py` | Nmap adapter and module tests (changed) |
| `scripts/live_tests/beginner_tools_lab.py` | `nmap` mode: real Nmap against a local lab |
| `scripts/live_tests/public_tool_results.py` | Public capture of `scanme.nmap.org` (run only with explicit confirmation) |

## 2. Install Nmap

**Mac (zsh):**

```zsh
brew install nmap
nmap --version
```

**Windows (PowerShell):** Download and run the official installer from [nmap.org/download](https://nmap.org/download.html). Open a new terminal, then check:

```powershell
nmap --version
```

If `nmap` is not found, find the installed `nmap.exe` and set the path for the current terminal only:

```powershell
$env:NMAP_PATH = 'C:\Program Files (x86)\Nmap\nmap.exe'
& $env:NMAP_PATH --version
```

**Expected:** a line such as `Nmap version 7.95`.

## 3. Settings

In `backend/.env` (private; do not commit):

```dotenv
NMAP_ENABLED=true
NMAP_PATH=nmap
NMAP_TIMEOUT=120
```

Set `NMAP_PATH` to the full path if `nmap` is not on PATH. Restart the backend after changing `.env`. `NMAP_ENABLED` defaults to `false`.

## 4. Options the framework accepts

| Option (`context.config`) | Default | Meaning |
|---|---|---|
| `nmap_ports` | from scope | TCP ports to probe. Must be inside the approved scope and within `PENTEST_MAX_PORTS`. |
| `nmap_service_version` | `True` | Light service detection |
| `nmap_timing` | `4` | Nmap timing template |
| `nmap_scripts` | none | NSE scripts. Only `banner` and `ssl-cert` are accepted. Intrusive scripts need FULL impact, and even then the script list is restricted. |
| `nmap_timeout` | `NMAP_TIMEOUT` (120 s) | Time limit per scan |

Any other script name, a wildcard, or a category is refused.

## 5. Use it from Python

Save this as `nmap_check.py` inside the **backend** folder. It scans only the approved host and ports in scope.

```python
import asyncio
from app.ai_engine.pentest import ExecutionEngine, PentestContext, ScopeConfig, default_registry

async def main():
    engine = ExecutionEngine(registry=default_registry())
    context = PentestContext(
        target="http://scanme.nmap.org/",
        scope=ScopeConfig(
            allowed_targets=["scanme.nmap.org"],
            allowed_ports=[22, 80, 443],
            max_impact="proof_of_concept",
        ),
        config={"nmap_ports": [22, 80, 443], "nmap_timing": 2},
    )
    findings = await engine.execute("nmap_scanner", context)
    for finding in findings:
        print(finding.severity.value, finding.title)

asyncio.run(main())
```

Run it from the backend folder.

**Mac (zsh):** `./.venv/bin/python nmap_check.py`

**Windows (PowerShell):** `.\.venv\Scripts\python.exe nmap_check.py`

> Use this public example only within the `scanme.nmap.org` limits above. For your own practice, use the local lab instead (section 6).

## 6. Verify on your computer (local lab, no public site)

This starts a temporary, deliberately vulnerable server on `127.0.0.1`, runs real Nmap against it, and stops it.

**Mac (zsh):**

```zsh
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py nmap
```

**Windows (PowerShell):**

```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py nmap
```

**Expected:** `PASS: real Nmap found the local lab's open port` followed by a port number that changes each run.

## 7. Public result (the only public Nmap capture)

| Field | Value |
|---|---|
| Target | `http://scanme.nmap.org/` |
| Captured | 2026-10-28, 01:53 UTC |
| Ports probed | 22, 80, 443 |
| Open ports | 22, 80, 443 |
| Services | OpenSSH 6.6.1p1, Apache HTTP server (version reported by Nmap) |
| Scripts | None (light service detection only) |

This is a point-in-time observation. Open ports and versions can change. Do not repeat it often.

## 8. Limits

- No automatic handoff of Nmap results to Metasploit or sqlmap.
- The API, AI agent and interface do not start Nmap yet.
- Scanning hostnames without IP restrictions does not pin DNS; use trusted DNS and network controls.
- Mac and Windows install commands were not run on those systems in this project.
