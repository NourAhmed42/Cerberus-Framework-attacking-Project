# VS Code tools test: run each Cerberus tool separately, all together, or at the same time

**Updated: 2 November 2026 (Cairo) · MacBook (zsh) and Windows (PowerShell)**

This page is for the team demo. It shows three ways to run the tools from the VS Code terminal:

1. **Separately:** one tool at a time.
2. **All together, one after another:** one plan, one tool after the other.
3. **All together, at the same time:** separate engagements running concurrently.

Each run is labelled, so you can show clearly what was real, simulated, or public.

> **Rules:** run the commands from the project root. The default local runs use a temporary target on your own computer, so no website is contacted. Public runs contact only the two approved targets: `scanme.nmap.org` (Nmap only) and SekuMart's product `id` parameter (sqlmap only). Public runs use daily limits and write results to `docs/real_results.json`, so run them only when the team asks for a fresh capture.

## 1. The labels

| Label | Meaning |
|---|---|
| **LOCAL LAB** | A temporary target that the command starts on `127.0.0.1` and stops at the end. |
| **SIMULATED** | The Metasploit step in the local lab uses a fake server, so it is not real Metasploit. |
| **PUBLIC** | A real public website. Used only with `--confirm-public-tests`. |
| **LOCAL REAL** | The real Metasploit daemon on your computer. Used only in the all-together public run. |
| **TESTS** | Automated tests for the tools. No database needed. |

## 2. Where the data goes

You do not paste data into files. Set these optional values in the same terminal window before running a command.

| Setting | What it is | Needed for |
|---|---|---|
| `SQLMAP_PATH` | Full path to `sqlmap.py`, if sqlmap is not on the PATH | sqlmap, all together, and the demo |
| `MSF_RPC_PASSWORD` | Password of the `msfrpcd` daemon | Real Metasploit (section 3C, public run) |
| `MSF_RPC_PORT` | Port of `msfrpcd` (default `55553`) | Real Metasploit |

The local runs do not save anything to the application database.

## 3. Three ways to run the tools

### 3A. Separately: one tool at a time

| Tool | Where | Mac (zsh) | Windows (PowerShell) |
|---|---|---|---|
| Nmap | LOCAL LAB | `./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py nmap` | `.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py nmap` |
| sqlmap | LOCAL LAB | `./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py sqlmap` | `.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py sqlmap` |
| Metasploit | LOCAL LAB, SIMULATED | `./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py metasploit` | `.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py metasploit` |
| Nmap | PUBLIC (`scanme.nmap.org`) | `./backend/.venv/bin/python scripts/live_tests/public_tool_results.py nmap --confirm-public-tests` | `.\backend\.venv\Scripts\python.exe scripts\live_tests\public_tool_results.py nmap --confirm-public-tests` |
| sqlmap | PUBLIC (SekuMart `id`) | `./backend/.venv/bin/python scripts/live_tests/public_tool_results.py sqlmap --confirm-public-tests` | `.\backend\.venv\Scripts\python.exe scripts\live_tests\public_tool_results.py sqlmap --confirm-public-tests` |

**Metasploit on its own with the real daemon is not a separate command.** The real daemon runs only in the all-together public run (3C, second command).

sqlmap commands need `SQLMAP_PATH` (Section 2) if sqlmap is not on the PATH.

### 3B. All together, one after another (one plan)

The tools run one after another against the same local lab. This shows the plan order: Nmap, then sqlmap, then Metasploit.

**Mac (zsh):**

```zsh
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py all
```

**Windows (PowerShell):**

```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py all
```

Metasploit in this run is **SIMULATED**.

### 3C. All together, at the same time (concurrent)

Three separate engagements start at the same time.

**Local lab (Metasploit SIMULATED):**

Mac (zsh):

```zsh
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py parallel
```

Windows (PowerShell):

```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py parallel
```

**Public sites and real Metasploit (run once, after `msfrpcd` is running):**

Mac (zsh):

```zsh
export MSF_RPC_PASSWORD="YOUR_STRONG_PASSWORD"
./backend/.venv/bin/python scripts/live_tests/run_all_tools.py --confirm-public-tests
```

Windows (PowerShell):

```powershell
$env:MSF_RPC_PASSWORD = "YOUR_STRONG_PASSWORD"
.\backend\.venv\Scripts\python.exe scripts\live_tests\run_all_tools.py --confirm-public-tests
```

This run uses Nmap on `scanme.nmap.org`, sqlmap on SekuMart's `id` parameter, and real Metasploit on a temporary listener on your computer.

## 4. The demo command (all steps, one command)

The demo runs the local checks and the automated tests. It adds the public run only with `--include-public`.

**Mac (zsh):**

```zsh
export SQLMAP_PATH="$(command -v sqlmap)"
./backend/.venv/bin/python scripts/demo/run_everything.py
```

Or the wrapper: `zsh scripts/demo/run-vscode-tools-test.sh`

**Windows (PowerShell):**

```powershell
$env:SQLMAP_PATH = "$HOME\sqlmap\sqlmap.py"
.\backend\.venv\Scripts\python.exe scripts\demo\run_everything.py
```

Or the wrapper: `powershell -ExecutionPolicy Bypass -File scripts\demo\run-vscode-tools-test.ps1`

Add `--include-public` to either command to include the public run. Set `MSF_RPC_PASSWORD` first.

## 5. What a good demo run looks like

This is the summary from the test run on 2 November 2026 (Linux, local-only steps):

