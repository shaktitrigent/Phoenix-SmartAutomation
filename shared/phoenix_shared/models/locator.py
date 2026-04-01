"""Locator Pydantic models."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel


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
    element_name: str
    strategy: LocatorStrategy
    value: str
    confidence: float = 1.0
    fallback: bool = False
    description: Optional[str] = None
