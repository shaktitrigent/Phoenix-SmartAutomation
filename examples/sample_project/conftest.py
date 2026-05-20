"""Pytest configuration for the Phoenix sample project."""

import pytest


BASE_URL = "https://the-internet.herokuapp.com"


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


def _addoption_if_missing(parser, option_name: str, **kwargs) -> None:
    if _parser_has_option(parser, option_name):
        return
    try:
        parser.addoption(option_name, **kwargs)
    except ValueError as exc:
        if option_name not in str(exc):
            raise


def pytest_addoption(parser):
    _addoption_if_missing(
        parser,
        "--base-url",
        action="store",
        default=None,
        help="Base URL for Phoenix sample tests when pytest-playwright is unavailable.",
    )


@pytest.fixture(scope="session")
def base_url(request) -> str:
    configured_base_url = request.config.getoption("--base-url", default=None)
    return configured_base_url or BASE_URL
