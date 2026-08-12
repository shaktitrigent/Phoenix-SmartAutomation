"""CreateANewEmployeeByEnteringTheEmPage — synthesized by phoenix automate (pom mode)."""
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


class CreateANewEmployeeByEnteringTheEmPage(BasePage):
    """Page object for create_a_new_employee_by_entering_the_em tests."""

    URL_PATH = ""

    def tc_001_create_a_new_employee_by_entering(self) -> None:
        """tc 001 create a new employee by entering."""
        configure_page(self._page)
        dismiss_known_overlays(self._page)
        # --- Step 1: User can navigate to the Add Employee page. ---
        expect(self._page.locator("body")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)

        # Expected: Page loads at the target URL with visible content and no error messages
        # --- Step 2: User can enter a valid First Name. ---
        fill_ready(self._page, self._page.get_by_label("User", exact=True), "can enter a valid First Name.", "User field")

        # Expected: "User" field contains the value "can enter a valid First Name."
        # --- Step 3: User can enter a valid Last Name. ---
        fill_ready(self._page, self._page.get_by_label("User", exact=True), "can enter a valid Last Name.", "User field")

        # Expected: "User" field contains the value "can enter a valid Last Name."
        # --- Step 4: User can enter a valid Employee ID. ---
        fill_ready(self._page, self._page.get_by_label("User", exact=True), "can enter a valid Employee ID.", "User field")

        # Expected: "User" field contains the value "can enter a valid Employee ID."
        # --- Step 5: User can click the Save button. ---
        click_ready(self._page, self._page.get_by_role("button", name="User can click the Save", exact=True), "User can click the Save button")

        # Expected: "User can click the Save" button is clicked and the action is triggered
        # --- Step 6: Employee is successfully created when all required details are valid. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Employee is successfully created when all required details are valid.
        # --- Step 7: A success confirmation is displayed after successful employee creation. ---

        # Expected: Dialog/alert is accepted and the page responds accordingly
        # --- Step 8: The newly created employee is available in the employee list. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: The newly created employee is available in the employee list.
        # --- Step 9: First Name is mandatory. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: First Name is mandatory.
        # --- Step 10: Last Name is mandatory. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Last Name is mandatory.
        # --- Step 11: Employee ID is mandatory. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: Employee ID is mandatory.
        # --- Step 12: An appropriate validation message is displayed when a mandatory field is empty. ---

        # Expected: [NEEDS MANUAL REVIEW] Expected outcome after: An appropriate validation message is displayed when a mandatory field is empty.
        # --- Step 13: An appropriate validation message is displayed when an invalid Employee ID is entered. ---
        fill_ready(self._page, self._page.get_by_label("An", exact=True), "appropriate validation message is displayed when an invalid Employee ID is entered.", "An field")

        # Expected: "An" field contains the value "appropriate validation message is displayed when an invalid Employee ID is entered."
        # --- Step 14: An employee should not be created with a duplicate Employee ID. ---
        expect(unique_visible(self._page.get_by_text("An employee should not be created with a duplicate Employee ", exact=True), "An employee should not be created with a duplicate Employee  assertion target")).to_be_visible(timeout=ASSERTION_TIMEOUT_MS)
