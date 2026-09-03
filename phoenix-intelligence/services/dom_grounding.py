"""Generic DOM grounding helpers for automation generation.

Works for any application: extracts interactive elements and attributes from
HTML / accessibility snapshots and builds LLM-ready context + Playwright
locator expressions without hard-coding app-specific IDs.

Captures simple form controls and complex widgets (tables/grids, iframes,
dialogs, ARIA roles, charts with hooks). Prompt context ranks by relevance
(priority labels + uniqueness + visibility) *before* applying size caps.
"""
from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
# Any opening tag — filtered to interactive / structural widgets.
_OPEN_TAG_RE = re.compile(
    r"<(?P<tag>[a-zA-Z][\w:-]*)\b(?P<attrs>[^>]*)>",
    re.IGNORECASE,
)
_ATTR_RE = re.compile(
    r"""(?P<name>[\w:-]+)\s*=\s*(?P<q>["'])(?P<value>.*?)(?P=q)""",
    re.IGNORECASE | re.DOTALL,
)
_NEARBY_HINT_RE = re.compile(
    r"(?:placeholder|aria-label|title|alt|name|id|data-testid|data-test|value|"
    r"form-hint|label)\s*[:=]\s*['\"]?([^'\"<>]{1,80})",
    re.IGNORECASE,
)
_NOISE_TOKEN_RE = re.compile(
    r"(footer|cookie|banner|advert|copyright|social-icon)",
    re.IGNORECASE,
)

_NATIVE_INTERACTIVE_TAGS = frozenset(
    {
        "input",
        "button",
        "select",
        "textarea",
        "a",
        "option",
        "label",
        "summary",
        "details",
        "iframe",
        "area",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        "dialog",
        "menu",
        "menuitem",
        "fieldset",
        "legend",
        "canvas",
        "svg",
    }
)
_VOID_TAGS = frozenset(
    {
        "input",
        "img",
        "area",
        "br",
        "hr",
        "meta",
        "link",
        "col",
        "embed",
        "source",
        "track",
        "wbr",
    }
)
_INTERACTIVE_ROLES = frozenset(
    {
        "button",
        "link",
        "textbox",
        "searchbox",
        "combobox",
        "listbox",
        "option",
        "checkbox",
        "radio",
        "switch",
        "slider",
        "spinbutton",
        "tab",
        "tablist",
        "tabpanel",
        "menuitem",
        "menuitemcheckbox",
        "menuitemradio",
        "menu",
        "menubar",
        "tree",
        "treeitem",
        "grid",
        "gridcell",
        "row",
        "rowgroup",
        "columnheader",
        "rowheader",
        "cell",
        "table",
        "dialog",
        "alertdialog",
        "toolbar",
        "navigation",
        "progressbar",
        "img",
        "graphics-document",
        "graphics-object",
        "list",
        "listitem",
        "form",
        "group",
    }
)
_CLICK_ROLES = frozenset(
    {
        "button",
        "link",
        "menuitem",
        "menuitemcheckbox",
        "menuitemradio",
        "tab",
        "treeitem",
        "option",
        "checkbox",
        "radio",
        "switch",
        "row",
        "gridcell",
        "cell",
        "columnheader",
        "rowheader",
    }
)
_INPUT_ROLES = frozenset(
    {
        "textbox",
        "searchbox",
        "combobox",
        "listbox",
        "spinbutton",
        "slider",
        "checkbox",
        "radio",
        "switch",
    }
)


