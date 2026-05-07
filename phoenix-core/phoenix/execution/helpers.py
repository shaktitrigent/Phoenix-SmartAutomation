"""Reusable Playwright helper functions for generated test scripts.

Import in generated scripts with:
    from phoenix.execution.helpers import safe_click, safe_fill, open_dropdown, ...

All helpers follow the Wait→Act→Assert pattern and handle the most common
failure modes identified across SauceDemo, OrangeHRM, DemoQA, Demoblaze,
and Maxima Apparel test runs.
"""

from __future__ import annotations

from typing import Optional

from playwright.sync_api import Locator, Page, expect


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------


def goto(page: Page, url: str, timeout: int = 120_000) -> None:
    """Navigate to URL with an extended timeout suitable for demo/staging sites."""
    page.goto(url, timeout=timeout)


def wait_for_navigation(page: Page, url_pattern: str, timeout: int = 30_000) -> None:
    """Wait for URL to match a glob or regex pattern after a navigation action."""
    page.wait_for_url(url_pattern, timeout=timeout)


# ---------------------------------------------------------------------------
# Interaction helpers
# ---------------------------------------------------------------------------


def safe_click(
    page: Page,
    selector: str,
    timeout: int = 30_000,
    *,
    retries: int = 2,
) -> None:
    """Click a selector with visibility check and retry on failure.

    Args:
        page: Playwright Page.
        selector: CSS selector or Playwright locator string.
        timeout: Milliseconds to wait for the element to be visible.
        retries: Number of times to retry on TimeoutError.
    """
    locator = page.locator(selector)
    for attempt in range(retries + 1):
        try:
            expect(locator.first).to_be_visible(timeout=timeout)
            locator.first.click()
            return
        except Exception:
            if attempt == retries:
                raise


def safe_fill(page: Page, selector: str, value: str, timeout: int = 30_000) -> None:
    """Clear and fill an input with a visibility check.

    Clears existing content before filling to prevent text concatenation.
    """
    locator = page.locator(selector).first
    expect(locator).to_be_visible(timeout=timeout)
    locator.clear()
    locator.fill(value)
    # Verify the fill was accepted
    expect(locator).to_have_value(value, timeout=5_000)


# ---------------------------------------------------------------------------
# Dropdown helpers
# ---------------------------------------------------------------------------


def open_dropdown(page: Page, trigger_selector: str, timeout: int = 10_000) -> None:
    """Open a custom dropdown and wait for options to become visible.

    Works with:
    - Custom combobox components (Vue/React/Angular)
    - Shopify disclosure patterns
    - aria-expanded trigger buttons

    Args:
        page: Playwright Page.
        trigger_selector: Selector for the dropdown trigger element.
        timeout: Milliseconds to wait for options to appear.
    """
    trigger = page.locator(trigger_selector).first
    expect(trigger).to_be_visible(timeout=timeout)
    trigger.click()
    # Wait for listbox or any expanded state
    try:
        expect(page.get_by_role("listbox")).to_be_visible(timeout=timeout)
    except Exception:
        # Fallback: wait for aria-expanded to become true
        expect(trigger).to_have_attribute("aria-expanded", "true", timeout=timeout)


def select_option(
    page: Page,
    dropdown_selector: str,
    option_text: str,
    *,
    timeout: int = 10_000,
    exact: bool = False,
) -> None:
    """Open a custom dropdown and select an option by text.

    For native <select> elements, use page.get_by_label(...).select_option() instead.

    Args:
        page: Playwright Page.
        dropdown_selector: Selector for the dropdown trigger (combobox).
        option_text: Visible text of the option to select.
        timeout: Milliseconds to wait for the option.
        exact: Whether to match option text exactly.
    """
    open_dropdown(page, dropdown_selector, timeout=timeout)
    option = page.get_by_role("option", name=option_text, exact=exact)
    expect(option).to_be_visible(timeout=timeout)
    option.click()


# ---------------------------------------------------------------------------
# Form submission helpers
# ---------------------------------------------------------------------------


