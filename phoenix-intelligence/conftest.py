"""
Pytest configuration for Phoenix Intelligence tests.
Disables browser password-manager prompts (e.g. "Change your password" after login)
so they do not block or interfere with test assertions.
"""

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """Add Chromium launch args to suppress password save/breach dialogs."""
    opts = dict(browser_type_launch_args or {})
    args = list(opts.get("args", []))
    args.extend([
        "--disable-save-password-bubble",
        "--disable-features=PasswordManager",
    ])
    opts["args"] = args
    return opts
