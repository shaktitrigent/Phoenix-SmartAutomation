"""AutomationScript Pydantic model."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

from phoenix_shared.models.locator import Locator


class AutomationScript(BaseModel):
    name: str
    description: str
    script_content: str
    script_path: Optional[str] = None
    locators: List[Locator] = []
    imports: List[str] = []
    framework: str = "playwright"
    language: str = "python"
