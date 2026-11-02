# Metasploit: added and changed files

**Updated: 2 November 2026 (Cairo) · Commits `bf543af` (code) and `59dc2b7` (results)**

This page lists the files that were added or changed for the Metasploit integration. Paths are relative to the project root `Cerberus/`.

## 1. Adapter: how the backend talks to `msfrpcd`

| File | Role |
|---|---|
| `backend/app/ai_engine/pentest/tools/metasploit_adapter.py` | **Replaced in this update.** It was XML-RPC, which does not work with real `msfrpcd`. It now uses MessagePack over HTTP, the protocol `msfrpcd` uses. It keeps the RPC token local, uses bounded timeouts, and refuses console commands with newline or command injection. |

## 2. Scanner module: what can run

| File | Role |
|---|---|
| `backend/app/ai_engine/pentest/modules/tools/metasploit_scanner.py` | **Changed.** Runs only `auxiliary/scanner/portscan/tcp`. Parses IPv4 and IPv6 results (for example `[::1]`). Checks scope. Limits ports to `PENTEST_MAX_PORTS`. |

## 3. Safety and scope files

| File | Role |
|---|---|
| `backend/app/ai_engine/pentest/core/scope_match.py` | **New.** Structured scope matching: host, scheme, path and port. Replaces substring matching. |
| `backend/app/ai_engine/pentest/core/safety.py` | **Changed.** Refuses any module when `testing_window` is set. Adds the Metasploit and Nmap restrictions. |
| `backend/app/ai_engine/pentest/core/context.py` | **Changed.** Scope and context checks for the new rules. |

## 4. Settings

| File | Change |
|---|---|
| `backend/app/core/config.py` | `MSF_RPC_TIMEOUT` default is **60 seconds**. The first console is usually quick; it took 0.48 seconds on the test machine. |
| `backend/.env.example` | Example values for `MSF_ENABLED`, `MSF_RPC_HOST`, `MSF_RPC_PORT`, `MSF_RPC_PASSWORD`, `MSF_RPC_SSL`, `MSF_RPC_TIMEOUT=60`. The password is a placeholder. |
| `backend/requirements.txt` | Adds `msgpack==1.1.2` |

Your private `backend/.env` is not changed by this update. If it already sets `MSF_RPC_TIMEOUT=10`, change it to `60`.

## 5. Tests

| File | What it checks |
|---|---|
| `backend/tests/unit/test_pentest_tools.py` | Adapter and scanner with a protocol-compatible test double (`FakeMsfrpcd`). The double does not run Metasploit. |
| `backend/tests/unit/test_pentest_framework.py` | Framework engine and scheduler tests (changed) |
| `backend/tests/unit/test_pentest_safety_regressions.py` | **New.** Safety regressions: refused modules, refused options, scope and IPv6 cases |
| `backend/tests/unit/test_public_tool_results.py` | Tests for the public-capture script (changed) |

## 6. Scripts and documents

| File | Role |
|---|---|
| `scripts/live_tests/beginner_tools_lab.py` | Beginner lab. Its `metasploit` mode is **simulated**, not a real daemon. |
| `scripts/live_tests/public_tool_results.py` | Refreshes public Nmap and sqlmap captures. It **does not** run Metasploit. |
| `scripts/live_tests/sqlmap_framework_smoke.py` | Local smoke test. Its Metasploit endpoint is a **fake** MessagePack service. |
| `docs/real_results.json` and `docs/REAL_RESULTS.md` | Saved results. Metasploit's real loopback runs are listed separately from public results. |
| `scripts/render_real_results.py` | Rebuilds the real-results PDF |

## 7. What is not in the repository

- The Metasploit program itself (about 1 GB). It is optional. The beginner lab works without it.
- Temporary loopback test scripts from the real-daemon check. They were removed after the test, so the real-daemon check must be run again by hand (see the steps document).
