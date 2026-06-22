"""Convert END_USER_GUIDE.md to a professional PDF using Playwright Chromium."""

import re
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

MD_FILE = Path(__file__).parent / "END_USER_GUIDE.md"
HTML_FILE = Path(__file__).parent / "END_USER_GUIDE.html"
PDF_FILE = Path(__file__).parent / "Phoenix_SmartAutomation_v0.1.4_User_Guide.pdf"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --brand:      #FF6B35;
    --brand-dark: #C94E1A;
    --text:       #1A1A2E;
    --text-muted: #555570;
    --border:     #E2E8F0;
    --bg-code:    #1E1E2E;
    --bg-inline:  #F1F5F9;
    --bg-note:    #FFF7F3;
    --bg-page:    #FFFFFF;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 10.5pt;
    line-height: 1.7;
    color: var(--text);
    background: var(--bg-page);
    padding: 0 48px;
}

/* ── Cover page ─────────────────────────────────────── */
.cover {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    min-height: 96vh;
    padding: 60px 0 40px;
    border-bottom: 4px solid var(--brand);
    margin-bottom: 48px;
    page-break-after: always;
}
.cover-logo {
    font-size: 13pt;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--brand);
    margin-bottom: 32px;
}
.cover h1 {
    font-size: 32pt;
    font-weight: 700;
    line-height: 1.15;
    color: var(--text);
    margin-bottom: 16px;
    border: none;
    padding: 0;
}
.cover h1 span { color: var(--brand); }
.cover-subtitle {
    font-size: 13pt;
    color: var(--text-muted);
    font-weight: 400;
    margin-bottom: 48px;
}
.cover-meta {
    font-size: 9.5pt;
    color: var(--text-muted);
    line-height: 2;
}
.cover-version {
    display: inline-block;
    background: var(--brand);
    color: white;
    font-size: 9.5pt;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 4px;
    margin-left: 8px;
    vertical-align: middle;
}

/* ── Headings ────────────────────────────────────────── */
h1, h2, h3, h4 {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    color: var(--text);
    margin-top: 1.6em;
    margin-bottom: 0.5em;
}

h1 {
    font-size: 18pt;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--brand);
    color: var(--brand-dark);
}

h2 {
    font-size: 13pt;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border);
}

h3 { font-size: 11pt; color: var(--brand-dark); }
h4 { font-size: 10.5pt; font-weight: 600; }

/* ── Body text ──────────────────────────────────────── */
p { margin-bottom: 0.8em; }

a { color: var(--brand); text-decoration: none; }

strong { font-weight: 600; }

em { font-style: italic; color: var(--text-muted); }

/* ── Code ───────────────────────────────────────────── */
code {
    font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
    font-size: 9pt;
    background: var(--bg-inline);
    color: #C94E1A;
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid var(--border);
}

pre {
    background: var(--bg-code);
    border-radius: 6px;
    padding: 16px 20px;
    margin: 12px 0 16px;
    overflow: hidden;
    page-break-inside: avoid;
    border-left: 3px solid var(--brand);
}

pre code {
    font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
    font-size: 8.5pt;
    background: none;
    color: #CDD6F4;
    padding: 0;
    border: none;
    border-radius: 0;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.6;
}

