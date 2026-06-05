"""Deterministic Action Registry.

Provides pattern-based mappings for common UI actions, avoiding LLM inference
for well-understood patterns. Each pattern maps to an (ActionType, element_hint,
playwright_template, confidence) tuple.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from phoenix.models.intent import ActionType


class ActionRegistry:
    """Deterministic mappings for common UI actions.

    Match order is significant — more specific patterns must appear first.
    """

    # (compiled_pattern, ActionType, element_hint_template, playwright_template, confidence)
    PATTERNS: List[Tuple] = [
        # ── Navigation ──────────────────────────────────────────────────────
        (
            re.compile(
                r"(?:go\s+to|navigate\s+to|open|visit)\s+(?:the\s+)?(.+?)\s*(?:page)?$",
                re.IGNORECASE,
            ),
            ActionType.NAVIGATE,
            "{page}",
            'await page.goto(config.BASE_URL + "/{page}")',
            0.90,
        ),
        # ── Login shorthand ──────────────────────────────────────────────────
        (
            re.compile(
                r"(?:log\s*in|sign\s*in)\s+(?:with|using)?\s*"
                r"(?:valid\s+)?(?:credentials|username|admin|user)?",
                re.IGNORECASE,
            ),
            ActionType.FILL,
            "login_form",
            (
                'await page.get_by_label("Username").fill(test_data["username"])\n'
                'await page.get_by_label("Password").fill(test_data["password"])\n'
                'await page.get_by_role("button", name="Login").click()'
            ),
            0.95,
        ),
        # ── Click ────────────────────────────────────────────────────────────
        (
            re.compile(
                r"click\s+(?:on\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s*"
                r"(?:button|link|tab|icon|element)?$",
                re.IGNORECASE,
            ),
            ActionType.CLICK,
            "{element}",
            'await page.get_by_role("button", name="{element}").click()',
            0.80,
        ),
        # ── Fill / type ──────────────────────────────────────────────────────
        (
            re.compile(
                r"(?:enter|fill|type|input)\s+['\"]?(.+?)['\"]?\s+"
                r"(?:in(?:to)?\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s*"
                r"(?:field|input|box)?$",
                re.IGNORECASE,
            ),
            ActionType.FILL,
            "{field}",
            'await page.get_by_label("{field}").fill("{value}")',
            0.80,
        ),
        # ── Date picker ──────────────────────────────────────────────────────
        (
            re.compile(
                r"select\s+(?:a\s+)?(?:future\s+)?(?:date|from\s*date|to\s*date)\s*"
                r"['\"]?(.+?)?['\"]?$",
                re.IGNORECASE,
            ),
            ActionType.SELECT,
            "date_picker",
            (
                'await page.get_by_label("{field}").click()\n'
                'await page.get_by_role("gridcell", name="{date}").click()'
            ),
            0.75,
        ),
        # ── Select / choose from dropdown ────────────────────────────────────
        (
            re.compile(
                r"(?:select|choose|pick)\s+(?:a\s+|an\s+|the\s+)?['\"]?(.+?)['\"]?\s+"
                r"(?:from\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s*"
                r"(?:dropdown|list|menu|combobox|option)?$",
                re.IGNORECASE,
            ),
            ActionType.SELECT,
            "{field}",
            'await page.get_by_label("{field}").select_option("{value}")',
            0.80,
        ),
        # ── Assert visible ───────────────────────────────────────────────────
        (
            re.compile(
                r"(?:should\s+(?:be\s+)?(?:displayed|visible|shown)|is\s+(?:displayed|visible))",
                re.IGNORECASE,
            ),
            ActionType.ASSERT_VISIBLE,
            None,
            'await expect(page.locator("{element}")).to_be_visible()',
            0.70,
        ),
        # ── Assert text ──────────────────────────────────────────────────────
        (
            re.compile(
                r"(?:should\s+(?:contain|have|show)\s+text|text\s+should\s+be)\s+"
                r"['\"]?(.+?)['\"]?$",
                re.IGNORECASE,
            ),
            ActionType.ASSERT_TEXT,
            None,
            'await expect(page.locator("{element}")).to_contain_text("{text}")',
            0.75,
        ),
        # ── Assert URL ───────────────────────────────────────────────────────
        (
            re.compile(
                r"(?:url|address)\s+(?:should\s+)?(?:be|contain|match)\s+"
                r"['\"]?(.+?)['\"]?$",
                re.IGNORECASE,
            ),
            ActionType.ASSERT_URL,
            None,
            'await expect(page).to_have_url(re.compile(r".*{path}.*"))',
            0.70,
        ),
    ]

    def match(
        self, text: str
    ) -> Optional[Tuple[ActionType, str, str, float]]:
        """Match text against patterns.

        Returns:
            (ActionType, element_hint, playwright_template, confidence) or None.
        """
        for pattern, action, element_hint, template, confidence in self.PATTERNS:
            m = pattern.search(text)
            if m:
                groups = m.groups()
                hint = element_hint or ""
                if groups and "{element}" in hint:
                    hint = hint.replace("{element}", groups[0].strip())
                elif groups and "{field}" in hint and len(groups) >= 2:
                    hint = hint.replace("{field}", groups[1].strip())
                elif groups and "{page}" in hint:
                    hint = hint.replace("{page}", groups[0].strip())
                return (action, hint, template, confidence)
        return None

    def get_page_mapping(self, page_name: str) -> Dict:
        """Return known locators and actions for a page by name."""
        from phoenix.mappings.pages import get_page_mapping as _get
        return _get(page_name)
