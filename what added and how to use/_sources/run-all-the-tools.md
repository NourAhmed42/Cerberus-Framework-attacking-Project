# Run all the tools at the same time

**Updated: 2 November 2026 (Cairo) · Run recorded: 2 November 2026, 14:14 UTC**

This page explains how to run the three real tools together in one command, what each one tests, and what the saved results mean.

> **Permission first.** Nmap and sqlmap run against public sites, and each site is used only for the tool its operator allows. Metasploit runs only on your own computer (`127.0.0.1`). No public site permits Metasploit testing.

## 1. What the command runs

The command starts **three separate engagements at the same time**. Each engagement runs its own tool.

| Engagement | Tool | Target | Kind of target | Permission in this project |
|---|---|---|---|---|
| 1 | Nmap | `http://scanme.nmap.org/`, ports 22, 80, 443 | Public | Operator permits Nmap only, about 12 scans per day, no exploits or denial of service |
| 2 | sqlmap | `https://sekumart.sekuripy.hr/product.php?id=1`, parameter `id` only | Public practice site | Operator's SQL injection playground; sqlmap only |
| 3 | Metasploit | Temporary listener on `127.0.0.1` (your computer) | Local lab | Only the reviewed port scanner `auxiliary/scanner/portscan/tcp` |

"At the same time" means the three engagements run concurrently. Each engagement still runs its own tool one step at a time. Results are not shared between engagements.

The command never accepts a target from you. The public targets are fixed in the code, and the command refuses to run without the confirmation flag.

## 2. Before you start

1. The project's Python environment exists at `backend/.venv` (see the beginner guide).
2. **Nmap** is installed (`nmap --version` works).
3. **sqlmap** is installed. Note its path (on Windows, the `sqlmap.py` path from the clone).
4. **Metasploit (optional but required for engagement 3):** the real `msfrpcd` daemon is running on `127.0.0.1` port `55553`. See **metasploit how to use.pdf**, sections 2 and 3. If it is not running, engagement 3 reports **FAILED**. It does not report a pass.
5. The daemon password is in your private `backend/.env` or set in the terminal. Do not print it or paste it into chat.

## 3. Commands

Run these from the **project root**, in the VS Code terminal.

### Step 1: set the terminal values (this window only)

**Mac (zsh):**

```zsh
export MSF_RPC_PASSWORD="YOUR_STRONG_PASSWORD"
export MSF_RPC_PORT=55553
export SQLMAP_PATH="$(command -v sqlmap)"
```

**Windows (PowerShell):**

```powershell
$env:MSF_RPC_PASSWORD = "YOUR_STRONG_PASSWORD"
$env:MSF_RPC_PORT = "55553"
$env:SQLMAP_PATH = "$HOME\sqlmap\sqlmap.py"
```

Use the same password as the `-P` value you gave `msfrpcd`. On Mac, `sqlmap` installed with Homebrew is found automatically; the `SQLMAP_PATH` line is optional there. On Windows, change the path if your clone is elsewhere.

### Step 2: run all three at the same time

**Mac (zsh):**

```zsh
./backend/.venv/bin/python scripts/live_tests/run_all_tools.py --confirm-public-tests
```

**Windows (PowerShell):**

```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\run_all_tools.py --confirm-public-tests
```

The run takes about 30 seconds to 2 minutes. Each line starts with the engagement name and shows `CAPTURED` (passed) or `FAILED`.

**Expected:**

```text
Starting three engagements at the same time: Nmap, sqlmap, Metasploit...
nmap: CAPTURED — The real tool completed and the framework returned a recognizable result.
sqlmap: CAPTURED — The real tool completed and the framework returned a recognizable result.
metasploit: CAPTURED — The real Metasploit daemon scanned the local listener and reported the open port.
```

### Step 3: read the results

The run saves:

- `docs/all_tools_result/run-all-tools.json`: each engagement's status, time, target, version, and output excerpt
- `docs/real_results.json` and `docs/real result.pdf`: the latest results, which are rebuilt automatically

Copies from the 2 November run are in **Real results / all tools result**.

### Step 4: after the run

Stop `msfrpcd` with `Ctrl+C` in its own window. Clear the variables by closing the terminal.

## 4. Limits on public tests

- Public scans count toward the operator limits. Nmap is limited to about 12 scans per day, and the command enforces 10 per rolling 24 hours. sqlmap is limited to 6 per 24 hours by the command.
- Do not run this command repeatedly. Run it once when you need a fresh capture.
- The command refuses to run without `--confirm-public-tests`.

## 5. Results from the run on 2 November 2026

| Engagement | Status | Started (UTC) | Finished (UTC) | Result |
|---|---|---|---|---|
| Nmap · `scanme.nmap.org` | **CAPTURED** | 14:14:36 | 14:14:54 | Nmap 7.95. Ports 22 (OpenSSH 6.6.1p1), 80 and 443 are open. |
| sqlmap · SekuMart `id` | **CAPTURED** | 14:14:36 | 14:14:43 | sqlmap 1.10.11.2#dev. Injection found in GET `id`, error-based, back-end MySQL. Detection only; no data was dumped. |
| Metasploit · `127.0.0.1` lab | **CAPTURED** | 14:14:36 | 14:14:36 | Metasploit 6.5.9 (real daemon). Found the open port 39873 that the lab listener was using. |

The three engagements started at the same second, so they ran at the same time.

**Note on the first attempt:** an earlier run of the same command reported Metasploit as failed. The cause was a wrong field name in the new script (`tool` instead of `msf_module`). The Metasploit result was correct, so the script was fixed and run again. The table above shows the corrected run.

## 6. What this shows and what it does not

**Shows:**
- Nmap, sqlmap and the real Metasploit daemon all run, and their outputs are read back into Cerberus.
- Three engagements can run at the same time without interfering with each other.
- Out-of-scope requests are refused before any tool runs (tested separately).

**Does not show:**
- That any public website is vulnerable to anything beyond the specific, documented results.
- Metasploit's behavior on a public site. No public site permits it.
- That Mac or Windows behaves the same way. These steps were run on Linux only.
- A finished product. The API, AI agent and interface do not start these tools yet.

## 7. Troubleshooting

| If you see | Try this |
|---|---|
| `nmap executable is missing` | Install Nmap, then reopen the terminal. |
| `sqlmap executable is missing` | Set `SQLMAP_PATH` for this window (Step 1). |
| `metasploit: FAILED` with a connection error | `msfrpcd` is not running, or the port is not `55553`. Start it and check Step 1. |
| `metasploit: FAILED` with an authentication error | The password in Step 1 does not match the `-P` value of `msfrpcd`. |
| Metasploit times out | Check that `msfrpcd` is running and that the port in Step 1 matches it. Retry once. On the test machine, creating the console took under one second. |
| `public tests require --confirm-public-tests` | Add the flag to the command. |
| Rate limit reached | Wait for the 24-hour window to pass. The command refuses before scanning. |
| PDF could not be rebuilt | The results are saved. Install `backend/requirements-dev.txt` and run `scripts/render_real_results.py`. Do not rescan. |

## 8. Files

| File | What it is |
|---|---|
| `scripts/live_tests/run_all_tools.py` | The runner |
| `backend/tests/unit/test_run_all_tools.py` | Tests that the runner refuses to start without confirmation and uses the approved targets |
| `docs/all_tools_result/run-all-tools.json` | Saved output of the run |
