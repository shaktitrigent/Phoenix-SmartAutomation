"""Locator Pydantic models — single locator and multi-locator bundle."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class LocatorStrategy(str, Enum):
    ROLE = "role"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    TEST_ID = "test-id"
    TEXT = "text"
    CSS = "css"
    XPATH = "xpath"
    ALT_TEXT = "alt-text"
    TITLE = "title"


class Locator(BaseModel):
    """A single locator expression for a UI element."""

    element_name: str
    strategy: LocatorStrategy
    value: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    fallback: bool = False
    description: Optional[str] = None

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def to_playwright(self) -> str:
        """Render this locator as a Playwright Python expression."""
        strategy_map = {
            LocatorStrategy.ROLE: lambda: f'page.get_by_role("{self.value}")',
            LocatorStrategy.LABEL: lambda: f'page.get_by_label("{self.value}")',
            LocatorStrategy.PLACEHOLDER: lambda: f'page.get_by_placeholder("{self.value}")',
            LocatorStrategy.TEST_ID: lambda: f'page.get_by_test_id("{self.value}")',
            LocatorStrategy.TEXT: lambda: f'page.get_by_text("{self.value}")',
            LocatorStrategy.CSS: lambda: f'page.locator("{self.value}")',
            LocatorStrategy.XPATH: lambda: f'page.locator("{self.value}")',
            LocatorStrategy.ALT_TEXT: lambda: f'page.get_by_alt_text("{self.value}")',
            LocatorStrategy.TITLE: lambda: f'page.get_by_title("{self.value}")',
        }
        fn = strategy_map.get(self.strategy)
        return fn() if fn else f'page.locator("{self.value}")'


class LocatorBundle(BaseModel):
    """Multi-locator bundle for a single UI element.

    Stores a primary locator plus 2+ ranked alternates so that automation
    scripts can fall back gracefully when the primary locator fails (e.g.,
    after a DOM change).

    Usage pattern in a Playwright test::

        bundle = registry.get("login_button")
        for loc in bundle.ordered():
            try:
                page.locator(loc.value).click()
                break
            except Exception:
                continue
    """

    element_name: str
    page: str = Field(default="global", description="Logical page/section this element belongs to")
    primary: Locator
    alternates: List[Locator] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("alternates", mode="before")
    @classmethod
    def mark_alternates_as_fallback(cls, v: List) -> List:
        result = []
        for item in v:
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("fallback", True)
            elif isinstance(item, Locator):
                item = item.model_copy(update={"fallback": True})
            result.append(item)
        return result

    def ordered(self) -> List[Locator]:
        """Return all locators sorted by confidence (primary first)."""
        all_locs = [self.primary] + self.alternates
        return sorted(all_locs, key=lambda loc: loc.confidence, reverse=True)

    def best(self) -> Locator:
        """Return the highest-confidence locator."""
        return self.ordered()[0]

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "LocatorBundle":
        return cls.model_validate(data)
