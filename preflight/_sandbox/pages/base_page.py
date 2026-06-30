"""BasePage — shared foundation for all Page Object classes.

Every page class inherits from BasePage and gains:
- Resilient click / fill / select helpers with built-in waits
- Assertion helpers that wrap Playwright's expect()
- Navigation helpers
- Screenshot-on-step support

Usage::

    class LoginPage(BasePage):
        URL_PATH = "/auth/login"

        def login(self, username: str) -> None:
            # Login with username; password resolved from TEST_PASSWORD env var.
            password = os.environ.get(f"PASS_{username.upper()}", os.environ["TEST_PASSWORD"])
            self.fill(self._page.get_by_label("Username"), username)
            self.fill(self._page.get_by_label("Password"), password)
            self.click(self._page.get_by_role("button", name="Login"))
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Union

from playwright.sync_api import Locator, Page, expect


class BasePage:
    """Base class for all page objects in _sandbox."""

    # Override in subclass to enable page.goto(BASE_URL + URL_PATH)
    URL_PATH: str = "/"

    # Default timeouts — override per-page or per-action as needed
    ACTION_TIMEOUT_MS: int = 30_000
    NAVIGATION_TIMEOUT_MS: int = 60_000

    def __init__(self, page: Page) -> None:
        self._page = page
        self._page.set_default_timeout(self.ACTION_TIMEOUT_MS)
        self._page.set_default_navigation_timeout(self.NAVIGATION_TIMEOUT_MS)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, path: Optional[str] = None) -> None:
        """Navigate to BASE_URL + path (defaults to URL_PATH)."""
        base = os.environ.get("APP_URL", "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login").rstrip("/")
        url = base + (path or self.URL_PATH)
        self._page.goto(url, timeout=self.NAVIGATION_TIMEOUT_MS)

    def reload(self) -> None:
        self._page.reload()

    def go_back(self) -> None:
        self._page.go_back()

    @property
    def current_url(self) -> str:
        return self._page.url

    @property
    def title(self) -> str:
        return self._page.title()

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def click(self, locator: Locator) -> None:
        """Wait for locator to be visible and enabled, then click."""
        expect(locator).to_be_visible(timeout=self.ACTION_TIMEOUT_MS)
        expect(locator).to_be_enabled(timeout=self.ACTION_TIMEOUT_MS)
        locator.click()

    def fill(self, locator: Locator, value: str) -> None:
        """Clear the field and type value."""
        expect(locator).to_be_visible(timeout=self.ACTION_TIMEOUT_MS)
        locator.clear()
        locator.fill(value)

    def select_option(self, locator: Locator, value: str) -> None:
        """Select a dropdown option by value or label."""
        expect(locator).to_be_visible(timeout=self.ACTION_TIMEOUT_MS)
        locator.select_option(value)

    def check(self, locator: Locator) -> None:
        locator.check()

    def uncheck(self, locator: Locator) -> None:
        locator.uncheck()

    def hover(self, locator: Locator) -> None:
        locator.hover()

    def press_key(self, locator: Locator, key: str) -> None:
        locator.press(key)

    def upload_file(self, locator: Locator, file_path: Union[str, Path]) -> None:
        locator.set_input_files(str(file_path))

    # ------------------------------------------------------------------
    # Waiting
    # ------------------------------------------------------------------

    def wait_for_visible(self, locator: Locator, timeout_ms: Optional[int] = None) -> None:
        expect(locator).to_be_visible(timeout=timeout_ms or self.ACTION_TIMEOUT_MS)

    def wait_for_hidden(self, locator: Locator, timeout_ms: Optional[int] = None) -> None:
        expect(locator).to_be_hidden(timeout=timeout_ms or self.ACTION_TIMEOUT_MS)

    def wait_for_url(self, pattern: str, timeout_ms: Optional[int] = None) -> None:
        expect(self._page).to_have_url(
            re.compile(pattern), timeout=timeout_ms or self.NAVIGATION_TIMEOUT_MS
        )

    def wait_for_text(self, locator: Locator, text: str, timeout_ms: Optional[int] = None) -> None:
        expect(locator).to_contain_text(text, timeout=timeout_ms or self.ACTION_TIMEOUT_MS)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_visible(self, locator: Locator, timeout_ms: Optional[int] = None) -> None:
        expect(locator).to_be_visible(timeout=timeout_ms or self.ACTION_TIMEOUT_MS)

    def assert_hidden(self, locator: Locator, timeout_ms: Optional[int] = None) -> None:
        expect(locator).to_be_hidden(timeout=timeout_ms or self.ACTION_TIMEOUT_MS)

    def assert_text(self, locator: Locator, text: str, timeout_ms: Optional[int] = None) -> None:
        expect(locator).to_contain_text(text, timeout=timeout_ms or self.ACTION_TIMEOUT_MS)

    def assert_value(self, locator: Locator, value: str, timeout_ms: Optional[int] = None) -> None:
        expect(locator).to_have_value(value, timeout=timeout_ms or self.ACTION_TIMEOUT_MS)

    def assert_url_contains(self, path: str, timeout_ms: Optional[int] = None) -> None:
        escaped = re.escape(path)
        expect(self._page).to_have_url(
            re.compile(f".*{escaped}.*"), timeout=timeout_ms or self.NAVIGATION_TIMEOUT_MS
        )

    def assert_title_contains(self, text: str) -> None:
        expect(self._page).to_have_title(re.compile(f".*{re.escape(text)}.*"))

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_text(self, locator: Locator) -> str:
        return locator.inner_text()

    def get_value(self, locator: Locator) -> str:
        return locator.input_value()

    def is_visible(self, locator: Locator) -> bool:
        return locator.is_visible()

    def is_enabled(self, locator: Locator) -> bool:
        return locator.is_enabled()

    def is_checked(self, locator: Locator) -> bool:
        return locator.is_checked()

    def count(self, locator: Locator) -> int:
        return locator.count()

    def screenshot(self, name: str, full_page: bool = False) -> None:
        """Save a screenshot to reports/screenshots/<name>.png."""
        out = Path("reports") / "screenshots" / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(out), full_page=full_page)

    def dismiss_dialog(self) -> None:
        self._page.once("dialog", lambda d: d.dismiss())

    def accept_dialog(self) -> None:
        self._page.once("dialog", lambda d: d.accept())
