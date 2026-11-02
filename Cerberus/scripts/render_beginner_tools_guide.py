"""Render the maintained beginner-tool Markdown guide as a printable PDF.

Run with the backend virtual environment after installing requirements-dev.txt.
The source hash in PDF metadata lets a test catch an out-of-date PDF.
"""

import argparse
import hashlib
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "HOW_TO_RUN_THE_TOOLS_AS_BEGINNER.md"
DEFAULT_OUTPUT = ROOT / "docs" / "how to run the tools as beginner.pdf"

CSS = """
@page {
  size: A4;
  margin: 17mm 18mm 19mm;
  @bottom-left {
    content: "CERBERUS  /  BEGINNER TOOL GUIDE";
    color: #73849b;
    font: 7.2pt "DejaVu Sans", sans-serif;
  }
  @bottom-right {
    content: "Page " counter(page) " / " counter(pages);
    color: #73849b;
    font: 7.2pt "DejaVu Sans", sans-serif;
  }
}
html { color: #26364b; font: 9.25pt/1.42 "DejaVu Sans", sans-serif; }
body { margin: 0; }
h1, h2, h3 { color: #102b49; line-height: 1.19; break-after: avoid; }
h1 { font-size: 21pt; margin: 0 0 4mm; letter-spacing: -0.35pt; }
h2 { font-size: 14pt; margin: 5.3mm 0 2.2mm; }
h3 { font-size: 10.5pt; margin: 4.5mm 0 1.8mm; }
p { margin: 0 0 2.8mm; }
a { color: #007d88; text-decoration: none; }
strong { color: #132f4c; }
ul, ol { margin: 1.5mm 0 3mm; padding-left: 5mm; }
li { margin: 0 0 1.8mm; }
blockquote {
  margin: 4mm 0;
  padding: 3.5mm 4mm;
  border-left: 3pt solid #0a9a9b;
  background: #eaf7f6;
  border-radius: 1.5mm;
}
blockquote p:last-child { margin-bottom: 0; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0 4mm; font-size: 8.1pt; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #143450; color: white; text-align: left; font-weight: 700; }
th, td { padding: 2mm 2.3mm; vertical-align: top; border: 0.3pt solid #d4dfea; }
tbody tr:nth-child(even) { background: #f2f7fa; }
td p:last-child { margin: 0; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.0pt; color: #075c6a; overflow-wrap: anywhere; }
pre {
  margin: 1.5mm 0 2.7mm;
  padding: 2.5mm 3mm;
  background: #10283e;
  border-radius: 1.5mm;
  color: #f2f8fc;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  break-inside: avoid;
}
pre code { font-size: 7.7pt; line-height: 1.35; color: #f2f8fc; }
.page-break { break-before: page; }
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        import markdown  # type: ignore[import-untyped]
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        parser.exit(
            1,
            f"PDF dependencies unavailable: {exc}\n"
            "Install backend/requirements-dev.txt and WeasyPrint's native libraries.\n",
        )

    source_bytes = SOURCE.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    rendered = markdown.markdown(
        source_bytes.decode("utf-8"), extensions=["fenced_code", "tables", "sane_lists"]
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>How to run the tools as a beginner</title>
<meta name="author" content="Cerberus Framework">
<meta name="keywords" content="source-sha256:{html.escape(digest)}">
<style>{CSS}</style>
</head>
<body>{rendered}</body>
</html>
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the metadata as plain PDF bytes so the no-extra-dependency test can
    # compare its source hash without requiring a PDF parser in the test suite.
    HTML(string=document, base_url=str(ROOT)).write_pdf(args.output, uncompressed_pdf=True)
    print(f"Wrote {args.output}")
    print(f"Guide source SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
