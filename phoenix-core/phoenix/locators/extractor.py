"""Locator Extractor — parses generated Playwright scripts into LocatorBundles.

Scans every ``page.get_by_*`` and ``page.locator()`` call in a script and
produces a :class:`LocatorBundle` for each unique element found.  Each bundle
carries the primary locator strategy **plus automatically generated alternates**
so an automation engineer can quickly swap strategies when a locator breaks.

Supported patterns
------------------
    page.get_by_placeholder("Username")
    page.get_by_role("button", name="Login")
    page.get_by_label("First Name")
    page.get_by_text("Save")
    page.get_by_test_id("submit-btn")
    page.locator(".oxd-toast")
    page.locator("input[type='file']")

Usage
-----
    from phoenix.locators.extractor import extract_locators_from_script
    from phoenix.locators.registry import LocatorRegistry

    bundles = extract_locators_from_script(script_code, page_name="add_employee")
    registry = LocatorRegistry()
    for bundle in bundles:
        registry.upsert(bundle)
    registry.save("locators/add_employee.json", page="add_employee")
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

try:
    from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy
except ImportError:
    from shared.phoenix_shared.models.locator import (  # type: ignore[no-redef]
        Locator,
        LocatorBundle,
        LocatorStrategy,
    )


# ---------------------------------------------------------------------------
# Regex patterns for each Playwright locator API
# ---------------------------------------------------------------------------

_PH_RE = re.compile(r'get_by_placeholder\(["\']([^"\']+)["\']')
_ROLE_RE = re.compile(r'get_by_role\(["\'](\w+)["\'](?:[^)]*?name=["\']([^"\']+)["\'])?\)')
_LABEL_RE = re.compile(r'get_by_label\(["\']([^"\']+)["\']')
_TEXT_RE = re.compile(r'get_by_text\(["\']([^"\']+)["\']')
_TESTID_RE = re.compile(r'get_by_test_id\(["\']([^"\']+)["\']')
_LOCATOR_RE = re.compile(r'(?<!\w)locator\(["\']([^"\']+)["\']\)')
_IGNORE_TEXT_RE = re.compile(
    r"\b(loads?\s+successfully|fields?\s+are\s+visible|manual locator review required"
    r"|criterion not mapped|success message appears|validation error messages appear)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Element name helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a display name to a snake_case slug."""
    text = re.sub(r"[^a-zA-Z0-9\s_-]", "", text)
    text = re.sub(r"[\s\-]+", "_", text.strip())
    return text.lower()


def _element_name_from_placeholder(value: str) -> str:
    return _slugify(value)


def _element_name_from_role(role: str, name: Optional[str]) -> str:
    if name:
        return f"{_slugify(name)}_{role}"
    return _slugify(role)


def _element_name_from_label(value: str) -> str:
    return f"{_slugify(value)}_field"


def _element_name_from_text(value: str) -> str:
    return _slugify(value)


def _element_name_from_testid(value: str) -> str:
    return _slugify(value)


def _element_name_from_locator(selector: str) -> str:
    # Strip CSS/XPath special chars for a readable slug
    slug = re.sub(r"[^a-zA-Z0-9_\-\s]", "_", selector)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:60].lower() or "element"


# ---------------------------------------------------------------------------
# Alternate locator generators
# ---------------------------------------------------------------------------

def _alternates_for_placeholder(value: str) -> List[Locator]:
    return [
        Locator(
            element_name=_element_name_from_placeholder(value),
            strategy=LocatorStrategy.LABEL,
            value=value,
            confidence=0.70,
            fallback=True,
            description=f"Label fallback for placeholder '{value}'",
        ),
        Locator(
            element_name=_element_name_from_placeholder(value),
            strategy=LocatorStrategy.CSS,
            value=f"input[placeholder='{value}']",
            confidence=0.50,
            fallback=True,
            description=f"CSS attribute selector for placeholder '{value}'",
        ),
    ]


def _alternates_for_role(role: str, name: Optional[str]) -> List[Locator]:
    alts: List[Locator] = []
    elem_name = _element_name_from_role(role, name)
    if name:
        alts.append(
            Locator(
                element_name=elem_name,
                strategy=LocatorStrategy.TEXT,
                value=name,
                confidence=0.70,
                fallback=True,
                description=f"Text fallback for role '{role}' name '{name}'",
            )
        )
        alts.append(
            Locator(
                element_name=elem_name,
                strategy=LocatorStrategy.CSS,
                value=f"{role}:has-text(\"{name}\")",
                confidence=0.50,
                fallback=True,
                description=f"CSS :has-text fallback for {role} '{name}'",
            )
        )
    else:
        alts.append(
            Locator(
                element_name=elem_name,
                strategy=LocatorStrategy.CSS,
                value=role,
                confidence=0.50,
                fallback=True,
                description=f"CSS tag fallback for role '{role}'",
            )
        )
    return alts


def _alternates_for_label(value: str) -> List[Locator]:
    elem_name = _element_name_from_label(value)
    return [
        Locator(
            element_name=elem_name,
            strategy=LocatorStrategy.PLACEHOLDER,
            value=value,
            confidence=0.70,
            fallback=True,
            description=f"Placeholder fallback for label '{value}'",
        ),
        Locator(
            element_name=elem_name,
            strategy=LocatorStrategy.CSS,
            value=f"input[aria-label='{value}']",
            confidence=0.50,
            fallback=True,
            description=f"aria-label CSS fallback for '{value}'",
        ),
    ]


