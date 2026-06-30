"""Shared constants for _sandbox test suite."""

import os

# ---------------------------------------------------------------------------
# Timeouts (milliseconds)
# ---------------------------------------------------------------------------

TIMEOUTS = {
    "action":     30_000,   # click, fill, select
    "navigation": 60_000,   # page.goto, URL assertions
    "short":       5_000,   # spinner / toast dismiss
    "long":      120_000,   # file uploads, slow reports
}

# ---------------------------------------------------------------------------
# Base URLs — resolved from environment at runtime
# ---------------------------------------------------------------------------

URLS = {
    "base":    os.environ.get("APP_URL", "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"),
    "login":   os.environ.get("APP_URL", "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login") + "/auth/login",
}

# ---------------------------------------------------------------------------
# Test credentials — always from environment, never hardcoded
# ---------------------------------------------------------------------------

CREDENTIALS = {
    "username": os.environ.get("TEST_USERNAME", ""),
    "password": os.environ.get("TEST_PASSWORD", ""),
}
