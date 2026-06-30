"""ManualTestTc001LoginSuccessPage — synthesized by phoenix automate (pom mode)."""
from __future__ import annotations

import os
import re
from playwright.sync_api import Locator, Page, expect
from pages.base_page import BasePage


ACTION_TIMEOUT_MS = 30_000
NAVIGATION_TIMEOUT_MS = 60_000
ASSERTION_TIMEOUT_MS = 15_000
OVERLAY_SELECTORS = [
    "[role='dialog']",
    "[aria-modal='true']",
    "[data-testid*='modal']",
    "[data-testid*='overlay']",
    "[class*='modal']",
    "[class*='overlay']",
    "[class*='backdrop']",
]


def configure_page(page: Page) -> None:
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)


def dismiss_known_overlays(page: Page) -> None:
    for selector in OVERLAY_SELECTORS:
        overlay = page.locator(selector)
        try:
            if overlay.count() == 0:
                continue
            close_button = overlay.get_by_role(
                "button",
                name=re.compile(r"close|dismiss|cancel|not now|skip|got it", re.IGNORECASE),
            ).first
            if close_button.is_visible(timeout=1_000):
                close_button.click(timeout=2_000)
        except Exception:
            continue
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def unique_visible(locator: Locator, description: str) -> Locator:
    expect(locator).to_have_count(1, timeout=ASSERTION_TIMEOUT_MS)
    expect(locator).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)
    return locator


def click_ready(page: Page, locator: Locator, description: str) -> None:
    dismiss_known_overlays(page)
    target = unique_visible(locator, description)
    expect(target).to_be_enabled(timeout=ASSERTION_TIMEOUT_MS)
    target.scroll_into_view_if_needed()
    target.click(timeout=ACTION_TIMEOUT_MS)


def fill_ready(page: Page, locator: Locator, value: str, description: str) -> None:
    dismiss_known_overlays(page)
    target = unique_visible(locator, description)
    target.scroll_into_view_if_needed()
    target.fill(value, timeout=ACTION_TIMEOUT_MS)


def expect_url_path(page: Page, path_fragment: str) -> None:
    expect(
        page,
    ).to_have_url(
        re.compile(rf".*{re.escape(path_fragment.strip('/'))}.*"),
        timeout=NAVIGATION_TIMEOUT_MS,
    )


class SuccessfulLoginWithValidCredentialsPage(BasePage):
    """Page object for manual_test_tc001_login_success tests."""

    URL_PATH = ""

    def tc_001_successful_login_with_valid_crede(self) -> None:
        """tc 001 successful login with valid crede."""
        configure_page(self._page)
        dismiss_known_overlays(self._page)
        # --- Step 1: Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login and log in with username "Admin" and password "admin123" ---
        fill_ready(self._page, self._page.locator("input[name='username']"), "Admin", "Username input")
        fill_ready(self._page, self._page.locator("input[name='password']"), "admin123", "Password input")
        click_ready(self._page, self._page.get_by_role("button", name="Login", exact=True), "Login button")
        expect(self._page).to_have_url(re.compile(r".*/dashboard.*"), timeout=NAVIGATION_TIMEOUT_MS)
