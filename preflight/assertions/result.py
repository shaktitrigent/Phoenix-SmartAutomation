from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal


@dataclass
class AssertionResult:
    tier: Literal["T1", "T2", "T3"]
    name: str
    passed: bool
    detail: str = ""      # concrete evidence on failure (file/line, selector, error)
    data: Dict[str, Any] = field(default_factory=dict)
