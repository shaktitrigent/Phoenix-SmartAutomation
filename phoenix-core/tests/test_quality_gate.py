"""Regression tests for the QualityGate."""

import pytest

from phoenix.models.intent import ActionType, ParsedTestCase, SemanticIntent
from phoenix.validation.quality_gate import QualityGate


@pytest.fixture
def gate():
    return QualityGate()


def _make_step(**kwargs) -> SemanticIntent:
    defaults = {
        "raw_text": "some step",
        "intent_type": "action",
        "action": ActionType.CLICK,
        "confidence": 0.9,
    }
    defaults.update(kwargs)
    return SemanticIntent(**defaults)


def _make_case(steps, title="Test Case") -> ParsedTestCase:
    return ParsedTestCase(title=title, steps=steps)


class TestQualityGateManualReviewMarker:
    def test_blocks_manual_review_in_raw_text(self, gate):
        step = _make_step(raw_text="[NEEDS MANUAL REVIEW] Click something")
        tc = _make_case([step])
        result = gate.validate(tc)
        assert result.passed is False
        assert any("manual_review_marker" in e for e in result.blocking_errors)

    def test_blocks_manual_review_lowercase(self, gate):
        step = _make_step(raw_text="[needs manual review] Some step")
        tc = _make_case([step])
        result = gate.validate(tc)
        assert result.passed is False


class TestQualityGateUnknownActions:
    def test_blocks_unknown_action(self, gate):
        step = _make_step(action=ActionType.UNKNOWN, raw_text="frobnicate the quux", confidence=0.9)
        tc = _make_case([step])
        result = gate.validate(tc)
        assert result.passed is False
        assert any("has_unknown_actions" in e for e in result.blocking_errors)


class TestQualityGateUnresolvedLocators:
    def test_blocks_click_without_element(self, gate):
        step = _make_step(
            action=ActionType.CLICK,
            target_element=None,
            target_locator=None,
            confidence=0.9,
        )
        tc = _make_case([step])
        result = gate.validate(tc)
        assert result.passed is False
        assert any("has_unresolved_locators" in e for e in result.blocking_errors)

    def test_allows_click_with_element(self, gate):
        step = _make_step(
            action=ActionType.CLICK,
            target_element="submit_button",
            confidence=0.9,
        )
        tc = _make_case([step])
        result = gate.validate(tc)
        # No unresolved locator blocking error
        assert not any("has_unresolved_locators" in e for e in result.blocking_errors)


class TestQualityGateInvalidURLAssertions:
    def test_blocks_business_text_url_assertion(self, gate):
        step = _make_step(
            action=ActionType.ASSERT_URL,
            expected_state="Apply Leave page is visible",
            intent_type="assertion",
            confidence=0.9,
        )
        tc = _make_case([step])
        result = gate.validate(tc)
        assert result.passed is False
        assert any("has_invalid_assertions" in e for e in result.blocking_errors)

    def test_allows_real_url_path(self, gate):
        step = _make_step(
            action=ActionType.ASSERT_URL,
            expected_state=".*/leave/apply",
            intent_type="assertion",
            confidence=0.9,
        )
        tc = _make_case([step])
        result = gate.validate(tc)
        assert not any("has_invalid_assertions" in e for e in result.blocking_errors)

    def test_blocks_should_be_displayed_as_url(self, gate):
        step = _make_step(
            action=ActionType.ASSERT_URL,
            expected_state="Dashboard should be displayed",
            intent_type="assertion",
            confidence=0.9,
        )
        tc = _make_case([step])
        result = gate.validate(tc)
        assert not result.passed


class TestQualityGateConfidenceThreshold:
    def test_blocks_low_confidence(self, gate):
        step = _make_step(action=ActionType.NAVIGATE, target_page="home", confidence=0.3)
        tc = _make_case([step])
        result = gate.validate(tc)
        assert any("confidence_below_threshold" in e for e in result.blocking_errors)

    def test_passes_high_confidence(self, gate):
        step = _make_step(action=ActionType.NAVIGATE, target_page="login", confidence=0.95)
        tc = _make_case([step])
        result = gate.validate(tc)
        assert not any("confidence_below_threshold" in e for e in result.blocking_errors)


class TestQualityGatePassingCase:
    def test_valid_case_passes(self, gate):
        steps = [
            SemanticIntent(
                raw_text="Navigate to the Login page",
                intent_type="precondition",
                action=ActionType.NAVIGATE,
                target_page="login",
                confidence=0.95,
            ),
            SemanticIntent(
                raw_text="Click the Login button",
                intent_type="action",
                action=ActionType.CLICK,
                target_element="login_button",
                confidence=0.90,
            ),
            SemanticIntent(
                raw_text="The dashboard should be visible",
                intent_type="assertion",
                action=ActionType.ASSERT_VISIBLE,
                expected_state="dashboard",
                confidence=0.80,
            ),
        ]
        tc = _make_case(steps)
        result = gate.validate(tc)
        assert result.passed is True
        assert result.blocking_errors == []