@dataclass
class InteractiveElement:
    """One interactive control discovered in HTML (app-agnostic)."""

    tag: str
    attrs: Dict[str, str] = field(default_factory=dict)
    text: str = ""
    hints: List[str] = field(default_factory=list)
    source_offset: int = 0

    @property
    def input_type(self) -> str:
        return (self.attrs.get("type") or "").lower()

    @property
    def kind_hint(self) -> str:
        role = (self.attrs.get("role") or "").lower()
        if self.tag in {"button", "a", "summary", "menuitem"} or role in _CLICK_ROLES:
            return "button"
        if self.tag == "input" and self.input_type in {
            "submit",
            "button",
            "image",
            "checkbox",
            "radio",
        }:
            return "button"
        if self.tag in {"th", "td", "tr", "table", "iframe", "canvas", "svg"} or role in {
            "grid",
            "table",
            "row",
            "cell",
            "gridcell",
            "columnheader",
            "dialog",
            "img",
            "graphics-document",
        }:
            return "button" if role in _CLICK_ROLES or self.tag in {"th", "a"} else "input"
        if self.tag in {"input", "textarea", "select", "option", "label"} or role in _INPUT_ROLES:
            return "input"
        return "input"

    def is_hiddenish(self) -> bool:
        """Cheap visibility heuristic from attributes (no live browser)."""
        if self.input_type == "hidden":
            return True
        if (self.attrs.get("aria-hidden") or "").lower() == "true":
            return True
        if "hidden" in self.attrs and (self.attrs.get("hidden") or "").lower() in {
            "",
            "true",
            "hidden",
        }:
            return True
        style = (self.attrs.get("style") or "").lower()
        if "display:none" in style.replace(" ", "") or "visibility:hidden" in style.replace(" ", ""):
            return True
        return False

    def uniqueness_bonus(self) -> float:
        """Prefer attributes that usually yield strict-mode-safe locators."""
        bonus = 0.0
        if self.attrs.get("data-testid") or self.attrs.get("data-test"):
            bonus += 0.35
        if self.attrs.get("id") and _is_safe_css_ident(self.attrs["id"]):
            bonus += 0.3
        if self.attrs.get("name"):
            bonus += 0.2
        if self.attrs.get("aria-label") or self.attrs.get("placeholder"):
            bonus += 0.1
        if self.attrs.get("role"):
            bonus += 0.05
        return bonus

    def score_for_label(self, label: str, *, kind: str = "input") -> float:
        """Score how well this element matches a semantic field/button label."""
        needle = _normalize_token(label)
        if not needle:
            return 0.0

        role = (self.attrs.get("role") or "").lower()
        haystacks: List[Tuple[str, float]] = []
        for key, weight in (
            ("data-testid", 1.0),
            ("data-test", 1.0),
            ("name", 0.95),
            ("id", 0.9),
            ("placeholder", 0.9),
            ("aria-label", 0.9),
            ("title", 0.7),
            ("value", 0.75),
            ("role", 0.5),
        ):
            val = self.attrs.get(key)
            if val:
                haystacks.append((_normalize_token(val), weight))
        if self.text:
            haystacks.append((_normalize_token(self.text), 0.85))
        for hint in self.hints:
            haystacks.append((_normalize_token(hint), 0.8))

        best = 0.0
        for hay, weight in haystacks:
            if not hay:
                continue
            if hay == needle:
                best = max(best, 1.0 * weight)
            elif needle in hay or hay in needle:
                best = max(best, 0.85 * weight)
            else:
                n_parts = set(p for p in re.split(r"[^a-z0-9]+", needle) if p)
                h_parts = set(p for p in re.split(r"[^a-z0-9]+", hay) if p)
                if n_parts and h_parts and n_parts.issubset(h_parts):
                    best = max(best, 0.8 * weight)
                elif n_parts and h_parts and (n_parts & h_parts):
                    best = max(best, 0.55 * weight)

        if kind == "any":
            return best

        if kind == "button":
            clickable = (
                self.tag in {"button", "input", "a", "summary", "menuitem", "th", "label"}
                or role in _CLICK_ROLES
                or self.input_type in {"submit", "button", "image", "checkbox", "radio"}
            )
            if not clickable:
                if self.tag in {"td", "tr", "table", "iframe", "div", "span", "li"} or role:
                    best *= 0.85
                else:
                    return 0.0
            if self.tag == "input" and self.input_type not in {
                "",
                "submit",
                "button",
                "image",
                "checkbox",
                "radio",
            }:
                best *= 0.3
            if self.tag == "a" and best < 0.7:
                best *= 0.5
        else:
            fillable = self.tag in {"input", "textarea", "select", "option"} or role in _INPUT_ROLES
            if not fillable:
                if "contenteditable" in self.attrs and (self.attrs.get("contenteditable") or "").lower() in {
                    "",
                    "true",
                }:
                    fillable = True
            if not fillable:
                return 0.0
            if self.tag == "input" and self.input_type in {
                "submit",
                "button",
                "image",
                "hidden",
                "checkbox",
                "radio",
            }:
                if "password" in needle and self.input_type == "password":
                    best = max(best, 0.95)
                elif "email" in needle and self.input_type == "email":
                    best = max(best, 0.95)
                else:
                    best *= 0.2
            if "password" in needle and self.input_type == "password":
                best = max(best, 0.95)
            if "email" in needle and self.input_type in {"email", "text"}:
                best = max(best, best, 0.7)

        return best

    def prompt_priority_score(self, priority_labels: Sequence[str] = ()) -> float:
        """Overall rank for inclusion in the LLM interactive-element map."""
        if self.is_hiddenish() and self.input_type == "hidden":
            return -1.0

        score = self.uniqueness_bonus()
        if self.is_hiddenish():
            score -= 0.5

        role = (self.attrs.get("role") or "").lower()
        if self.tag in {"table", "iframe", "canvas", "dialog"} or role in {
            "grid",
            "table",
            "dialog",
            "graphics-document",
        }:
            score += 0.15

        blob = " ".join(
            [
                self.attrs.get("id", ""),
                self.attrs.get("name", ""),
                self.attrs.get("class", ""),
                self.text,
                " ".join(self.hints[:3]),
            ]
        )
        if _NOISE_TOKEN_RE.search(blob):
            score -= 0.25

        best_label = 0.0
        for label in priority_labels:
            best_label = max(best_label, self.score_for_label(label, kind="any"))
        score += best_label * 2.0
        return score

    def to_playwright_expr(self, *, kind: str = "input") -> Optional[str]:
        """Build a Playwright locator chain from real attributes (no invented IDs)."""
        parts: List[str] = []
        test_id = self.attrs.get("data-testid") or self.attrs.get("data-test")
        if test_id:
            parts.append(f'page.get_by_test_id("{_escape_py(test_id)}")')

        placeholder = self.attrs.get("placeholder")
        aria = self.attrs.get("aria-label")
        el_id = self.attrs.get("id")
        name = self.attrs.get("name")
        value = self.attrs.get("value")
        role = (self.attrs.get("role") or "").strip()
        role_name = (aria or self.text or value or "").strip()

        if role:
            if role_name:
                parts.append(
                    f'page.get_by_role("{_escape_py(role)}", name=re.compile(r"^{re.escape(role_name)}$", re.IGNORECASE))'
                )
            else:
                parts.append(f'page.get_by_role("{_escape_py(role)}")')

        if kind == "button" or self.kind_hint == "button":
            if role_name and not role:
                parts.append(
                    f'page.get_by_role("button", name=re.compile(r"^{re.escape(role_name)}$", re.IGNORECASE))'
                )
            if self.tag == "a" and role_name:
                parts.append(
                    f'page.get_by_role("link", name=re.compile(r"^{re.escape(role_name)}$", re.IGNORECASE))'
                )
            css_bits = []
            if el_id and _is_safe_css_ident(el_id):
                css_bits.append(f"#{el_id}")
            if name:
                css_bits.append(f"input[name='{_escape_css_attr(name)}']")
                css_bits.append(f"button[name='{_escape_css_attr(name)}']")
            if value:
                css_bits.append(f"input[type='submit'][value='{_escape_css_attr(value)}']")
            if test_id:
                css_bits.append(f"[data-testid='{_escape_css_attr(test_id)}']")
            if self.tag == "iframe":
                if el_id and _is_safe_css_ident(el_id):
                    css_bits.append(f"iframe#{el_id}")
                if name:
                    css_bits.append(f"iframe[name='{_escape_css_attr(name)}']")
            if self.tag == "table" and el_id and _is_safe_css_ident(el_id):
                css_bits.append(f"table#{el_id}")
            if css_bits:
                parts.append(f'page.locator("{", ".join(dict.fromkeys(css_bits))}")')
        else:
            if placeholder:
                parts.append(f'page.get_by_placeholder("{_escape_py(placeholder)}", exact=True)')
            if aria:
                parts.append(f'page.get_by_label("{_escape_py(aria)}", exact=True)')
            css_bits = []
            if el_id and _is_safe_css_ident(el_id):
                css_bits.append(f"#{el_id}")
            if name:
                css_bits.append(f"input[name='{_escape_css_attr(name)}']")
                css_bits.append(f"textarea[name='{_escape_css_attr(name)}']")
                css_bits.append(f"select[name='{_escape_css_attr(name)}']")
            if test_id:
                css_bits.append(f"[data-testid='{_escape_css_attr(test_id)}']")
                css_bits.append(f"[data-test='{_escape_css_attr(test_id)}']")
            if css_bits:
                parts.append(f'page.locator("{", ".join(dict.fromkeys(css_bits))}")')

        if not parts:
            return None
        preferred = _prefer_unique_locator_parts(parts)
        expr = preferred[0]
        for part in preferred[1:]:
            expr = f"{expr}.or_({part})"
        return expr

    def summary_line(self, *, include_locator: bool = True) -> str:
        interesting = {
            k: v
            for k, v in self.attrs.items()
            if k
            in {
                "id",
                "name",
                "type",
                "placeholder",
                "aria-label",
                "data-testid",
                "data-test",
                "value",
                "href",
                "role",
                "tabindex",
                "contenteditable",
                "src",
                "title",
            }
            and v
        }
        text = self.text.strip()[:60]
        hint = f" text={text!r}" if text else ""
        hint2 = f" hints={self.hints[:3]}" if self.hints else ""
        line = f"<{self.tag} {interesting}>{hint}{hint2}"
        if include_locator:
            locator = self.to_playwright_expr(kind=self.kind_hint)
            if locator:
                primary = locator.split(".or_(")[0]
                line = f"{line} preferred_locator={primary}"
        return line


