"""Example Playwright test for orhrm — delete or adapt as needed."""

import pytest
from playwright.sync_api import Page, expect


def test_homepage_loads(page: Page, base_url: str) -> None:
    """Verify the application home page is reachable."""
    page.goto(base_url)
    expect(page).not_to_have_title("")


def test_login_page_visible(page: Page, base_url: str) -> None:
    """Verify the login page renders key elements."""
    page.goto(base_url)
    # Adjust selectors to match your application
    expect(page.get_by_role("button", name="Login")).to_be_visible()
