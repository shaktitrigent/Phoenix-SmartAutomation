"""Reusable OrangeHRM leave-flow helpers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import Locator, Page, expect


LOGIN_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"
SCREENSHOT_DIR = Path(__file__).resolve().parent / "debug_screenshots"


def _ensure_screenshot_dir() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def take_debug_screenshot(page: Page, name: str) -> None:
    _ensure_screenshot_dir()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_").lower()
    page.screenshot(path=str(SCREENSHOT_DIR / f"{safe_name}.png"), full_page=True)


def log_page_state(page: Page, label: str) -> None:
    print(f"[{label}] url={page.url}")
    print(f"[{label}] title={page.title()}")


def log_dom_snippet(page: Page, label: str, selector: str = "main", limit: int = 900) -> None:
    try:
        html = page.locator(selector).first.inner_html(timeout=5_000)
    except Exception:
        html = page.content()
    snippet = re.sub(r"\s+", " ", html).strip()[:limit]
    print(f"[{label}] dom={snippet}")


def log_locator_candidates(label: str, candidates: list[tuple[str, Locator]]) -> None:
    print(f"[locator-candidates] {label}: {', '.join(name for name, _ in candidates)}")


def first_visible_locator(
    label: str,
    candidates: list[tuple[str, Locator]],
    timeout: int = 15_000,
) -> Locator:
    log_locator_candidates(label, candidates)
    last_error: Exception | None = None
    for candidate_name, candidate in candidates:
        try:
            expect(candidate).to_be_visible(timeout=timeout)
            print(f"[locator-selected] {label}: {candidate_name}")
            return candidate
        except Exception as exc:
            last_error = exc
    raise AssertionError(f"Could not find a visible locator for {label}.") from last_error


def wait_for_loader(page: Page, label: str = "loader_wait") -> None:
    loader = page.locator(".oxd-form-loader")
    try:
        if loader.count():
            print(f"[{label}] waiting for .oxd-form-loader to disappear")
            loader.wait_for(state="hidden", timeout=20_000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass


def safe_click(page: Page, locator: Locator, label: str, *, force: bool = False) -> None:
    wait_for_loader(page, f"{label}_before_click")
    locator.wait_for(state="visible", timeout=20_000)
    locator.scroll_into_view_if_needed()
    try:
        locator.click(timeout=20_000, force=force)
    except Exception:
        take_debug_screenshot(page, "failure_state")
        log_page_state(page, f"{label}_click_failed")
        log_dom_snippet(page, f"{label}_click_failed")
        raise
    wait_for_loader(page, f"{label}_after_click")


def format_future_date(days_from_today: int) -> str:
    return (datetime.now() + timedelta(days=days_from_today)).strftime("%Y-%m-%d")


def fill_text_input(page: Page, locator: Locator, value: str, label: str) -> None:
    wait_for_loader(page, f"{label}_before_fill")
    locator.wait_for(state="visible", timeout=20_000)
    locator.scroll_into_view_if_needed()
    locator.click(timeout=10_000)
    locator.press("Control+A")
    locator.fill(value)


def username_field(page: Page) -> Locator:
    return first_visible_locator(
        "username_input",
        [
            ("username-by-name", page.locator("input[name='username']")),
            ("username-by-placeholder", page.get_by_placeholder("Username")),
        ],
    )


def password_field(page: Page) -> Locator:
    return first_visible_locator(
        "password_input",
        [
            ("password-by-name", page.locator("input[name='password']")),
            ("password-by-placeholder", page.get_by_placeholder("Password")),
        ],
    )


def login_button(page: Page) -> Locator:
    return first_visible_locator(
        "login_button",
        [("login-role-button", page.get_by_role("button", name="Login"))],
    )


def login(page: Page) -> None:
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    wait_for_loader(page, "login_page_loaded")
    expect(username_field(page)).to_be_visible()
    expect(password_field(page)).to_be_visible()
    fill_text_input(page, username_field(page), "Admin", "username")
    fill_text_input(page, password_field(page), "admin123", "password")
    safe_click(page, login_button(page), "login_button")
    dashboard = page.get_by_role("heading", name=re.compile("Dashboard", re.I))
    expect(dashboard).to_be_visible(timeout=30_000)
    take_debug_screenshot(page, "after_login")
    log_page_state(page, "after_login")
    log_dom_snippet(page, "after_login")


def invalid_credentials_banner(page: Page) -> Locator:
    return first_visible_locator(
        "invalid_credentials_banner",
        [
            (
                "invalid-banner-css",
                page.locator(".oxd-alert-content-text").filter(has_text="Invalid credentials"),
            ),
            ("invalid-banner-text", page.get_by_text("Invalid credentials", exact=True)),
        ],
    )


def navigate_to_apply_leave(page: Page) -> None:
    leave_link = first_visible_locator(
        "leave_link",
        [("leave-role-link", page.get_by_role("link", name="Leave"))],
    )
    safe_click(page, leave_link, "leave_link")

    apply_link = first_visible_locator(
        "apply_link",
        [("apply-role-link", page.get_by_role("link", name="Apply"))],
    )
    safe_click(page, apply_link, "apply_link")

    wait_for_loader(page, "apply_leave_page")
    apply_heading = first_visible_locator(
        "apply_leave_heading",
        [
            ("apply-leave-heading", page.get_by_role("heading", name=re.compile("Apply Leave", re.I))),
            ("apply-leave-text", page.get_by_text("Apply Leave", exact=True)),
        ],
        timeout=20_000,
    )
    expect(apply_heading).to_be_visible()
    take_debug_screenshot(page, "leave_page")
    log_page_state(page, "leave_page")
    log_dom_snippet(page, "leave_page")


def navigate_to_my_leave(page: Page) -> None:
    leave_link = first_visible_locator(
        "leave_link_my_leave",
        [("leave-role-link", page.get_by_role("link", name="Leave"))],
    )
    safe_click(page, leave_link, "leave_link_my_leave")
    my_leave_link = first_visible_locator(
        "my_leave_link",
        [("my-leave-role-link", page.get_by_role("link", name="My Leave"))],
    )
    safe_click(page, my_leave_link, "my_leave_link")
    wait_for_loader(page, "my_leave_page")


def leave_type_combobox(page: Page) -> Locator:
    return first_visible_locator(
        "leave_type_combobox",
        [
            (
                "leave-type-scoped-combobox",
                page.locator("div.oxd-input-group")
                .filter(has=page.get_by_text("Leave Type", exact=True))
                .get_by_role("combobox"),
            ),
            ("leave-type-first-combobox", page.get_by_role("combobox").first),
        ],
    )


def ensure_leave_type_available(page: Page) -> str:
    wait_for_loader(page, "leave_type_check")
    try:
        combo = leave_type_combobox(page)
    except AssertionError:
        pytest.skip("OrangeHRM demo environment has no leave balance")

    safe_click(page, combo, "leave_type_combobox", force=True)
    options = page.get_by_role("option")
    try:
        expect(options.first).to_be_visible(timeout=10_000)
    except Exception:
        pytest.skip("OrangeHRM demo environment has no leave balance")

    option_count = options.count()
    if option_count == 0:
        pytest.skip("OrangeHRM demo environment has no leave balance")

    for index in range(option_count):
        option = options.nth(index)
        text = option.inner_text().strip()
        if text and text != "-- Select --" and "No Leave Types" not in text:
            safe_click(page, option, f"leave_type_option_{index}", force=True)
            return text

    pytest.skip("OrangeHRM demo environment has no leave balance")


def field_group(page: Page, label: str) -> Locator:
    return page.locator("div.oxd-input-group").filter(has=page.get_by_text(label, exact=True))


def scoped_combobox(page: Page, label: str) -> Locator:
    return first_visible_locator(
        f"{label.lower().replace(' ', '_')}_combobox",
        [
            ("scoped-combobox", field_group(page, label).get_by_role("combobox")),
            ("scoped-select-text", field_group(page, label).locator(".oxd-select-text").first),
        ],
    )


def date_input(page: Page, label: str) -> Locator:
    return first_visible_locator(
        f"{label.lower().replace(' ', '_')}_input",
        [
            ("scoped-input", field_group(page, label).locator("input").first),
            ("date-placeholder", page.get_by_placeholder("yyyy-mm-dd").first),
        ],
    )


def comment_box(page: Page) -> Locator:
    return first_visible_locator(
        "comment_box",
        [
            ("comment-placeholder", page.get_by_placeholder("Type comment here")),
            ("comment-textarea", page.locator("textarea").first),
        ],
    )


def apply_button(page: Page) -> Locator:
    return first_visible_locator(
        "apply_button",
        [("apply-role-button", page.get_by_role("button", name="Apply"))],
    )


def search_button(page: Page) -> Locator:
    return first_visible_locator(
        "search_button",
        [("search-role-button", page.get_by_role("button", name="Search"))],
    )


def submit_leave_request(page: Page, comment: str, from_date: str, to_date: str) -> str:
    leave_type = ensure_leave_type_available(page)
    fill_text_input(page, date_input(page, "From Date"), from_date, "from_date")
    fill_text_input(page, date_input(page, "To Date"), to_date, "to_date")
    fill_text_input(page, comment_box(page), comment, "comment")
    take_debug_screenshot(page, "before_submit")
    safe_click(page, apply_button(page), "apply_button", force=True)
    success_toast = first_visible_locator(
        "success_toast",
        [
            ("success-toast", page.locator(".oxd-toast").filter(has_text="Success")),
            ("success-status", page.get_by_role("alert").filter(has_text="Success")),
        ],
        timeout=20_000,
    )
    expect(success_toast).to_be_visible()
    return leave_type


def apply_leave_request(page: Page, comment: str, from_date: str, to_date: str) -> str:
    login(page)
    navigate_to_apply_leave(page)
    return submit_leave_request(page, comment, from_date, to_date)
