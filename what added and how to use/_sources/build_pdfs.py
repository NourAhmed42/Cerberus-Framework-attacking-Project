"""Build the tool PDFs in this folder from the Markdown sources in _sources/.

Run from the Cerberus project root with the backend virtual environment (Markdown and WeasyPrint are in requirements-dev.txt):
  Mac / zsh:        ./backend/.venv/bin/python "what added and how to use/_sources/build_pdfs.py"
  Windows / PowerShell: .\\backend\\.venv\\Scripts\\python.exe "what added and how to use\\_sources\\build_pdfs.py"
"""

import html
import importlib.util
from pathlib import Path

import markdown
from weasyprint import HTML

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
# Run from the Cerberus project root (the folder that contains backend/ and scripts/).
REPO = Path.cwd()
if not (REPO / "scripts" / "render_beginner_tools_guide.py").exists():
    raise SystemExit("Run this from the Cerberus project root.")

# Reuse the exact page styling of the maintained beginner guide.
_spec = importlib.util.spec_from_file_location(
    "beginner_renderer", REPO / "scripts" / "render_beginner_tools_guide.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
BASE_CSS = _mod.CSS

# (source markdown, output PDF relative to the folder, footer label)
DOCS = [
    ("attack-framework.md", "Attack framework/frameworks added.pdf", "CERBERUS  /  ATTACK FRAMEWORK"),
    ("metasploit-added-files.md", "Metasploit/metasploit added files.pdf", "CERBERUS  /  METASPLOIT"),
    ("metasploit-how-to-use.md", "Metasploit/metasploit how to use.pdf", "CERBERUS  /  METASPLOIT"),
    ("metasploit-steps-to-check.md", "Metasploit/metasploit steps to check up.pdf", "CERBERUS  /  METASPLOIT"),
    ("nmap.md", "Nmap/nmap integration and how to use (2026-11-02).pdf", "CERBERUS  /  NMAP"),
    ("sqlmap.md", "sqlmap/sqlmap integration and how to use (2026-11-02).pdf", "CERBERUS  /  SQLMAP"),
    ("vscode-terminal.md", "VS Code terminal/vscode terminal verification steps.pdf", "CERBERUS  /  VS CODE TERMINAL"),
    ("run-all-the-tools.md", "Real results/all tools result/run all the tools.pdf", "CERBERUS  /  RUN ALL THE TOOLS"),
    ("vscode-tools-test.md", "VS Code terminal/vscode tools test.pdf", "CERBERUS  /  VS CODE TOOLS TEST"),
    ("output-only.md", "Real results/output only.pdf", "CERBERUS  /  OUTPUT ONLY"),
    ("shawky-ar.md", "Shawky عمل ايه.pdf", "CERBERUS  /  SHAWKY (AR)"),
    ("beginner-guide-ar.md", "Beginner guide/how to run the tools as beginner (arabic).pdf", "CERBERUS  /  BEGINNER GUIDE (AR)"),
    ("vscode-tools-test-python-ar.md", "VS Code terminal/vscode tools test - python commands (arabic).pdf", "CERBERUS  /  PYTHON COMMANDS (AR)"),
]


def render(source: Path, output: Path, footer: str) -> None:
    body = markdown.markdown(
        source.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"]
    )
    css = BASE_CSS.replace("CERBERUS  /  BEGINNER TOOL GUIDE", footer)
    if source.name.endswith("-ar.md"):
        # Arabic: right-to-left text, but commands and code stay left-to-right.
        css += (
            "body{direction:rtl;text-align:right;}"
            "pre,code,kbd{direction:ltr;text-align:left;unicode-bidi:embed;}"
            "table{direction:rtl;}"
        )
        body = f'<div dir="rtl" lang="ar">{body}</div>'
    document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(footer)}</title><style>{css}</style></head>"
        f"<body>{body}</body></html>"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=document, base_url=str(source.parent)).write_pdf(str(output))
    print("Wrote", output)


def main() -> None:
    for src, rel, footer in DOCS:
        render(HERE / src, FOLDER / rel, footer)


if __name__ == "__main__":
    main()
