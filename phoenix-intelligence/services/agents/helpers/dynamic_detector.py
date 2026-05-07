"""Dynamic element detector — identifies elements requiring multi-step interaction.

Analyses HTML/DOM input and tags elements that need open→wait→interact sequences:
  - Custom dropdowns (aria-expanded, role=combobox, role=listbox)
  - Nested menus (aria-haspopup, sub-menu patterns)
  - Date pickers (input[type=date], calendar widgets)
  - Disclosure/accordion panels (aria-controls, hidden siblings)
  - Modals/dialogs
  - Shopify disclosure patterns

The returned DynamicElementProfile is injected into automation agent prompts so the
LLM knows which interaction pattern to generate for each detected element type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DynamicType(str, Enum):
    CUSTOM_DROPDOWN = "custom_dropdown"
    NESTED_MENU = "nested_menu"
    DATE_PICKER = "date_picker"
    DISCLOSURE = "disclosure"
    MODAL = "modal"
    FILE_INPUT = "file_input"
    STANDARD = "standard"


@dataclass
class DynamicElement:
    element_type: DynamicType
    trigger_hint: str
    interaction_pattern: str
    confidence: float = 1.0


@dataclass
class DynamicElementProfile:
    """Aggregated detection results for a page/HTML snippet."""

    has_custom_dropdowns: bool = False
    has_nested_menus: bool = False
    has_date_pickers: bool = False
    has_disclosures: bool = False
    has_modals: bool = False
    elements: list[DynamicElement] = field(default_factory=list)

    def as_prompt_context(self) -> str:
        """Return a short instruction block to inject into the LLM system prompt."""
        if not self.elements:
            return ""

        lines = ["## Dynamic Element Patterns Detected\n"]
        if self.has_custom_dropdowns:
            lines.append(
                "- **Custom dropdowns present**: use `get_by_role('combobox', name=...)."
                "click()` then `get_by_role('option', name=...).click()`. "
                "Never use `get_by_label` or `select_option()` for these.\n"
            )
        if self.has_nested_menus:
            lines.append(
                "- **Nested menus present**: click the parent menu item first, "
                "then click the child item after it becomes visible.\n"
            )
        if self.has_date_pickers:
            lines.append(
                "- **Date pickers present**: click the date input field to open the calendar, "
                "wait for it to become visible, then click the date value.\n"
            )
        if self.has_disclosures:
            lines.append(
                "- **Disclosure/accordion patterns present**: click the trigger button "
                "(usually `<button aria-expanded>` or `button[aria-controls=...]`) first, "
                "then interact with the revealed content.\n"
            )
        if self.has_modals:
            lines.append(
                "- **Modals/dialogs present**: wait for `get_by_role('dialog')` to be visible "
                "before interacting with elements inside it.\n"
            )
        return "".join(lines)


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

_COMBOBOX_RE = re.compile(r'role=["\']combobox["\']', re.IGNORECASE)
_LISTBOX_RE = re.compile(r'role=["\']listbox["\']', re.IGNORECASE)
_ARIA_EXPANDED_RE = re.compile(r'aria-expanded=["\']', re.IGNORECASE)
_ARIA_HASPOPUP_RE = re.compile(r'aria-haspopup=["\']', re.IGNORECASE)
_ARIA_CONTROLS_RE = re.compile(r'aria-controls=["\']', re.IGNORECASE)
_DATE_INPUT_RE = re.compile(r'type=["\']date["\']', re.IGNORECASE)
_CALENDAR_CLASS_RE = re.compile(
    r'class=["\'][^"\']*(?:date-?picker|calendar|datepicker|oxd-date)[^"\']*["\']',
    re.IGNORECASE,
)
_DIALOG_RE = re.compile(r'role=["\']dialog["\']|<dialog[\s>]', re.IGNORECASE)
_FILE_INPUT_RE = re.compile(r'type=["\']file["\']', re.IGNORECASE)
_SHOPIFY_DISCLOSURE_RE = re.compile(r'disclosure__list|disclosure-list', re.IGNORECASE)
_SELECT_RE = re.compile(r'<select[\s>]', re.IGNORECASE)
_OXD_SELECT_RE = re.compile(r'oxd-select|oxd-autocomplete', re.IGNORECASE)


def detect(html_or_dom: Optional[str]) -> DynamicElementProfile:
    """Analyse an HTML/DOM string and return a DynamicElementProfile.

    Args:
        html_or_dom: Raw HTML string or a DOM snapshot. Pass None to get an empty profile.

    Returns:
        DynamicElementProfile with detected element types and prompt injection text.
    """
    profile = DynamicElementProfile()
    if not html_or_dom:
        return profile

    html = html_or_dom

    # Custom dropdowns — combobox role, aria-expanded, listbox, OrangeHRM-style
    if (
        _COMBOBOX_RE.search(html)
        or _LISTBOX_RE.search(html)
        or _OXD_SELECT_RE.search(html)
        or (_ARIA_EXPANDED_RE.search(html) and not _SELECT_RE.search(html))
    ):
        profile.has_custom_dropdowns = True
        profile.elements.append(
            DynamicElement(
                element_type=DynamicType.CUSTOM_DROPDOWN,
                trigger_hint="get_by_role('combobox', name=LABEL).click()",
                interaction_pattern=(
                    "# Open the custom dropdown\n"
                    "page.get_by_role('combobox', name='LABEL').click()\n"
                    "# Wait for options to appear\n"
                    "expect(page.get_by_role('listbox')).to_be_visible()\n"
                    "# Select the option\n"
                    "page.get_by_role('option', name='OPTION').click()"
                ),
            )
        )

    # Nested menus — aria-haspopup
    if _ARIA_HASPOPUP_RE.search(html):
        profile.has_nested_menus = True
        profile.elements.append(
            DynamicElement(
                element_type=DynamicType.NESTED_MENU,
                trigger_hint="click parent menu item first",
                interaction_pattern=(
                    "# Click the parent menu to expand\n"
                    "page.get_by_role('link', name='PARENT_MENU').click()\n"
                    "# Wait for sub-menu to appear\n"
                    "expect(page.get_by_role('link', name='CHILD_ITEM')).to_be_visible()\n"
                    "page.get_by_role('link', name='CHILD_ITEM').click()"
                ),
            )
        )

    # Date pickers
    if _DATE_INPUT_RE.search(html) or _CALENDAR_CLASS_RE.search(html):
        profile.has_date_pickers = True
        profile.elements.append(
            DynamicElement(
                element_type=DynamicType.DATE_PICKER,
                trigger_hint="click date input to open calendar",
                interaction_pattern=(
                    "# Click the date input to open the calendar widget\n"
                    "page.locator('input.DATE_INPUT_CLASS').click()\n"
                    "# Wait for calendar to be visible\n"
                    "expect(page.locator('.calendar-widget')).to_be_visible()\n"
                    "# Click the target date\n"
                    "page.get_by_text('DD', exact=True).click()"
                ),
            )
        )

    # Disclosure / accordion (Shopify patterns, generic aria-controls)
    if _SHOPIFY_DISCLOSURE_RE.search(html) or _ARIA_CONTROLS_RE.search(html):
        profile.has_disclosures = True
        profile.elements.append(
            DynamicElement(
                element_type=DynamicType.DISCLOSURE,
                trigger_hint="click button[aria-controls=...] trigger",
                interaction_pattern=(
                    "# Click the disclosure trigger button\n"
                    "page.locator(\"button[aria-controls='PANEL_ID']\").click()\n"
                    "# Wait for content to become visible\n"
                    "expect(page.locator('#PANEL_ID')).to_be_visible()\n"
                    "# Interact with revealed content\n"
                    "page.get_by_role('option', name='OPTION').click()"
                ),
            )
        )

    # Modals / dialogs
    if _DIALOG_RE.search(html):
        profile.has_modals = True
        profile.elements.append(
            DynamicElement(
                element_type=DynamicType.MODAL,
                trigger_hint="wait for role=dialog before interacting",
                interaction_pattern=(
                    "# Wait for the modal to appear\n"
                    "dialog = page.get_by_role('dialog')\n"
                    "expect(dialog).to_be_visible()\n"
                    "# Interact within the modal scope\n"
                    "dialog.get_by_role('button', name='CONFIRM').click()\n"
                    "# Wait for modal to close\n"
                    "expect(dialog).to_be_hidden()"
                ),
            )
        )

    return profile
