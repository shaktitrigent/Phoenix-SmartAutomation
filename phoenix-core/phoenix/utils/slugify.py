"""Filename-safe slug generation.

Rules:
  - lowercase; convert any non-alphanumeric run → single underscore
  - strip leading/trailing underscores; collapse repeated underscores
  - NEVER truncate mid-word: if max_len is enforced, drop WHOLE trailing words
  - on collision, append a short stable 4-char hash suffix rather than slicing

Used by:
  - AutomationTestGenerator  (tests/test_{NNN}_{slug}.py)
  - ManualTestGenerator      (manual_tests/manual_test_{NNN}_{slug}.md)
  - OutputManager page objects ({slug}_page.py)
"""

from __future__ import annotations

import hashlib
import re


_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_COLLAPSE   = re.compile(r"_+")


def slugify(
    name: str,
    max_len: int = 80,
    suffix: str = "",
) -> str:
    """Return a filesystem-safe snake_case slug from *name*.

    Args:
        name:    The human-readable title / test name.
        max_len: Maximum character length for the slug (default 80).
                 Whole trailing words are dropped until the slug fits.
                 Set to 0 for unlimited.
        suffix:  Optional stable suffix to append (e.g. a test id or hash).
                 Appended AFTER the word-trimming so it is never cut.

    Returns:
        A non-empty slug string, always starting and ending with an
        alphanumeric character.
    """
    raw = _NON_ALNUM.sub("_", name.lower())
    raw = _COLLAPSE.sub("_", raw).strip("_")

    if not raw:
        raw = "test"

    if suffix:
        raw = f"{raw}_{suffix.strip('_')}"
        raw = _COLLAPSE.sub("_", raw).strip("_")

    if max_len <= 0 or len(raw) <= max_len:
        return raw

    # Drop WHOLE trailing words to fit within max_len
    words = raw.split("_")
    while words and len("_".join(words)) > max_len:
        words.pop()

    trimmed = "_".join(words).strip("_") or raw[:max_len]
    return trimmed


def unique_slug(
    name: str,
    existing: set[str],
    max_len: int = 80,
) -> str:
    """Like slugify() but appends a 4-char hash if the base slug already exists.

    Args:
        name:     Source title.
        existing: Set of slugs already in use.
        max_len:  Maximum length *including* any hash suffix.

    Returns:
        A slug not present in *existing*.
    """
    base = slugify(name, max_len=max_len)
    if base not in existing:
        return base

    # Build a stable 4-char hash from the full (untrimmed) slug
    h = hashlib.sha1(name.lower().encode()).hexdigest()[:4]
    # Re-slug with reduced max_len to leave room for _XXXX
    base2 = slugify(name, max_len=max_len - 5)
    candidate = f"{base2}_{h}"
    return candidate