def _prefer_unique_locator_parts(parts: List[str]) -> List[str]:
    """Order locator strategies: test-id / id CSS before broader role/text."""

    def rank(part: str) -> int:
        if "get_by_test_id" in part:
            return 0
        if "page.locator(\"#" in part or "page.locator('#" in part:
            return 1
        if "get_by_placeholder" in part or "get_by_label" in part:
            return 2
        if "get_by_role" in part:
            return 3
        return 4

    return sorted(parts, key=rank)


def _label_looks_like_button(label: str) -> bool:
    low = (label or "").lower()
    return bool(
        re.search(
            r"\b(log\s*in|login|sign\s*in|submit|save|continue|next|apply|search|ok|cancel)\b",
            low,
        )
    )


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _escape_py(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_css_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _is_safe_css_ident(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][\w\-:.]*", value or ""))


def _parse_attrs(attrs_str: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for match in _ATTR_RE.finditer(attrs_str or ""):
        attrs[match.group("name").lower()] = html_lib.unescape(match.group("value")).strip()
    return attrs


def strip_noise_from_html(html: str, *, max_chars: int = 120_000) -> str:
    """Remove scripts/styles and optionally truncate for prompts/storage previews."""
    if not html:
        return ""
    cleaned = _SCRIPT_STYLE_RE.sub("", html)
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n<!-- truncated -->"
    return cleaned


def _is_interactive_candidate(tag: str, attrs: Dict[str, str]) -> bool:
    """True when a tag should be included in the interactive-element map."""
    tag = (tag or "").lower()
    role = (attrs.get("role") or "").lower()

    if tag in _NATIVE_INTERACTIVE_TAGS:
        # Plain table cells explode maps; keep only identifiable / role-bearing cells.
        if tag == "td":
            return bool(
                attrs.get("id")
                or attrs.get("data-testid")
                or attrs.get("data-test")
                or attrs.get("role")
                or attrs.get("tabindex")
                or attrs.get("onclick")
            )
        if tag in {"canvas", "svg"}:
            return bool(
                attrs.get("id")
                or attrs.get("data-testid")
                or attrs.get("data-test")
                or attrs.get("aria-label")
                or attrs.get("role")
                or attrs.get("title")
            )
        return True

    if role in _INTERACTIVE_ROLES:
        return True
    if attrs.get("data-testid") or attrs.get("data-test"):
        return True
    if "tabindex" in attrs:
        return True
    if "contenteditable" in attrs and (attrs.get("contenteditable") or "").lower() in {
        "",
        "true",
    }:
        return True
    if attrs.get("onclick") or attrs.get("ng-click") or attrs.get("@click"):
        return True
    return False


def _extract_tag_text(cleaned: str, open_end: int, tag: str) -> str:
    """Best-effort visible text after an opening tag (short window)."""
    if tag in _VOID_TAGS:
        return ""
    snippet = cleaned[open_end : open_end + 240]
    close = re.search(rf"</{re.escape(tag)}\s*>", snippet, re.IGNORECASE)
    if close:
        snippet = snippet[: close.start()]
    text = re.sub(r"<[^>]+>", " ", snippet)
    return html_lib.unescape(re.sub(r"\s+", " ", text)).strip()[:80]


def extract_interactive_elements(html: str) -> List[InteractiveElement]:
    """Extract interactive / structural controls from HTML (app-agnostic).

    Includes form controls, links, tables, iframes, dialogs, ARIA widgets,
    charts with hooks, and elements with testability attributes.
    """
    if not html or "<" not in html:
        return []

    cleaned = _SCRIPT_STYLE_RE.sub("", html)
    elements: List[InteractiveElement] = []
    seen: set = set()

    for match in _OPEN_TAG_RE.finditer(cleaned):
        tag = (match.group("tag") or "").lower()
        if tag in {"script", "style", "noscript", "html", "head", "body", "meta", "link", "br", "hr"}:
            continue
        attrs = _parse_attrs(match.group("attrs") or "")
        if not _is_interactive_candidate(tag, attrs):
            continue

        text = _extract_tag_text(cleaned, match.end(), tag)
        window = cleaned[match.end() : match.end() + 240]
        hints: List[str] = []
        for hm in _NEARBY_HINT_RE.finditer(window):
            hints.append(hm.group(1).strip())
        for hm in re.finditer(
            r'class=["\'][^"\']*(?:hint|label|form-hint)[^"\']*["\'][^>]*>([^<]{1,60})',
            window,
            re.IGNORECASE,
        ):
            hints.append(hm.group(1).strip())

        dedupe_key = (
            tag,
            attrs.get("id", ""),
            attrs.get("name", ""),
            attrs.get("data-testid") or attrs.get("data-test") or "",
            attrs.get("role", ""),
            text[:40],
            match.start(),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        elements.append(
            InteractiveElement(
                tag=tag,
                attrs=attrs,
                text=text,
                hints=[h for h in dict.fromkeys(hints) if h],
                source_offset=match.start(),
            )
        )
    return elements


def rank_elements_for_prompt(
    elements: Sequence[InteractiveElement],
    *,
    priority_labels: Sequence[str] = (),
    max_elements: int = 80,
) -> List[InteractiveElement]:
    """Rank interactive elements by relevance, then take the top N."""
    if not elements:
        return []
    scored: List[Tuple[float, int, InteractiveElement]] = []
    for idx, el in enumerate(elements):
        score = el.prompt_priority_score(priority_labels)
        if score < 0:
            continue
        scored.append((score, idx, el))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [el for _, _, el in scored[:max_elements]]


def resolve_locator_from_dom(
    label: str,
    *,
    kind: str = "input",
    html: str = "",
    min_score: float = 0.55,
) -> Optional[str]:
    """Resolve a Playwright locator expression from live HTML attributes."""
    elements = extract_interactive_elements(html)
    if not elements:
        return None

    ranked: List[Tuple[float, InteractiveElement]] = []
    for el in elements:
        score = el.score_for_label(label, kind=kind)
        if score >= min_score:
            ranked.append((score, el))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1].to_playwright_expr(kind=kind)


def _html_slice_for_prompt(
    html: str,
    *,
    ranked: Sequence[InteractiveElement],
    max_chars: int,
) -> str:
    """Prefer HTML around top-ranked elements; fall back to document prefix."""
    cleaned = strip_noise_from_html(html, max_chars=max(max_chars * 3, max_chars))
    if len(cleaned) <= max_chars:
        return cleaned

    windows: List[Tuple[int, int]] = []
    pad = max(800, max_chars // 8)
    for el in ranked[:20]:
        start = max(0, el.source_offset - pad)
        end = min(len(cleaned), el.source_offset + pad)
        if end > start:
            windows.append((start, end))
    if not windows:
        return cleaned[:max_chars] + "\n<!-- truncated -->"

    windows.sort()
    merged: List[Tuple[int, int]] = [windows[0]]
    for start, end in windows[1:]:
        prev_s, prev_e = merged[-1]
        if start <= prev_e + 200:
            merged[-1] = (prev_s, max(prev_e, end))
        else:
            merged.append((start, end))

    chunks = [cleaned[s:e] for s, e in merged]
    combined = "\n<!-- ... -->\n".join(chunks)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n<!-- truncated -->"
    elif len(cleaned) > len(combined):
        combined = combined + "\n<!-- html regions prioritized by relevance; remainder omitted -->"
    return combined


def _a11y_slice_for_prompt(
    accessibility_tree: str,
    *,
    priority_labels: Sequence[str],
    max_chars: int,
) -> str:
    """Keep a11y lines that mention priority labels; fill remainder from the start."""
    a11y = (accessibility_tree or "").strip()
    if not a11y:
        return ""
    if len(a11y) <= max_chars:
        return a11y

    labels = [lab.strip() for lab in priority_labels if lab and lab.strip()]
    if not labels:
        return a11y[:max_chars] + "\n<!-- a11y truncated -->"

    lines = a11y.splitlines()
    keep_idx = set()
    lower_labels = [lab.lower() for lab in labels]
    for i, line in enumerate(lines):
        low = line.lower()
        if any(lab in low for lab in lower_labels):
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                keep_idx.add(j)

    prioritized = [lines[i] for i in sorted(keep_idx)]
    prioritized_text = "\n".join(prioritized)
    if len(prioritized_text) >= max_chars:
        return prioritized_text[:max_chars] + "\n<!-- a11y truncated -->"

    remaining = max_chars - len(prioritized_text) - 40
    prefix_parts: List[str] = []
    used = 0
    for i, line in enumerate(lines):
        if i in keep_idx:
            continue
        if used + len(line) + 1 > remaining:
            break
        prefix_parts.append(line)
        used += len(line) + 1
    merged = "\n".join(prefix_parts + ["<!-- priority a11y matches -->"] + prioritized)
    if len(merged) > max_chars:
        merged = merged[:max_chars] + "\n<!-- a11y truncated -->"
    return merged


def build_llm_dom_context(
    *,
    html: str = "",
    accessibility_tree: str = "",
    priority_labels: Sequence[str] = (),
    max_elements: int = 80,
    max_html_chars: int = 40_000,
    max_a11y_chars: int = 8_000,
) -> str:
    """Build an app-agnostic DOM section for LLM prompts."""
    parts: List[str] = []
    labels = [lab.strip() for lab in priority_labels if lab and str(lab).strip()]
    elements = extract_interactive_elements(html) if html else []
    ranked = rank_elements_for_prompt(
        elements, priority_labels=labels, max_elements=max_elements
    )

    if ranked:
        parts.append("## Interactive elements extracted from live HTML")
        parts.append(
            "Use these REAL attributes and preferred_locator values verbatim. "
            "Do NOT invent data-testid/id/name values that are not listed. "
            "preferred_locator is pre-chosen for uniqueness (reduces strict-mode risk). "
            "Map includes forms, tables/grids, iframes, dialogs, tabs/menus, and chart hooks."
        )
        if labels:
            parts.append(f"Priority labels from the manual test: {', '.join(labels[:20])}")
        for el in ranked:
            parts.append(f"- {el.summary_line(include_locator=True)}")
        omitted = max(0, len(elements) - len(ranked))
        if omitted:
            parts.append(f"- ... ({omitted} more interactive elements omitted after relevance ranking)")
        parts.append("")

    if html:
        parts.append("## Live HTML DOM (scripts/styles stripped; relevance-prioritized)")
        parts.append(
            _html_slice_for_prompt(html, ranked=ranked, max_chars=max_html_chars)
        )
        parts.append("")

    if accessibility_tree:
        parts.append("## Accessibility tree (roles / visible names)")
        parts.append(
            _a11y_slice_for_prompt(
                accessibility_tree,
                priority_labels=labels,
                max_chars=max_a11y_chars,
            )
        )
        parts.append("")

    if not parts:
        return ""

    parts.append("## DOM grounding rules")
    parts.append(
        "1. Prefer preferred_locator from the interactive map when present "
        "(data-testid > id/name > placeholder/aria-label > role+name)"
    )
    parts.append("2. Copy attribute values EXACTLY from the snapshot (case-sensitive for id/name)")
    parts.append("3. If an attribute is missing, do not invent it")
    parts.append("4. For buttons, match visible name/value from the snapshot (e.g. LOGIN vs Login)")
    parts.append(
        "5. Prefer unique locators; avoid page-wide get_by_text / bare role clicks that match many nodes"
    )
    parts.append(
        "6. Use the matching widget type (table/grid/iframe/dialog/tab/chart) — "
        "do not assume login-only controls"
    )
    return "\n".join(parts).strip()


def combine_inspection_for_prompt(
    html: str,
    accessibility_tree: str,
    priority_labels: Sequence[str] = (),
) -> str:
    """Compatibility helper: single string snapshot for callers expecting str."""
    return build_llm_dom_context(
        html=html,
        accessibility_tree=accessibility_tree,
        priority_labels=priority_labels,
    )
