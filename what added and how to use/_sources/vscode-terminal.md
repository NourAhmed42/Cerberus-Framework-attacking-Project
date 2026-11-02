# Cerberus tools in the VS Code terminal: verification steps

**Updated: 2 November 2026 (Cairo) · MacBook (zsh) and Windows (PowerShell)**

This guide runs the tool checks from the VS Code terminal. Open the terminal with **Terminal → New Terminal** (on a Mac you can also press `` Ctrl+` `` or `Cmd+J`).

> **Rules for every step:** run commands from the project root unless a step says **backend**. Test only systems you are allowed to test. No public site is used in these steps.

## 0. Where data is stored

| Item | Stored on disk? | Where | How to remove |
|---|---|---|---|
| Lab results printed in the terminal | No | Terminal window only | Close the terminal |
| Temporary lab servers and sqlmap files | Briefly | Temporary folders | Removed automatically on normal finish. A forced stop (Ctrl+C twice) can leave files behind. |
| Python environment | Yes | `backend/.venv` | Keep it. Delete only if you want to rebuild it. |
| Test cache | Yes | `backend/.pytest_cache` | `rm -rf backend/.pytest_cache` (Mac) or `Remove-Item -Recurse backend\.pytest_cache` (Windows) |
| Real Metasploit program (optional) | Only if installed | Its install folder, and logs in your user profile (for example `~/.msf4` on a Mac) | Use the uninstaller from Rapid7 |
| Private settings | Yes | `backend/.env` | Keep it private. Do not commit or share it. |

The lab scripts do **not** save results to the application database.

## 1. Set up the Python environment (once)

**Mac (zsh):**

```zsh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cd ..
```

**Windows (PowerShell):**

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Set-Location ..
```

If `backend/.venv` already exists, do not delete it. Use it as it is.

**Expected:** pip completes without errors.

## 2. Run the framework unit tests (no database, no external program)

**Mac (zsh):**

```zsh
cd backend
./.venv/bin/python -m pytest --noconftest -q -k "not persist" tests/unit/test_pentest_tools.py tests/unit/test_pentest_framework.py tests/unit/test_pentest_safety_regressions.py tests/unit/test_sqlmap_integration.py tests/unit/test_public_tool_results.py
cd ..
```

**Windows (PowerShell):**

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest --noconftest -q -k "not persist" tests/unit/test_pentest_tools.py tests/unit/test_pentest_framework.py tests/unit/test_pentest_safety_regressions.py tests/unit/test_sqlmap_integration.py tests/unit/test_public_tool_results.py
Set-Location ..
```

**Expected:** `228 passed, 2 deselected`. This is the result recorded on Linux; if your count differs, note the first failing test.

## 3. Run the beginner lab for each tool

These run on a temporary local lab only. Install Nmap and sqlmap first if you want their real checks (see the beginner guide).

**Mac (zsh):**

```zsh
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py nmap
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py sqlmap
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py metasploit
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py all
```

**Windows (PowerShell):**

```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py nmap
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py sqlmap
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py metasploit
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py all
```

**Expected:**

- `nmap` prints `PASS: real Nmap found the local lab's open port`.
- `sqlmap` prints `PASS: real sqlmap detected the lab's intentional SQL injection in id.`
- `metasploit` prints `SIMULATED` and a `PASS` for the fake response. It does **not** test real Metasploit.
- `all` runs Nmap, then sqlmap, then the simulated Metasploit step, one after another.

A `FAILED` line, a missing-tool message, or an `ERROR` is **not** a pass. Read the message and follow the troubleshooting table in the beginner guide.

## 4. Test the real Metasploit daemon (optional)

This needs the Metasploit program and `msfrpcd` running. The full steps are in **metasploit steps to check up.pdf**. Do not run it against any public site.

## 5. Public websites: not run from the terminal

Public captures are refreshed only by the script below. It refuses to run without the confirmation flag, and it only uses the allowed targets:

- `scanme.nmap.org` for Nmap only (about 12 scans per day)
- SekuMart's product `id` parameter for sqlmap only

**Mac (zsh):**

```zsh
./backend/.venv/bin/python scripts/live_tests/public_tool_results.py nmap --confirm-public-tests
```

**Windows (PowerShell):**

```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\public_tool_results.py nmap --confirm-public-tests
```

Run it only when you need a fresh capture. Do not use these sites for any other tool or purpose. Metasploit has no public target.

## 6. Clean up after testing

1. Stop any running daemon or server with `Ctrl+C` in its own window.
2. Remove temporary files if a run was stopped by force: check the system temp folder for `sqlmap` or `cerberus` leftovers and delete only those you recognise.
3. Keep `backend/.env` private.

## 7. Troubleshooting

| If you see | Try this |
|---|---|
| `No such file` for the Python path | Open the project root in VS Code. Check that `backend/.venv` exists. |
| `Missing Python package` | Run the install step (section 1) with the project's `.venv` Python. |
| `nmap` or `sqlmap` not found | Reopen the terminal. Set `NMAP_PATH` or `SQLMAP_PATH` for this terminal (see the beginner guide). |
| `SECRET_KEY` too short | Fix the private `backend/.env`. Do not paste the key into chat. |
| `Activate.ps1` cannot run (Windows) | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again. |

## 8. Current limits

- The Mac and Windows commands have not been run on those systems in this project. They were checked on Linux.
- The API, AI agent and interface do not start these tools yet.
- Metasploit has no public test result.
