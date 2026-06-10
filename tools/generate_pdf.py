"""
Generate a PDF from a Markdown file using Playwright's headless Chromium.

Usage:
    python tools/generate_pdf.py docs/END_USER_GUIDE.md dist/END_USER_GUIDE.pdf
"""

import sys
import textwrap
from pathlib import Path

import markdown


# ---------------------------------------------------------------------------
# CSS — clean, print-ready professional styling
# ---------------------------------------------------------------------------

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --brand:   #1a56db;
    --brand-dk:#1039a8;
    --text:    #111827;
    --muted:   #6b7280;
    --border:  #e5e7eb;
    --bg-code: #f3f4f6;
    --bg-tbl-h:#eff6ff;
    --success: #065f46;
    --warn-bg: #fffbeb;
    --warn-bd: #fde68a;
    --warn-tx: #92400e;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: var(--text);
    background: #fff;
    padding: 0;
}

/* ── Page layout ── */
.page-wrap {
    max-width: 780px;
    margin: 0 auto;
    padding: 48px 56px;
}

/* ── Cover page ── */
.cover {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    padding: 80px 56px;
    background: linear-gradient(135deg, #1a1f3c 0%, #1a56db 100%);
    color: #fff;
    page-break-after: always;
}
.cover .logo { font-size: 13pt; font-weight: 600; letter-spacing: 0.05em;
               text-transform: uppercase; opacity: .75; margin-bottom: 40px; }
.cover h1 { font-size: 34pt; font-weight: 700; line-height: 1.15;
             margin-bottom: 16px; }
.cover .subtitle { font-size: 13pt; opacity: .80; margin-bottom: 48px;
                   max-width: 520px; line-height: 1.5; }
.cover .meta { font-size: 9.5pt; opacity: .60; }
.cover .pill { display: inline-block; background: rgba(255,255,255,.15);
               border: 1px solid rgba(255,255,255,.3); border-radius: 20px;
               padding: 4px 14px; font-size: 9pt; margin-bottom: 32px; }

/* ── TOC ── */
.toc-page { page-break-after: always; padding-top: 24px; }
.toc-page h2 { font-size: 16pt; font-weight: 700; color: var(--brand);
               border-bottom: 2px solid var(--brand); padding-bottom: 8px;
               margin-bottom: 20px; }
.toc-list { list-style: none; }
.toc-list li { display: flex; align-items: baseline;
               padding: 5px 0; border-bottom: 1px dotted var(--border); }
.toc-list li span.toc-title { flex: 1; font-size: 10pt; }
.toc-list li span.toc-dots { flex: 1; border-bottom: 1px dotted var(--border);
                              margin: 0 8px; min-width: 40px; }
.toc-list li span.toc-pg { font-size: 9pt; color: var(--muted); }
.toc-list .toc-sub { padding-left: 20px; }
.toc-list .toc-sub span.toc-title { font-size: 9.5pt; color: var(--muted); }

/* ── Headings ── */
h1 { font-size: 22pt; font-weight: 700; color: var(--brand); margin: 36px 0 14px;
     padding-bottom: 8px; border-bottom: 2px solid var(--brand); page-break-after: avoid; }
h2 { font-size: 15pt; font-weight: 700; color: var(--text); margin: 28px 0 10px;
     padding-bottom: 6px; border-bottom: 1px solid var(--border); page-break-after: avoid; }
h3 { font-size: 12pt; font-weight: 600; color: var(--brand-dk); margin: 22px 0 8px;
     page-break-after: avoid; }
h4 { font-size: 10.5pt; font-weight: 600; color: var(--text); margin: 18px 0 6px;
     page-break-after: avoid; }

/* ── Body text ── */
p  { margin: 0 0 10px; }
ul, ol { margin: 8px 0 10px 24px; }
li { margin-bottom: 4px; }
li > ul, li > ol { margin-top: 4px; margin-bottom: 4px; }
strong { font-weight: 600; }
em     { font-style: italic; }
hr { border: none; border-top: 1px solid var(--border); margin: 28px 0; }

/* ── Code ── */
code {
    font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
    font-size: 8.8pt;
    background: var(--bg-code);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 5px;
    color: #c7254e;
}
pre {
    background: #1e1e2e;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 10px 0 14px;
    overflow-x: auto;
    page-break-inside: avoid;
}
pre code {
    font-size: 8.5pt;
    background: none;
    border: none;
    color: #cdd6f4;
    padding: 0;
    line-height: 1.6;
}

/* ── Tables ── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 16px;
    font-size: 9.5pt;
    page-break-inside: avoid;
}
thead tr { background: var(--bg-tbl-h); }
th {
    text-align: left;
    padding: 8px 12px;
    font-weight: 600;
    border: 1px solid var(--border);
    color: var(--brand-dk);
    font-size: 9pt;
}
td {
    padding: 7px 12px;
    border: 1px solid var(--border);
    vertical-align: top;
}
tr:nth-child(even) td { background: #f9fafb; }

/* ── Blockquote / callout ── */
blockquote {
    background: var(--warn-bg);
    border-left: 4px solid var(--warn-bd);
    color: var(--warn-tx);
    margin: 10px 0 14px;
    padding: 10px 16px;
    border-radius: 0 6px 6px 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}
blockquote p { margin: 0; }

/* ── Section separator ── */
.part-header {
    background: linear-gradient(90deg, var(--brand) 0%, var(--brand-dk) 100%);
    color: #fff;
    padding: 14px 20px;
    border-radius: 8px;
    margin: 32px 0 20px;
    page-break-after: avoid;
}
.part-header h2 { color: #fff; border: none; margin: 0; padding: 0;
                  font-size: 14pt; }

/* ── Print ── */
@media print {
    body { font-size: 10pt; }
    .cover { min-height: auto; padding: 60px 56px; }
    h1, h2, h3 { page-break-after: avoid; }
    pre, table, blockquote { page-break-inside: avoid; }
    tr { page-break-inside: avoid; }
}
"""


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>

{cover}

<div class="page-wrap">
{body}
</div>

</body>
</html>"""


COVER_TEMPLATE = """<div class="cover">
  <div class="logo">Phoenix SmartAutomation</div>
  <div class="pill">Version 0.1.1</div>
  <h1>End User<br>Guide</h1>
  <p class="subtitle">
    Step-by-step guide for setting up, using, and maintaining<br>
    the Phoenix AI-powered test automation platform.
  </p>
  <p class="meta">
    Generated {date} &nbsp;·&nbsp; For internal use only
  </p>
</div>"""


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def md_to_html_body(md_text: str) -> str:
    """Convert markdown to HTML body content."""
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "codehilite", "toc", "nl2br"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
        },
    )
    html = md.convert(md_text)
    # Wrap Part headings in styled divs
    import re
    html = re.sub(
        r'<h2>(Part \d+[^<]*)</h2>',
        r'<div class="part-header"><h2>\1</h2></div>',
        html,
    )
    return html


