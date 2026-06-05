"""DocumentLoader — extract readable text from supporting documents.

Supports:
  Native (no extra deps): .txt .md .csv .json .xml .yaml .yml .html .htm
  Optional deps:          .pdf  (pypdf)
                          .docx (python-docx)
                          .xlsx .xls (openpyxl)

Each document is returned as::

    {
        "filename": "wireframe.pdf",
        "format":   "pdf",
        "content":  "...extracted text, truncated to _MAX_CHARS_PER_DOC...",
    }

Usage::

    loader = DocumentLoader()
    docs = loader.load_directory(Path("user_stories/apply_leave"))
    # or
    doc = loader.load_file(Path("requirements.docx"))
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Characters kept per document (prevents single large file from flooding the context)
_MAX_CHARS_PER_DOC = 8_000
# Total characters across all documents passed to the LLM
_MAX_CHARS_TOTAL = 32_000

# File extensions that can be read without any optional dependency
_NATIVE_TEXT_EXTS = {".txt", ".md", ".html", ".htm", ".xml", ".yaml", ".yml"}


def _truncate(text: str, limit: int = _MAX_CHARS_PER_DOC) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated — {len(text) - limit} chars omitted]"


# ---------------------------------------------------------------------------
# Format-specific extractors
# ---------------------------------------------------------------------------

def _read_plain(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_csv(path: Path) -> str:
    """Convert CSV to a readable tabular text block."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return ""
    col_widths = [max(len(str(r[i])) for r in rows if i < len(r)) for i in range(len(rows[0]))]
    lines = []
    for row in rows:
        padded = [str(row[i]).ljust(col_widths[i]) if i < len(col_widths) else str(row[i]) for i in range(len(row))]
        lines.append("  ".join(padded))
    return "\n".join(lines)


def _read_json(path: Path) -> str:
    """Pretty-print JSON so the LLM can read it as structured text."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return json.dumps(data, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> Optional[str]:
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())
    except ImportError:
        pass
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(str(path)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())
    except ImportError:
        logger.warning(
            "PDF extraction skipped for %s — install 'pypdf' or 'pdfplumber': pip install pypdf",
            path.name,
        )
        return None


def _read_docx(path: Path) -> Optional[str]:
    try:
        import docx  # type: ignore
        doc = docx.Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except ImportError:
        logger.warning(
            "Word document extraction skipped for %s — install 'python-docx': pip install python-docx",
            path.name,
        )
        return None


def _read_xlsx(path: Path) -> Optional[str]:
    try:
        import openpyxl  # type: ignore
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        lines: List[str] = []
        for sheet in wb.worksheets:
            lines.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(c.strip() for c in cells):
                    lines.append("  ".join(cells))
        return "\n".join(lines)
    except ImportError:
        logger.warning(
            "Excel extraction skipped for %s — install 'openpyxl': pip install openpyxl",
            path.name,
        )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class DocumentLoader:
    """Load and extract text from supporting documents of any common format."""

    # Extensions this loader will attempt to process
    SUPPORTED_EXTS = {
        ".txt", ".md", ".html", ".htm",
        ".xml", ".yaml", ".yml",
        ".csv",
        ".json",
        ".pdf",
        ".docx",
        ".xlsx", ".xls",
    }

    def load_file(self, path: Path) -> Optional[Dict[str, str]]:
        """Extract text from a single file.

        Returns None if the format is unsupported or extraction fails.
        """
        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTS:
            logger.debug("Skipping unsupported format: %s", path.name)
            return None

        content: Optional[str] = None
        try:
            if ext in _NATIVE_TEXT_EXTS:
                content = _read_plain(path)
            elif ext == ".csv":
                content = _read_csv(path)
            elif ext == ".json":
                content = _read_json(path)
            elif ext == ".pdf":
                content = _read_pdf(path)
            elif ext == ".docx":
                content = _read_docx(path)
            elif ext in (".xlsx", ".xls"):
                content = _read_xlsx(path)
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path.name, exc)
            return None

        if not content or not content.strip():
            return None

        return {
            "filename": path.name,
            "format": ext.lstrip("."),
            "content": _truncate(content.strip()),
        }

    def load_directory(self, dir_path: Path) -> List[Dict[str, str]]:
        """Load all supported documents from *dir_path* (non-recursive).

        Files are returned sorted by name for deterministic prompt ordering.
        """
        if not dir_path.is_dir():
            return []

        docs: List[Dict[str, str]] = []
        total_chars = 0

        for file_path in sorted(dir_path.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.SUPPORTED_EXTS:
                continue
            if total_chars >= _MAX_CHARS_TOTAL:
                logger.warning(
                    "Supporting documents total limit (%d chars) reached — skipping %s and remaining files",
                    _MAX_CHARS_TOTAL,
                    file_path.name,
                )
                break

            doc = self.load_file(file_path)
            if doc:
                # Respect global total cap
                remaining = _MAX_CHARS_TOTAL - total_chars
                if len(doc["content"]) > remaining:
                    doc["content"] = doc["content"][:remaining] + "\n... [truncated]"
                docs.append(doc)
                total_chars += len(doc["content"])
                logger.info("Loaded supporting doc: %s (%d chars)", file_path.name, len(doc["content"]))

        return docs

    def supporting_docs_dir_for_story(self, story_file: Path) -> Path:
        """Return the conventional supporting-docs folder for a story file.

        Convention: story file  user_stories/apply_leave.txt
                    docs folder user_stories/apply_leave/
        """
        return story_file.parent / story_file.stem
