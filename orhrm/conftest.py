"""Pytest configuration for OrangeHRM Phoenix tests."""

from __future__ import annotations

import os
from contextlib import suppress

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from orhrm.orangehrm_leave_flow import login


BASE_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"
DEFAULT_BROWSER = "chromium"
ACTION_TIMEOUT_MS = 30_000
NAVIGATION_TIMEOUT_MS = 60_000


def _parser_has_option(parser, option_name: str) -> bool:
    option_groups = []
    anonymous = getattr(parser, "_anonymous", None)
    if anonymous is not None:
        option_groups.append(anonymous)
    option_groups.extend(getattr(parser, "_groups", []))

    for group in option_groups:
        for option in getattr(group, "options", []):
            if option_name in getattr(option, "_long_opts", []):
                return True
    return False


def _addoption_if_missing(parser, option_name: str, *aliases, **kwargs) -> None:
    if _parser_has_option(parser, option_name):
        return
    try:
        parser.addoption(option_name, *aliases, **kwargs)
    except ValueError as exc:
        if option_name not in str(exc):
            raise


def pytest_addoption(parser):
    _addoption_if_missing(
        parser,
        "--base-url",
        action="store",
        default=None,
        help="Base URL for Phoenix-generated tests when pytest-playwright is not installed.",
    )
    _addoption_if_missing(
        parser,
        "--browser-type",
        default=DEFAULT_BROWSER,
        choices=["chromium", "firefox", "webkit"],
        help="Browser to use",
    )
    _addoption_if_missing(
        parser,
        "--headless",
        action="store_true",
        default=True,
        help="Run headless",
    )


@pytest.fixture(scope="session")
def base_url(request) -> str:
    configured_base_url = request.config.getoption("--base-url", default=None)
    return configured_base_url or BASE_URL


@pytest.fixture(scope="session")
def orangehrm_credentials() -> dict[str, str]:
    return {
        "username": os.environ.get("ORANGEHRM_USERNAME", "Admin"),
        "password": os.environ.get("ORANGEHRM_PASSWORD", "admin123"),
        "invalid_password": os.environ.get("ORANGEHRM_INVALID_PASSWORD", "invalid-password"),
    }


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser_type_name(request) -> str:
    return request.config.getoption("--browser-type")


@pytest.fixture(scope="session")
def browser(playwright_instance, browser_type_name, request) -> Browser:
    headless = request.config.getoption("--headless")
    browser_type = getattr(playwright_instance, browser_type_name)
    launched_browser = browser_type.launch(
        headless=headless,
        args=[
            "--disable-save-password-bubble",
            "--disable-features=PasswordManager",
        ],
    )
    yield launched_browser
    with suppress(Exception):
        launched_browser.close()


@pytest.fixture
def context(browser) -> BrowserContext:
    isolated_context = browser.new_context()
    isolated_context.set_default_timeout(ACTION_TIMEOUT_MS)
    isolated_context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    yield isolated_context
    with suppress(Exception):
        isolated_context.close()


@pytest.fixture
def page(context) -> Page:
    created_page = context.new_page()
    created_page.set_default_timeout(ACTION_TIMEOUT_MS)
    created_page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    created_page.on("dialog", lambda dialog: dialog.dismiss())
    yield created_page
    with suppress(Exception):
        created_page.close()


@pytest.fixture
def authenticated_page(page) -> Page:
    login(page)
    return page


@pytest.fixture(scope="session")
def locator_registry(tmp_path_factory):
    """Session-scoped registry that maps element names to LocatorBundles."""
    try:
        from phoenix.locators.registry import LocatorRegistry

        registry = LocatorRegistry.load_all("locators/")
    except ImportError:
        registry = {}
    return registry
