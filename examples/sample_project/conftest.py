"""Pytest configuration for the Phoenix sample project."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default="https://the-internet.herokuapp.com",
        help="Base URL for the application under test",
    )
