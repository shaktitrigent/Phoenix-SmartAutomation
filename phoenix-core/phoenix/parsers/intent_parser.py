"""Intent Parser — converts business-language test steps into SemanticIntent objects.

Handles Gherkin (Given/When/Then), plain English, and Markdown table row formats.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from phoenix.models.intent import ActionType, ParsedTestCase, SemanticIntent


# ---------------------------------------------------------------------------
# Keyword strippers
# ---------------------------------------------------------------------------

_GHERKIN_PREFIX = re.compile(
    r"^\s*(?:given|when|then|and|but)\s+", re.IGNORECASE
)

_STEP_KEYWORDS = re.compile(
    r"^\s*(?:step\s*\d+\s*[-:.]?\s*)", re.IGNORECASE
)


def _strip_keyword(text: str) -> str:
    text = _GHERKIN_PREFIX.sub("", text)
    text = _STEP_KEYWORDS.sub("", text)
    return text.strip()


def _detect_intent_type(raw: str) -> str:
    lower = raw.lower()
    if re.match(r"^\s*(given|i am on|navigate to|open|visit|log ?in|sign ?in)", lower):
        return "precondition"
    assertion_patterns = (
        "should", "must", "verify", "assert", "confirm",
        "is displayed", "is visible", "should be", "is shown",
        "appear", "contains", "has text", "have text",
    )
    if any(p in lower for p in assertion_patterns):
        return "assertion"
    return "action"


# ---------------------------------------------------------------------------
# Navigation patterns
# ---------------------------------------------------------------------------

_NAV_PATTERNS: List[tuple] = [
    (
        re.compile(
            r"(?:go\s+to|navigate\s+to|open|visit|am\s+on(?:\s+the)?|on\s+the)\s+"
            r"(?:the\s+)?['\"]?(.+?)['\"]?\s*(?:page|screen|view|module)?$",
            re.IGNORECASE,
        ),
        ActionType.NAVIGATE,
    ),
    (
        re.compile(
            r"(?:i\s+am\s+on|i\s+navigate\s+to)\s+(?:the\s+)?['\"]?(.+?)['\"]?\s*(?:page)?$",
            re.IGNORECASE,
        ),
        ActionType.NAVIGATE,
    ),
]

# ---------------------------------------------------------------------------
# Action patterns  (order matters — more specific first)
# ---------------------------------------------------------------------------

_ACTION_PATTERNS: List[tuple] = [
    # Login shorthand
    (
        re.compile(
            r"(?:log\s*in|sign\s*in)\s+(?:with|using)?\s*"
            r"(?:valid\s+)?(?:credentials|username|admin|user)?",
            re.IGNORECASE,
        ),
        ActionType.FILL,
        "login_form",
    ),
    # Fill / enter / type / input
    (
        re.compile(
            r"(?:enter|fill|type|input|set|provide)\s+"
            r"(?:the\s+|a\s+|an\s+)?['\"]?(.+?)['\"]?\s+"
            r"(?:in(?:to)?\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s*"
            r"(?:field|input|box|area|textbox)?$",
            re.IGNORECASE,
        ),
        ActionType.FILL,
        None,
    ),
    # Select / choose from dropdown
    (
        re.compile(
            r"(?:select|choose|pick)\s+(?:a\s+|an\s+|the\s+)?['\"]?(.+?)['\"]?\s+"
            r"(?:from\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s*"
            r"(?:dropdown|list|menu|combobox|option)?$",
            re.IGNORECASE,
        ),
        ActionType.SELECT,
        None,
    ),
    # Click button / link / tab
    (
        re.compile(
            r"click\s+(?:on\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s*"
            r"(?:button|link|tab|icon|element)?$",
            re.IGNORECASE,
        ),
        ActionType.CLICK,
        None,
    ),
    # Wait
    (
        re.compile(r"wait\s+(?:for\s+)?(.+)$", re.IGNORECASE),
        ActionType.WAIT,
        None,
    ),
]

# ---------------------------------------------------------------------------
# Assertion patterns
# ---------------------------------------------------------------------------

_ASSERT_PATTERNS: List[tuple] = [
    # URL assertion
    (
        re.compile(
            r"(?:url|address|page)\s+(?:should\s+)?(?:be|contain|match|show)\s+"
            r"['\"]?(.+?)['\"]?$",
            re.IGNORECASE,
        ),
        ActionType.ASSERT_URL,
    ),
    # Text assertion
    (
        re.compile(
            r"(?:should\s+(?:contain|have|show)\s+text|text\s+should\s+be)\s+"
            r"['\"]?(.+?)['\"]?$",
            re.IGNORECASE,
        ),
        ActionType.ASSERT_TEXT,
    ),
    # Success / error message assertion
    (
        re.compile(
            r"(?:success|confirmation|error|warning|alert|message|notification)\s+"
            r"(?:should\s+be\s+(?:displayed|visible|shown)|is\s+(?:displayed|visible))",
            re.IGNORECASE,
        ),
        ActionType.ASSERT_VISIBLE,
    ),
    # Generic visible assertion
    (
        re.compile(
            r"(?:should\s+be\s+(?:displayed|visible|shown)|is\s+(?:displayed|visible))",
            re.IGNORECASE,
        ),
        ActionType.ASSERT_VISIBLE,
    ),
]

# ---------------------------------------------------------------------------
# Page name normaliser
# ---------------------------------------------------------------------------

_PAGE_NORMALISE = re.compile(r"\s+")
_PAGE_NOISE = re.compile(
    r"\b(?:the|a|an|page|screen|view|module)\b", re.IGNORECASE
)


def _normalise_page(raw: str) -> str:
    name = _PAGE_NOISE.sub("", raw).strip()
    name = _PAGE_NORMALISE.sub("_", name.lower()).strip("_")
    return re.sub(r"_+", "_", name)


# ---------------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------------

class IntentParser:
    """Parses business-language test steps into SemanticIntent objects."""

    CONFIDENCE_FULL = 0.95
    CONFIDENCE_PARTIAL = 0.70
    CONFIDENCE_LOW = 0.30

    def parse_step(
        self, raw_text: str, context: Optional[Dict] = None
    ) -> SemanticIntent:
        context = context or {}
        stripped = _strip_keyword(raw_text)
        intent_type = _detect_intent_type(raw_text)
        errors: List[str] = []

        # Manual review markers → immediately flag
        if "[needs manual review]" in raw_text.lower() or "[manual review]" in raw_text.lower():
            return SemanticIntent(
                raw_text=raw_text,
                intent_type=intent_type,
                action=ActionType.UNKNOWN,
                confidence=0.0,
                requires_review=True,
                validation_errors=["Step contains [NEEDS MANUAL REVIEW] marker — cannot automate"],
            )

        # Try navigation
        for pattern, action in _NAV_PATTERNS:
            m = pattern.search(stripped)
            if m:
                page_raw = m.group(1).strip()
                return SemanticIntent(
                    raw_text=raw_text,
                    intent_type="precondition",
                    action=action,
                    target_page=_normalise_page(page_raw),
                    confidence=self.CONFIDENCE_FULL,
                )

        # Try assertions
        for pattern, action in _ASSERT_PATTERNS:
            m = pattern.search(stripped)
            if m:
                groups = m.groups()
                expected = groups[0].strip() if groups else stripped
                return SemanticIntent(
                    raw_text=raw_text,
                    intent_type="assertion",
                    action=action,
                    expected_state=expected,
                    confidence=self.CONFIDENCE_PARTIAL,
                )

        # Try actions
        for pattern, action, default_element in _ACTION_PATTERNS:
            m = pattern.search(stripped)
            if m:
                groups = m.groups()
                element = None
                value = None
                if action == ActionType.FILL and default_element == "login_form":
                    element = "login_form"
                    confidence = self.CONFIDENCE_FULL
                elif action in (ActionType.FILL, ActionType.SELECT) and len(groups) >= 2:
                    value = groups[0].strip()
                    element = groups[1].strip().lower().replace(" ", "_") if groups[1] else None
                    confidence = self.CONFIDENCE_PARTIAL
                elif action == ActionType.CLICK and groups:
                    element = groups[0].strip().lower().replace(" ", "_")
                    confidence = self.CONFIDENCE_PARTIAL
                else:
                    element = groups[0].strip() if groups else None
                    confidence = self.CONFIDENCE_PARTIAL

                if action in (ActionType.FILL, ActionType.SELECT, ActionType.CLICK) and not element:
                    errors.append(f"Could not resolve target element from: {raw_text!r}")

                return SemanticIntent(
                    raw_text=raw_text,
                    intent_type=intent_type,
                    action=action,
                    target_element=element,
                    input_value=value,
                    confidence=confidence,
                    validation_errors=errors,
                )

        # No pattern matched
        return SemanticIntent(
            raw_text=raw_text,
            intent_type=intent_type,
            action=ActionType.UNKNOWN,
            confidence=self.CONFIDENCE_LOW,
            requires_review=True,
            validation_errors=[f"No pattern matched for step: {raw_text!r}"],
        )

    def parse_test_case(
        self,
        steps: List[str],
        metadata: Optional[Dict] = None,
    ) -> ParsedTestCase:
        metadata = metadata or {}
        title = metadata.get("name", metadata.get("title", "Unnamed Test"))
        tc_id = metadata.get("case_id", metadata.get("id", ""))

        parsed_steps = [self.parse_step(s, context=metadata) for s in steps]

        # Detect source format from first step
        source_format: str = "plain_english"
        if steps and re.match(r"^\s*(given|when|then)\b", steps[0], re.IGNORECASE):
            source_format = "gherkin"

        return ParsedTestCase(
            id=tc_id,
            title=title,
            source_format=source_format,  # type: ignore[arg-type]
            steps=parsed_steps,
        )
