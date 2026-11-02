# What was added and how to use

**Updated: 2 November 2026 (Cairo)**

Each tool or framework has its own folder. When a new tool is added, it gets its own folder with the same kind of files.

## Folder index

| Folder | What is inside | Status |
|---|---|---|
| `Attack framework/` | How the framework and its 9 modules connect to the 3 tools, safety rules, public-target policy, verification record | Updated 2 Nov 2026 |
| `Metasploit/` | Added files, how to use (real daemon and simulated lab), steps to check it works | Updated 2 Nov 2026 |
| `Nmap/` | Install, settings, Python example, local lab check, the public `scanme.nmap.org` capture | Updated 2 Nov 2026 |
| `sqlmap/` | Install, settings, Python example, local checks, the public SekuMart capture | Updated 2 Nov 2026 |
| `Beginner guide/` | Beginner guide for all tools, Windows PowerShell and Mac zsh commands (`how to run the tools as beginner.pdf`), and the Arabic version (`how to run the tools as beginner (arabic).pdf`) | Updated 2 Nov 2026 |
| `Real results/` | Real captured results. Public, local and simulated results are labelled separately. | Copy of the current repo PDF |
| `Real results/output only.pdf` | Output only: what each tool printed in the latest run on the allowed sites and on the local lab, plus test results. | Updated 2 Nov 2026 |
| `Real results/all tools result/` | **Run all the tools**: the command and explanation (`run all the tools.pdf`), plus the saved output of the 2 Nov 2026 run (JSON and log). Nmap, sqlmap and Metasploit ran at the same time. | Updated 2 Nov 2026 |
| `VS Code terminal/` | Terminal steps for Mac and Windows (`vscode terminal verification steps.pdf`); the team demo with its appendix of command explanations (`vscode tools test.pdf`); and the Arabic explanation of the Python commands (`vscode tools test - python commands (arabic).pdf`) | Updated 2 Nov 2026 |
| `Shawky عمل ايه.pdf` | Summary of everything built so far, with why each part exists and step-by-step commands (Arabic). Updated after every change. | Updated 2 Nov 2026 |
| `_sources/` | Markdown sources for the PDFs above and the build script `build_pdfs.py` | Edit the `.md` files, then rebuild |

## Rules for every new tool

1. Create a folder named after the tool (for example `Nmap/`, `Metasploit/`, `sqlmap/`).
2. Put these files in it:
   - **Added files**: the files added or changed for the tool, with commit references.
   - **How to use**: install and run steps, with **Windows PowerShell** and **Mac zsh** commands.
   - **Steps to check it works**: commands with the expected result of each step.
3. Update `Attack framework/` and `Beginner guide/` when a tool is added.
4. Update `Real results/` only when there is a new genuine result. Label each one **public**, **local lab** or **simulated**.
5. Keep the Markdown source in `_sources/`, rebuild the PDFs, and check the layout.
6. Tell the user when this is done.

## Rebuilding the PDFs

Run these from the Cerberus project root (the folder that contains `backend` and `scripts`):

**Mac (zsh):**

```zsh
./backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
./backend/.venv/bin/python "what added and how to use/_sources/build_pdfs.py"
```

**Windows (PowerShell):**

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\backend\.venv\Scripts\python.exe "what added and how to use\_sources\build_pdfs.py"
```

The Beginner guide and Real results PDFs are built from the repo by their own scripts (`scripts/render_beginner_tools_guide.py` and `scripts/render_real_results.py`), not by this script.

## Test status (2 Nov 2026)

- Pentest unit tests without a database: **228 passed**, 2 deselected.
- Full backend suite (2 Nov 2026, rebuilt environment): **385 passed**. A test-isolation fix in `backend/tests/conftest.py` clears only the `abuse:*` Redis counters between tests.
- Nmap and sqlmap: real tools checked on a local lab. Public captures are from 28 Oct 2026.
- Metasploit: real `msfrpcd` 6.5.9 re-verified on loopback on 2 Nov 2026 (IPv4 and IPv6). No public site permits Metasploit testing.
- Mac and Windows commands have not been run on those systems in this project.

## Known gap in this folder

Five older PDFs were overwritten during this update. Their names were the same as the new versions, so the old content is not on disk and is not in git:

- `Metasploit/metasploit added files.pdf`
- `Metasploit/metasploit how to use.pdf`
- `Metasploit/metasploit steps to check up.pdf`
- `Attack framework/frameworks added.pdf`
- `VS Code terminal/vscode terminal verification steps.pdf`