def assert_form_submitted(
    page: Page,
    original_url: str,
    *,
    success_patterns: Optional[list[str]] = None,
    error_patterns: Optional[list[str]] = None,
    timeout: int = 10_000,
) -> bool:
    """Multi-strategy assertion for form submission outcomes.

    Tries in order:
    1. URL changed from original (redirect = success)
    2. Visible success text (thank, success, submitted, sent, received)
    3. Visible error text (error, invalid, required, failed)
    4. Form still visible (stayed = validation failed)

    Args:
        page: Playwright Page.
        original_url: URL before the form was submitted.
        success_patterns: Additional success text patterns (regex strings).
        error_patterns: Additional error text patterns (regex strings).
        timeout: Milliseconds for each check.

    Returns:
        True if success indicators found, False if error indicators found.

    Raises:
        AssertionError: If neither success nor error can be determined.
    """
    _success = success_patterns or []
    _error = error_patterns or []

    default_success = r"thank|success|submitted|sent|received|confirm"
    default_error = r"error|invalid|required|failed|wrong|incorrect"

    success_re = "|".join([default_success] + _success)
    error_re = "|".join([default_error] + _error)

    # Strategy 1: URL change
    try:
        page.wait_for_url(lambda url: url != original_url, timeout=5_000)
        return True
    except Exception:
        pass

    # Strategy 2: Success text visible
    success_loc = page.locator(f"text=/{success_re}/i")
    if success_loc.count() > 0:
        expect(success_loc.first).to_be_visible(timeout=timeout)
        return True

    # Strategy 3: Error text visible
    error_loc = page.locator(f"text=/{error_re}/i")
    if error_loc.count() > 0:
        expect(error_loc.first).to_be_visible(timeout=timeout)
        return False

    # Strategy 4: Form stayed on page (implicit validation rejection)
    if page.locator("form").count() > 0:
        return False

    raise AssertionError(
        f"Could not determine form submission outcome. "
        f"Current URL: {page.url}, Original URL: {original_url}"
    )


# ---------------------------------------------------------------------------
# Menu / navigation helpers
# ---------------------------------------------------------------------------


def open_nested_menu(
    page: Page,
    parent_selector: str,
    child_selector: str,
    timeout: int = 10_000,
) -> None:
    """Click a parent menu item and wait for the child item to be visible.

    Use this for navigation structures where sub-items are hidden until
    the parent menu is expanded (e.g., OrangeHRM sidebar).

    Args:
        page: Playwright Page.
        parent_selector: Selector (or role/name pattern) for the parent menu item.
        child_selector: Selector for the child menu item to click.
        timeout: Milliseconds to wait for the child item.
    """
    page.locator(parent_selector).first.click()
    child_locator = page.locator(child_selector).first
    expect(child_locator).to_be_visible(timeout=timeout)
    child_locator.click()


# ---------------------------------------------------------------------------
# Date picker helpers
# ---------------------------------------------------------------------------


def select_date(
    page: Page,
    input_selector: str,
    day: str,
    *,
    calendar_selector: str = ".calendar, [class*='calendar'], [class*='datepicker']",
    timeout: int = 10_000,
) -> None:
    """Open a date picker and select a specific day.

    Args:
        page: Playwright Page.
        input_selector: Selector for the date input field.
        day: Day number as string (e.g., "15").
        calendar_selector: Selector for the calendar widget container.
        timeout: Milliseconds to wait for the calendar.
    """
    date_input = page.locator(input_selector).first
    expect(date_input).to_be_visible(timeout=timeout)
    date_input.click()
    # Wait for calendar to appear
    expect(page.locator(calendar_selector).first).to_be_visible(timeout=timeout)
    # Click the day
    page.get_by_text(day, exact=True).first.click()
    # Verify the calendar closed
    try:
        expect(page.locator(calendar_selector).first).to_be_hidden(timeout=3_000)
    except Exception:
        pass  # Some pickers stay open — not a failure condition


# ---------------------------------------------------------------------------
# Modal helpers
# ---------------------------------------------------------------------------


def wait_for_modal(page: Page, name: Optional[str] = None, timeout: int = 10_000) -> Locator:
    """Wait for a modal/dialog to become visible and return its locator.

    Args:
        page: Playwright Page.
        name: Optional accessible name of the dialog.
        timeout: Milliseconds to wait.

    Returns:
        Locator scoped to the dialog for chaining.
    """
    if name:
        modal = page.get_by_role("dialog", name=name)
    else:
        modal = page.get_by_role("dialog")
    expect(modal.first).to_be_visible(timeout=timeout)
    return modal.first


def dismiss_modal(page: Page, button_name: str = "Close", timeout: int = 10_000) -> None:
    """Click a button inside the active modal to dismiss it."""
    modal = page.get_by_role("dialog")
    expect(modal.first).to_be_visible(timeout=timeout)
    modal.first.get_by_role("button", name=button_name).click()
    expect(modal.first).to_be_hidden(timeout=timeout)
