"""Page-specific locator and action mappings."""

from __future__ import annotations

from typing import Dict

from phoenix.mappings.pages.base_page import PAGE_MAPPING as _BASE
from phoenix.mappings.pages.employee_page import PAGE_MAPPING as _EMPLOYEE
from phoenix.mappings.pages.leave_page import PAGE_MAPPING as _LEAVE
from phoenix.mappings.pages.login_page import PAGE_MAPPING as _LOGIN

_REGISTRY: Dict[str, Dict] = {
    "login": _LOGIN,
    "employee": _EMPLOYEE,
    "add_employee": _EMPLOYEE,
    "employee_list": _EMPLOYEE,
    "leave": _LEAVE,
    "apply_leave": _LEAVE,
    "leave_application": _LEAVE,
    "global": _BASE,
}


def get_page_mapping(page_name: str) -> Dict:
    """Return the page mapping for *page_name*, falling back to base."""
    key = page_name.lower().replace(" ", "_").replace("-", "_")
    return _REGISTRY.get(key, _BASE)


def list_known_pages() -> list:
    return sorted(_REGISTRY.keys())