/* PowerShell keyword highlights (simple regex will be applied in Python) */
.kw  { color: #CBA6F7; }   /* keywords  */
.str { color: #A6E3A1; }   /* strings   */
.cm  { color: #6C7086; font-style: italic; } /* comments */
.fn  { color: #89B4FA; }   /* functions */
.var { color: #F38BA8; }   /* variables */

/* ── Tables ─────────────────────────────────────────── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 20px;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

th {
    background: var(--text);
    color: white;
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.03em;
}

td {
    padding: 7px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
}

tr:nth-child(even) td { background: #F8FAFC; }

/* ── Blockquotes / notes ─────────────────────────────── */
blockquote {
    background: var(--bg-note);
    border-left: 4px solid var(--brand);
    margin: 12px 0;
    padding: 10px 16px;
    border-radius: 0 4px 4px 0;
    color: var(--text-muted);
    font-size: 9.5pt;
    page-break-inside: avoid;
}

blockquote p { margin: 0; }

/* ── Lists ──────────────────────────────────────────── */
ul, ol {
    margin: 6px 0 12px 24px;
}
li { margin-bottom: 4px; }

/* ── Horizontal rule ─────────────────────────────────── */
hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 20px 0;
}

/* ── Page breaks ─────────────────────────────────────── */
h1 { page-break-before: always; }
h1:first-of-type { page-break-before: avoid; }

/* ── Print / PDF page setup ──────────────────────────── */
@page {
    size: A4;
    margin: 20mm 16mm 22mm 16mm;

    @bottom-center {
        font-family: 'Inter', sans-serif;
        font-size: 8pt;
        color: #9CA3AF;
        content: "Phoenix SmartAutomation  ·  End User Guide  ·  v0.1.4  ·  Page " counter(page) " of " counter(pages);
    }
}
"""

def highlight_shell(code: str) -> str:
    """Very light syntax colouring for shell / PowerShell blocks."""
    lines = []
    for line in code.split("\n"):
        if line.strip().startswith("#"):
            lines.append(f'<span class="cm">{line}</span>')
            continue
        line = re.sub(r'(\$env:\w+|\$\w+)', r'<span class="var">\1</span>', line)
        line = re.sub(r'("(?:[^"\\]|\\.)*")', r'<span class="str">\1</span>', line)
        line = re.sub(
            r'\b(pip|python|phoenix|playwright|curl|netstat|Get-Content|ForEach-Object|'
            r'System\.Environment|SetEnvironmentVariable|mkdir|cd|echo|notepad)\b',
            r'<span class="fn">\1</span>', line
        )
        line = re.sub(
            r'\b(if|then|else|for|in|do|done|function|return|import|from|as|and|or|not|True|False|None)\b',
            r'<span class="kw">\1</span>', line
        )
        lines.append(line)
    return "\n".join(lines)


def md_to_html(md_text: str) -> str:
    # Strip the H1 title — it goes on the cover page instead
    md_text = re.sub(r'^#\s+.+\n', '', md_text, count=1)

    md_ext = [
        "fenced_code", "tables", "attr_list",
        "def_list", "footnotes", "toc",
        "nl2br", "sane_lists",
    ]
    body = markdown.markdown(md_text, extensions=md_ext)

    # Apply shell highlighting to every <pre><code> block
    def _highlight(m):
        inner = m.group(1)
        inner = (inner
                 .replace("&amp;", "&")
                 .replace("&lt;", "<")
                 .replace("&gt;", ">"))
        return f"<pre><code>{highlight_shell(inner)}</code></pre>"

    body = re.sub(r"<pre><code[^>]*>([\s\S]*?)</code></pre>", _highlight, body)

    cover = """
<div class="cover">
  <div class="cover-logo">&#9672; Phoenix SmartAutomation</div>
  <h1>End User<br><span>Guide</span></h1>
  <p class="cover-subtitle">From user story to running Playwright tests — no build tools required.</p>
  <div class="cover-meta">
    Version <span class="cover-version">0.1.4</span><br>
    Prepared for QA Teams &amp; End Users<br>
    Phoenix SmartAutomation Platform
  </div>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phoenix SmartAutomation — End User Guide v0.1.4</title>
<style>{CSS}</style>
</head>
<body>
{cover}
{body}
</body>
</html>"""
    return html


def main():
    print(f"Reading  {MD_FILE}")
    md_text = MD_FILE.read_text(encoding="utf-8")

    print("Converting Markdown -> HTML ...")
    html = md_to_html(md_text)
    HTML_FILE.write_text(html, encoding="utf-8")
    print(f"HTML     {HTML_FILE}")

    print("Rendering HTML -> PDF via Chromium ...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(HTML_FILE.as_uri(), wait_until="networkidle", timeout=30000)
        page.pdf(
            path=str(PDF_FILE),
            format="A4",
            print_background=True,
            margin={"top": "20mm", "bottom": "22mm", "left": "16mm", "right": "16mm"},
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=(
                "<div style='font-size:8pt;color:#9CA3AF;width:100%;text-align:center;"
                "font-family:Inter,sans-serif;padding-bottom:4mm'>"
                "Phoenix SmartAutomation &nbsp;·&nbsp; End User Guide &nbsp;·&nbsp; v0.1.4"
                "&nbsp;·&nbsp; Page <span class='pageNumber'></span> "
                "of <span class='totalPages'></span></div>"
            ),
        )
        browser.close()

    size_kb = round(PDF_FILE.stat().st_size / 1024)
    print(f"PDF      {PDF_FILE}  ({size_kb} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
