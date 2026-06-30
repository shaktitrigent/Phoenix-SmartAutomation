"""ManualTestTc002LoginFailurePage — synthesized by phoenix automate (pom mode)."""
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


class LoginPageLoadsAndDisplaysCorrectTitlePage(BasePage):
    """Page object for manual_test_tc002_login_failure tests."""

    URL_PATH = ""

    def tc_002_login_page_loads_and_displays_cor(self) -> None:
        """tc 002 login page loads and displays cor."""
        configure_page(self._page)
        dismiss_known_overlays(self._page)
        # --- Step 1: Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login ---
        expect(self._page.locator("body")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)

        # Expected: Login page loads with visible content
        # --- Step 2: Verify that the page title contains "OrangeHRM" ---
        expect(self._page).to_have_title(re.compile(r".*OrangeHRM.*"))
