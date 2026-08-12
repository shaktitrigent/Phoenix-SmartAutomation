"""CreateSearchUpdateAssignLeaveUploadPage — synthesized by phoenix automate (pom mode)."""
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


class CreateSearchUpdateAssignLeaveUploadPage(BasePage):
    """Page object for create_search_update_assign_leave_upload tests."""

    URL_PATH = ""

    def tc_001_create_search_update_assign_leave(self) -> None:
        """tc 001 create search update assign leave."""
        configure_page(self._page)
        dismiss_known_overlays(self._page)
        # --- Step 1: Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login and log in ---
        expect(self._page.locator("body")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)

        # Expected: Page at https://opensource-demo.orangehrmlive.com/web/index.php/auth/login loads successfully with visible content and no error messages
        # --- Step 2: Scenario 1 – Login ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Scenario 1 – Login
        # --- Step 3: Login successfully. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Login successfully.
        # --- Step 4: Scenario 2 – Create Employee ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Scenario 2 – Create Employee
        # --- Step 5: Navigate to PIM. ---
        expect(self._page.locator("body")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)

        # Expected: Page loads at the target URL with visible content and no error messages
        # --- Step 6: Add Employee. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Add Employee.
        # --- Step 7: Enter personal details. ---
        fill_ready(self._page, self._page.get_by_label("Personal", exact=True), "details.", "Personal field")

        # Expected: "Personal" field contains the value "details."
        # --- Step 8: Save successfully. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Save successfully.
        # --- Step 9: Scenario 3 – Search Employee ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Scenario 3 – Search Employee
        # --- Step 10: Search using employee name. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Search using employee name.
        # --- Step 11: Employee should appear. ---

        # Expected: Employee should appear.
        # --- Step 12: Scenario 4 – Update Employee ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Scenario 4 – Update Employee
        # --- Step 13: Update: ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Update:
        # --- Step 14: Nickname ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Nickname
        # --- Step 15: Driver License Number ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Driver License Number
        # --- Step 16: Nationality ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Nationality
        # --- Step 17: Marital Status ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Marital Status
        # --- Step 18: Click Save. ---

        # Expected: "Save." element responds to the click interaction
        # --- Step 19: Changes should persist ---
        expect(unique_visible(self._page.get_by_text("Changes should persist", exact=True), "Changes should persist assertion target")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)
