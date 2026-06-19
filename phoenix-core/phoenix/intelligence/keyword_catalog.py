"""Keyword Catalog — prevents duplicate Gherkin phrasing and maps every keyword
to its step function and page method.

Catalog file: .phoenix/keywords.json
Schema (single entry):
    {
      "id": "login_as",
      "canonical": "I log in as {username}",
      "aliases": ["I sign in as {username}"],
      "step_type": "when",
      "step_function": "steps/login_steps.py::step_login_as",
      "page_method": "LoginPage.login",
      "params": ["username"]
    }
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# rapidfuzz is optional; fall back to a simple ratio when not installed
try:
    from rapidfuzz import fuzz as _fuzz
    def _similarity(a: str, b: str) -> float:
        return _fuzz.token_sort_ratio(a, b)
except ImportError:
    def _similarity(a: str, b: str) -> float:
        # Jaccard on word sets as a cheap fallback
        wa, wb = set(a.split()), set(b.split())
        union = wa | wb
        return len(wa & wb) / len(union) * 100 if union else 0.0

FUZZY_THRESHOLD = 90.0   # minimum score to count as a match


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Keyword:
    id: str
    canonical: str
    aliases: List[str] = field(default_factory=list)
    step_type: str = "when"         # given | when | then
    step_function: str = ""
    page_method: str = ""
    params: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "canonical": self.canonical,
            "aliases": self.aliases,
            "step_type": self.step_type,
            "step_function": self.step_function,
            "page_method": self.page_method,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Keyword":
        return cls(
            id=d["id"],
            canonical=d.get("canonical", ""),
            aliases=d.get("aliases", []),
            step_type=d.get("step_type", "when"),
            step_function=d.get("step_function", ""),
            page_method=d.get("page_method", ""),
            params=d.get("params", []),
        )


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_LEADING_ARTICLES = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)
_QUOTED_VALUE = re.compile(r'"[^"]*"')
_SINGLE_QUOTED = re.compile(r"'[^']*'")
_NUMBER = re.compile(r"\b\d+\b")
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Return a canonical key for *text* used for exact and fuzzy matching.

    Transformations applied (in order):
    1. lowercase
    2. strip leading Gherkin keywords (given/when/then/and/but)
    3. strip leading articles (a/an/the)
    4. replace quoted strings and bare numbers with {param}
    5. collapse whitespace and strip
    """
    t = text.strip().lower()
    t = re.sub(r"^(given|when|then|and|but)\s+", "", t)
    t = _LEADING_ARTICLES.sub("", t)
    t = _QUOTED_VALUE.sub("{param}", t)
    t = _SINGLE_QUOTED.sub("{param}", t)
    t = _NUMBER.sub("{param}", t)
    t = _WHITESPACE.sub(" ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class KeywordCatalog:
    """Manages .phoenix/keywords.json — the growing vocabulary of BDD keywords."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._keywords: Dict[str, Keyword] = {}
        self._norm_index: Dict[str, str] = {}  # normalised text → keyword id
        if self.path.exists():
            self.load()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def normalize(self, text: str) -> str:
        return normalize(text)

    def find_match(self, step_text: str) -> Optional[Keyword]:
        """Return the best-matching Keyword or None.

        Priority:
        1. Exact normalized match against canonical + all aliases.
        2. Fuzzy match (token sort ratio ≥ FUZZY_THRESHOLD) — returns best.
        """
        key = normalize(step_text)

        # Exact match in pre-built index
        if key in self._norm_index:
            return self._keywords.get(self._norm_index[key])

        # Fuzzy match over all canonical + alias normalized forms
        best_score = 0.0
        best_kw: Optional[Keyword] = None
        for norm_form, kw_id in self._norm_index.items():
            score = _similarity(key, norm_form)
            if score > best_score:
                best_score = score
                best_kw = self._keywords.get(kw_id)

        return best_kw if best_score >= FUZZY_THRESHOLD else None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add(self, keyword: Keyword) -> None:
        """Append a keyword; reject silently if the id already exists."""
        if keyword.id in self._keywords:
            return
        self._keywords[keyword.id] = keyword
        self._rebuild_index()
        self.save()

    def add_alias(self, kw_id: str, phrase: str) -> None:
        """Record an additional phrasing for an existing keyword."""
        kw = self._keywords.get(kw_id)
        if kw is None:
            return
        if phrase not in kw.aliases:
            kw.aliases.append(phrase)
        self._rebuild_index()
        self.save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "keywords": [kw.to_dict() for kw in self._keywords.values()],
        }
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._keywords = {
                kw["id"]: Keyword.from_dict(kw) for kw in raw.get("keywords", [])
            }
            self._rebuild_index()
        except (json.JSONDecodeError, OSError, KeyError):
            self._keywords = {}

    def _rebuild_index(self) -> None:
        self._norm_index = {}
        for kw in self._keywords.values():
            self._norm_index[normalize(kw.canonical)] = kw.id
            for alias in kw.aliases:
                self._norm_index[normalize(alias)] = kw.id

    # ------------------------------------------------------------------
    # Summary for LLM injection
    # ------------------------------------------------------------------

    def to_prompt_summary(self) -> str:
        if not self._keywords:
            return "AVAILABLE KEYWORDS: (none yet — this is a new project)\n"
        lines = ["AVAILABLE KEYWORDS (reuse these — match phrasing before inventing new):"]
        for kw in self._keywords.values():
            lines.append(
                f"  - [{kw.step_type}] {kw.canonical}"
                + (f"  -> {kw.page_method}" if kw.page_method else "")
            )
        return "\n".join(lines) + "\n"

    def __len__(self) -> int:
        return len(self._keywords)