def _alternates_for_text(value: str) -> List[Locator]:
    elem_name = _element_name_from_text(value)
    return [
        Locator(
            element_name=elem_name,
            strategy=LocatorStrategy.CSS,
            value=f":text(\"{value}\")",
            confidence=0.60,
            fallback=True,
            description=f"CSS :text fallback for '{value}'",
        ),
    ]


def _alternates_for_locator(selector: str) -> List[Locator]:
    elem_name = _element_name_from_locator(selector)
    # For class selectors, offer a partial-class variant
    class_match = re.match(r"^\.([a-zA-Z][\w-]+)$", selector.strip())
    if class_match:
        cls = class_match.group(1)
        return [
            Locator(
                element_name=elem_name,
                strategy=LocatorStrategy.CSS,
                value=f"[class*='{cls}']",
                confidence=0.50,
                fallback=True,
                description=f"Partial class fallback for '{selector}'",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

_SEEN_KEY = Tuple[str, str]  # (strategy_value, element_name)


def extract_locators_from_script(
    script_code: str,
    page_name: str = "global",
) -> List[LocatorBundle]:
    """Parse *script_code* and return one LocatorBundle per unique element.

    Deduplication is by (strategy + value) so the same locator call appearing
    in multiple steps produces only one bundle entry.

    Args:
        script_code: Full content of a pytest + Playwright Python file.
        page_name:   Logical page name stored in each bundle's ``.page`` field.
                     Typically derived from the test script filename.

    Returns:
        List of LocatorBundle objects ready to be upserted into a registry.
    """
    bundles: Dict[str, LocatorBundle] = {}  # keyed by element_name
    seen: set = set()

    def _add(
        elem_name: str,
        strategy: LocatorStrategy,
        value: str,
        confidence: float,
        description: str,
        alternates: List[Locator],
    ) -> None:
        if strategy == LocatorStrategy.TEXT and _IGNORE_TEXT_RE.search(value):
            return
        if strategy == LocatorStrategy.ROLE and value == "heading":
            return
        dedup_key = (strategy.value, value)
        if dedup_key in seen:
            return
        seen.add(dedup_key)

        # If the element name already has a bundle, keep the higher-confidence one
        existing = bundles.get(elem_name)
        if existing and existing.primary.confidence >= confidence:
            return

        primary = Locator(
            element_name=elem_name,
            strategy=strategy,
            value=value,
            confidence=confidence,
            description=description,
        )
        # Fix element_name in alternates
        fixed_alts = [a.model_copy(update={"element_name": elem_name}) for a in alternates]
        bundles[elem_name] = LocatorBundle(
            element_name=elem_name,
            page=page_name,
            primary=primary,
            alternates=fixed_alts,
            notes="Auto-extracted from script during phoenix generate",
        )

    # --- get_by_placeholder ---
    for m in _PH_RE.finditer(script_code):
        v = m.group(1)
        _add(
            _element_name_from_placeholder(v),
            LocatorStrategy.PLACEHOLDER, v, 0.90,
            f"Placeholder input: '{v}'",
            _alternates_for_placeholder(v),
        )

    # --- get_by_role ---
    for m in _ROLE_RE.finditer(script_code):
        role, name = m.group(1), m.group(2)
        val = f"{role}[name={name}]" if name else role
        _add(
            _element_name_from_role(role, name),
            LocatorStrategy.ROLE, val, 0.95,
            f"Role '{role}'" + (f" name '{name}'" if name else ""),
            _alternates_for_role(role, name),
        )

    # --- get_by_label ---
    for m in _LABEL_RE.finditer(script_code):
        v = m.group(1)
        _add(
            _element_name_from_label(v),
            LocatorStrategy.LABEL, v, 0.85,
            f"Label: '{v}'",
            _alternates_for_label(v),
        )

    # --- get_by_text ---
    for m in _TEXT_RE.finditer(script_code):
        v = m.group(1)
        _add(
            _element_name_from_text(v),
            LocatorStrategy.TEXT, v, 0.75,
            f"Text content: '{v}'",
            _alternates_for_text(v),
        )

    # --- get_by_test_id ---
    for m in _TESTID_RE.finditer(script_code):
        v = m.group(1)
        _add(
            _element_name_from_testid(v),
            LocatorStrategy.TEST_ID, v, 0.98,
            f"Test ID: '{v}'",
            [],
        )

    # --- locator() ---
    for m in _LOCATOR_RE.finditer(script_code):
        v = m.group(1)
        _add(
            _element_name_from_locator(v),
            LocatorStrategy.CSS, v, 0.65,
            f"CSS/XPath selector: '{v}'",
            _alternates_for_locator(v),
        )

    return list(bundles.values())


def page_name_from_script_path(script_path: str) -> str:
    """Derive a logical page name from a script filename.

    Examples:
        test_001_add_employee.py  →  add_employee
        test_tc_002_login_flow.py →  tc_002_login_flow
    """
    from pathlib import Path

    stem = Path(script_path).stem  # e.g. "test_001_add_employee"
    # Strip leading "test_" prefix
    name = re.sub(r"^test_", "", stem)
    return name or stem