def build_html(md_path: Path) -> str:
    from datetime import date as _date

    md_text = md_path.read_text(encoding="utf-8")
    # Strip the H1 title — it goes on the cover instead
    lines = md_text.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0].lstrip("# ").strip()
        md_text = "\n".join(lines[1:]).lstrip()
    else:
        title = md_path.stem.replace("-", " ").replace("_", " ").title()

    body = md_to_html_body(md_text)
    cover = COVER_TEMPLATE.format(date=_date.today().strftime("%B %d, %Y"))

    return HTML_TEMPLATE.format(
        title=title,
        css=CSS,
        cover=cover,
        body=body,
    )


def generate_pdf(md_path: Path, pdf_path: Path) -> None:
    """Render HTML via Playwright's headless Chromium and save as PDF."""
    from playwright.sync_api import sync_playwright

    html = build_html(md_path)
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            margin={"top": "0", "bottom": "16mm", "left": "0", "right": "0"},
            print_background=True,
        )
        browser.close()

    html_path.unlink()
    print(f"PDF saved: {pdf_path}  ({pdf_path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tools/generate_pdf.py <input.md> <output.pdf>")
        sys.exit(1)

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    if not src.exists():
        print(f"Error: {src} not found")
        sys.exit(1)

    dst.parent.mkdir(parents=True, exist_ok=True)
    generate_pdf(src, dst)