```text
  Step                                    Label                       Status     Time  Note
  Step 1 - Nmap, sqlmap, Metasploit (lab) LOCAL LAB; Metasploit SIMULATED PASS       3.5s  exit 0
  Step 2 - Automated tests                TESTS                       PASS      15.4s  exit 0
  Step 3 - Public sites + real Metasploit PUBLIC + LOCAL REAL         SKIP       0.0s  not run; add --include-public
Passed: every step that ran. 1 step(s) were SKIPPED (reasons above).
```

**Your run may differ.** Step 3 shows SKIP unless you add `--include-public`. Step 1 shows SKIP if Nmap or sqlmap is missing. The Step 0 checklist tells you which item is MISSING.

## 6. Troubleshooting

| You see | What to do |
|---|---|
| `[MISSING] sqlmap` or sqlmap not found | Set `SQLMAP_PATH` in the same terminal window (Section 2). |
| `[MISSING] Nmap` | Install Nmap from nmap.org/download, then open a new terminal. |
| `[MISSING] Metasploit daemon` | Start `msfrpcd` and set `MSF_RPC_PASSWORD`. Only the public all-together run needs it. |
| `Not the project .venv` | Use the `.venv` command shown in the table, not a global Python. |
| A test or step shows FAIL | Copy the first line marked FAILED and ask for help. Do not change the tests. |
| Public run says the daily limit is reached | Wait for the 24-hour window to pass. The runner stops before it scans. |
| Public run asks for `--confirm-public-tests` | Add the flag. The public runs refuse to start without it. |

## 7. What this shows and what it does not

**Shows:** each tool starts, reads its real output, and reports it. The labels show the difference between real, simulated, and public results.

**Does not show:** that the tools are connected to the web app, the API or the AI agent. Those connections are not part of this demo. The local runs do not save results to the database.

## 8. Appendix: what each command does

Short explanation of every command in this guide. Mac (zsh) and Windows (PowerShell) versions do the same thing.

### 8.1 Shell commands

| Command | What it does |
|---|---|
| `cd ~/Cerberus` (Mac) / `cd $HOME\Cerberus` (Windows) | Moves the terminal into the project folder. All other commands assume you are here. |
| `export SQLMAP_PATH="$(command -v sqlmap)"` (Mac) | Finds where `sqlmap` is installed and saves that path for this terminal window only. |
| `$env:SQLMAP_PATH = "$HOME\sqlmap\sqlmap.py"` (Windows) | Sets the sqlmap path for this PowerShell window only. Change the path if your copy is elsewhere. |
| `export MSF_RPC_PASSWORD="..."` / `$env:MSF_RPC_PASSWORD = "..."` | Gives the scripts the password of the Metasploit daemon for this window only. Replace the placeholder with your own password. Never paste it into chat. |
| `zsh scripts/demo/run-vscode-tools-test.sh` | Runs the demo wrapper on Mac. The wrapper finds sqlmap if it is on the PATH, then runs the demo. |
| `powershell -ExecutionPolicy Bypass -File scripts\demo\run-vscode-tools-test.ps1` | Runs the demo wrapper on Windows. The `Bypass` setting allows this one script to run without changing your system settings. |

### 8.2 Python commands

`./backend/.venv/bin/python` (Mac) and `.\backend\.venv\Scripts\python.exe` (Windows) both start the Python that belongs to the project. Using it means the project's installed packages are used, not a global Python.

| Command | What it does |
|---|---|
| `beginner_tools_lab.py nmap` | Starts a temporary vulnerable target on `127.0.0.1`, runs real Nmap against it, then stops the target. |
| `beginner_tools_lab.py sqlmap` | Same temporary target. Runs real sqlmap against its `id` parameter to detect the SQL injection. |
| `beginner_tools_lab.py metasploit` | Same temporary target. Uses a fake (SIMULATED) Metasploit response. It does not contact the real daemon. |
| `beginner_tools_lab.py all` | Runs Nmap, sqlmap and the simulated Metasploit one after another against the temporary target. |
| `beginner_tools_lab.py parallel` | Runs the same three tools at the same time, each as a separate engagement. |
| `public_tool_results.py nmap --confirm-public-tests` | Runs Nmap on `scanme.nmap.org` only. Saves the result to `docs/real_results.json`. Counts toward the daily Nmap limit. |
| `public_tool_results.py sqlmap --confirm-public-tests` | Runs sqlmap on SekuMart's `id` parameter only. Saves the result to `docs/real_results.json`. Counts toward the daily sqlmap limit. |
| `run_all_tools.py --confirm-public-tests` | Runs Nmap and sqlmap on their public sites, and the real Metasploit daemon on a temporary listener on your computer, all at the same time. Needs `msfrpcd` running. |
| `run_everything.py` | Runs the demo: checks what is installed, runs the local lab (Step 1), runs the 228 automated tests (Step 2), and prints a summary. |
| `run_everything.py --include-public` | Same as above, plus Step 3: the public sites and the real Metasploit daemon. |
| `-m pytest --noconftest -q -k "not persist" ...` | Runs the automated tests in the listed files. `--noconftest` skips the database setup, and `-k "not persist"` skips the tests that need a database. |

### 8.3 Options

| Option | What it does |
|---|---|
| `--confirm-public-tests` | Required for every public run. It confirms you have checked the site operators' rules and limits. Without it, the script refuses to start. |
| `--include-public` | Makes the demo also run the public step. Without it, Step 3 is skipped. |
| `nmap`, `sqlmap`, `metasploit`, `all`, `parallel` | The mode for the local lab. Chooses which tool or tools run. |

**Safety rule:** the commands never accept a target from you. The public targets are fixed in the code, and the only site used for Nmap is `scanme.nmap.org`.
