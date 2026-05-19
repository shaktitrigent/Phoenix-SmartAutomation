# Playwright Login Flow Test Pattern — Knowledge Base

> This file defines the standard patterns for testing authentication flows in Playwright. All examples follow the project's locator, assertion, waiting, and security rules. See companion files for those conventions.

---

## Golden Rule

**Never hardcode real credentials.** All usernames, passwords, and tokens come from environment variables or fixtures. Test data uses obviously synthetic values and `@example.com` domains.

**Positive and negative login scenarios must not share authenticated browser state.**
Use a fresh browser context or a fresh `page` fixture for invalid-credential scenarios so a prior successful login cannot leak into a negative-path test.

---

## 1. Auth Fixture — Reusable Login Setup

Define a shared login fixture in `conftest.py` to avoid repeating authentication in every test.

### Basic Login Fixture

```python
# conftest.py
import os
import re
import pytest
from playwright.sync_api import expect

@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("BASE_URL", "http://localhost:3000")

@pytest.fixture
def credentials():
    """Test credentials from environment. Never hardcoded."""
    return {
        "username": os.environ.get("TEST_USERNAME", "REPLACE_WITH_ENV_VAR"),
        "password": os.environ.get("TEST_PASSWORD", "REPLACE_WITH_ENV_VAR"),
    }
    # TODO: Supply real credentials via .env or CI secrets.

@pytest.fixture
def logged_in_page(page, base_url, credentials):
    """Yield a page that is already authenticated."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill(credentials["username"])
    page.get_by_label("Password").fill(credentials["password"])
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(re.compile(r".*/dashboard"))
    yield page
```

### Storage State Fixture (Faster — Reuse Session Across Tests)

```python
# conftest.py
import json, os, tempfile

@pytest.fixture(scope="session")
def auth_storage_state(browser, base_url, credentials):
    """Authenticate once, save session, reuse across all tests."""
    context = browser.new_context()
    page = context.new_page()

    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill(credentials["username"])
    page.get_by_label("Password").fill(credentials["password"])
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(re.compile(r".*/dashboard"))

    # Save storage state to temp file
    storage_path = os.path.join(tempfile.gettempdir(), "auth_state.json")
    context.storage_state(path=storage_path)
    context.close()
    yield storage_path
    # Cleanup
    if os.path.exists(storage_path):
        os.unlink(storage_path)

@pytest.fixture
def authenticated_page(browser, auth_storage_state):
    """Create a new page with pre-loaded auth session."""
    context = browser.new_context(storage_state=auth_storage_state)
    page = context.new_page()
    yield page
    context.close()
```

### API Login Fixture (Fastest — No UI for Setup)

```python
@pytest.fixture
def api_auth_context(playwright, base_url):
    """Authenticate via API, inject session into browser context."""
    import requests

    resp = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "email": os.environ["TEST_USERNAME"],
            "password": os.environ["TEST_PASSWORD"],
        },
    )
    assert resp.status_code == 200
    token = resp.json()["token"]

    # Create browser context with auth cookie/header
    context = playwright.chromium.launch().new_context(
        extra_http_headers={"Authorization": f"Bearer {token}"}
    )
    page = context.new_page()
    yield page
    context.close()
```

---

## 2. Successful Login

### Standard Login

```python
def test_login_success(page, base_url, credentials):
    """Valid credentials → redirect to dashboard."""
    page.goto(f"{base_url}/login")

    # Assert — login page loaded
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()

    # Act — enter credentials
    page.get_by_label("Email").fill(credentials["username"])
    page.get_by_label("Password").fill(credentials["password"])
    page.get_by_role("button", name="Sign in").click()

    # Assert — redirected to dashboard
    expect(page).to_have_url(re.compile(r".*/dashboard"))
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
```

### Verify Session Is Active

```python
def test_login_creates_session(page, base_url, credentials):
    """After login, session-dependent elements are visible."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill(credentials["username"])
    page.get_by_label("Password").fill(credentials["password"])
    page.get_by_role("button", name="Sign in").click()

    expect(page).to_have_url(re.compile(r".*/dashboard"))

    # Assert — session indicators
    expect(page.get_by_role("button", name="Account")).to_be_visible()       # user menu
    expect(page.get_by_role("navigation")).to_contain_text(credentials["username"])
```

### Login with "Remember Me"

```python
def test_login_remember_me(page, base_url, credentials):
    """Check 'Remember me' and verify persistent session."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill(credentials["username"])
    page.get_by_label("Password").fill(credentials["password"])
    page.get_by_role("checkbox", name="Remember me").check()
    page.get_by_role("button", name="Sign in").click()

    expect(page).to_have_url(re.compile(r".*/dashboard"))

    # Verify checkbox was checked (optional — validates the UI toggled)
    # Further session persistence testing requires closing/reopening browser
    # which is better handled via storage state validation
```

---

## 3. Invalid Credentials

### Wrong Password

```python
def test_login_wrong_password(page, base_url, credentials):
    """Valid email + wrong password → error, stays on login page."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill(credentials["username"])
    page.get_by_label("Password").fill("WrongPassword123!")
    page.get_by_role("button", name="Sign in").click()

    # Assert — error message visible
    expect(page.get_by_role("alert")).to_contain_text("Invalid email or password")

    # Assert — still on login page
    expect(page).to_have_url(re.compile(r".*/login"))

    # Assert — password field is cleared (common security pattern)
    expect(page.get_by_label("Password")).to_have_value("")
```

### Wrong Email

```python
def test_login_wrong_email(page, base_url):
    """Non-existent email → error, no information leakage."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill("nonexistent@example.com")
    page.get_by_label("Password").fill("AnyPassword123!")
    page.get_by_role("button", name="Sign in").click()

    # Assert — generic error (should NOT reveal whether email exists)
    expect(page.get_by_role("alert")).to_contain_text("Invalid email or password")

    # Assert — stays on login page
    expect(page).to_have_url(re.compile(r".*/login"))
```

### Account Locked After Repeated Failures (If Applicable)

```python
def test_login_account_lockout(page, base_url, credentials):
    """Multiple failed attempts → account locked message."""
    page.goto(f"{base_url}/login")

    for attempt in range(5):
        page.get_by_label("Email").fill(credentials["username"])
        page.get_by_label("Password").fill(f"WrongPassword{attempt}")
        page.get_by_role("button", name="Sign in").click()

        if attempt < 4:
            expect(page.get_by_role("alert")).to_contain_text("Invalid")
            # Clear fields for next attempt
            page.get_by_label("Email").clear()
            page.get_by_label("Password").clear()

    # Assert — locked after max attempts
    expect(page.get_by_role("alert")).to_contain_text("locked")
```

---

## 4. Empty Fields / Validation

### Both Fields Empty

```python
def test_login_empty_fields(page, base_url):
    """Submit empty form → validation errors for both fields."""
    page.goto(f"{base_url}/login")
    page.get_by_role("button", name="Sign in").click()

    # Assert — validation errors visible
    expect(page.get_by_text("Email is required")).to_be_visible()
    expect(page.get_by_text("Password is required")).to_be_visible()

    # Assert — stays on login page
    expect(page).to_have_url(re.compile(r".*/login"))
```

### Empty Email Only

```python
def test_login_empty_email(page, base_url):
    """Password filled, email empty → email validation error."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Password").fill("SomePassword123!")
    page.get_by_role("button", name="Sign in").click()

    expect(page.get_by_text("Email is required")).to_be_visible()
```

### Empty Password Only

```python
def test_login_empty_password(page, base_url):
    """Email filled, password empty → password validation error."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill("test@example.com")
    page.get_by_role("button", name="Sign in").click()

    expect(page.get_by_text("Password is required")).to_be_visible()
```

### Invalid Email Format

```python
def test_login_invalid_email_format(page, base_url):
    """Malformed email → format validation error."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill("not-an-email")
    page.get_by_label("Password").fill("SomePassword123!")
    page.get_by_role("button", name="Sign in").click()

    expect(page.get_by_text("valid email")).to_be_visible()
```

---

## 5. Password Reset Flow

### Request Reset

```python
def test_password_reset_request(page, base_url):
    """Request a password reset and verify confirmation."""
    page.goto(f"{base_url}/login")
    page.get_by_role("link", name="Forgot password").click()

    # Assert — on reset page
    expect(page.get_by_role("heading", name="Reset password")).to_be_visible()

    # Act — enter email and submit
    page.get_by_label("Email").fill("test@example.com")
    page.get_by_role("button", name="Send reset link").click()

    # Assert — confirmation message (should NOT reveal if email exists)
    expect(page.get_by_role("alert")).to_contain_text("check your email")
```

### Reset with Invalid Email

```python
def test_password_reset_invalid_email(page, base_url):
    """Reset request with invalid email → validation error."""
    page.goto(f"{base_url}/forgot-password")
    page.get_by_label("Email").fill("not-an-email")
    page.get_by_role("button", name="Send reset link").click()

    expect(page.get_by_text("valid email")).to_be_visible()
```

### Back to Login from Reset

```python
def test_password_reset_back_to_login(page, base_url):
    """Verify user can navigate back to login from reset page."""
    page.goto(f"{base_url}/forgot-password")
    page.get_by_role("link", name="Back to login").click()

    expect(page).to_have_url(re.compile(r".*/login"))
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
```

---

## 6. Logout

### Standard Logout

```python
def test_logout(logged_in_page, base_url):
    """Logged-in user logs out → redirected to login page."""
    page = logged_in_page

    # Act — logout via user menu
    page.get_by_role("button", name="Account").click()
    page.get_by_role("menuitem", name="Sign out").click()

    # Assert — redirected to login
    expect(page).to_have_url(re.compile(r".*/login"))
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
```

### Session Invalidated After Logout

```python
def test_logout_session_invalidated(logged_in_page, base_url):
    """After logout, navigating to a protected page redirects to login."""
    page = logged_in_page

    # Logout
    page.get_by_role("button", name="Account").click()
    page.get_by_role("menuitem", name="Sign out").click()
    expect(page).to_have_url(re.compile(r".*/login"))

    # Attempt to access protected page
    page.goto(f"{base_url}/dashboard")

    # Assert — redirected back to login
    expect(page).to_have_url(re.compile(r".*/login"))
```

---

## 7. Protected Routes / Unauthorized Access

```python
def test_protected_route_redirects_to_login(page, base_url):
    """Unauthenticated user accessing a protected route → redirect to login."""
    page.goto(f"{base_url}/dashboard")

    # Assert — redirected to login with return URL
    expect(page).to_have_url(re.compile(r".*/login"))
```

```python
def test_protected_route_with_return_url(page, base_url, credentials):
    """After login, user is returned to originally requested page."""
    # Try accessing settings without auth
    page.goto(f"{base_url}/settings")
    expect(page).to_have_url(re.compile(r".*/login"))

    # Login
    page.get_by_label("Email").fill(credentials["username"])
    page.get_by_label("Password").fill(credentials["password"])
    page.get_by_role("button", name="Sign in").click()

    # Assert — redirected to originally requested page, not default dashboard
    expect(page).to_have_url(re.compile(r".*/settings"))
```

---

## 8. OAuth / Social Login (If Applicable)

```python
def test_oauth_login_button_visible(page, base_url):
    """Verify OAuth login options are present on the login page."""
    page.goto(f"{base_url}/login")

    expect(page.get_by_role("button", name="Continue with Google")).to_be_visible()
    expect(page.get_by_role("button", name="Continue with GitHub")).to_be_visible()
```

```python
def test_oauth_redirect(page, base_url):
    """Clicking OAuth button redirects to the provider."""
    page.goto(f"{base_url}/login")
    page.get_by_role("button", name="Continue with Google").click()

    # Assert — redirected to Google's OAuth page
    expect(page).to_have_url(re.compile(r".*accounts\.google\.com.*"))
```

> **Note:** Full OAuth flow testing (completing the provider login) requires either mock OAuth providers or test accounts from the provider. Do not hardcode OAuth tokens.

---

## 9. Security-Focused Login Tests

### Password Not Visible by Default

```python
def test_password_field_masked(page, base_url):
    """Password input is masked (type=password) by default."""
    page.goto(f"{base_url}/login")
    expect(page.get_by_label("Password")).to_have_attribute("type", "password")
```

### Show/Hide Password Toggle

```python
def test_password_visibility_toggle(page, base_url):
    """Toggle reveals and hides password text."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Password").fill("TestPassword123!")

    # Show password
    page.get_by_role("button", name="Show password").click()
    expect(page.get_by_label("Password")).to_have_attribute("type", "text")

    # Hide password
    page.get_by_role("button", name="Hide password").click()
    expect(page.get_by_label("Password")).to_have_attribute("type", "password")
```

### SQL Injection Attempt

```python
def test_login_sql_injection(page, base_url):
    """SQL injection in email field → handled gracefully, no server error."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill("' OR '1'='1'; --")
    page.get_by_label("Password").fill("anything")
    page.get_by_role("button", name="Sign in").click()

    # Assert — generic error, not a 500 or stack trace
    expect(page.get_by_role("alert")).to_be_visible()
    expect(page).to_have_url(re.compile(r".*/login"))
```

### XSS Attempt

```python
def test_login_xss_attempt(page, base_url):
    """Script injection in email field → escaped, not executed."""
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill("<script>alert('xss')</script>")
    page.get_by_label("Password").fill("anything")
    page.get_by_role("button", name="Sign in").click()

    # Assert — no dialog appeared (script was not executed)
    # Assert — still on login page with a normal error
    expect(page.get_by_role("alert")).to_be_visible()
    expect(page).to_have_url(re.compile(r".*/login"))
```

---

## Test Coverage Matrix

| Scenario                          | Priority   | Type       |
|-----------------------------------|------------|------------|
| Successful login                  | 🔴 P0      | Smoke      |
| Invalid password                  | 🔴 P0      | Regression |
| Invalid email                     | 🔴 P0      | Regression |
| Empty fields validation           | 🟡 P1      | Regression |
| Invalid email format              | 🟡 P1      | Regression |
| Logout                            | 🔴 P0      | Smoke      |
| Session invalidated after logout  | 🟡 P1      | Regression |
| Protected route redirect          | 🔴 P0      | Smoke      |
| Return URL after login            | 🟡 P1      | Regression |
| Password reset request            | 🟡 P1      | Regression |
| Remember me                       | 🟢 P2      | Regression |
| Account lockout                   | 🟡 P1      | Security   |
| Password field masked             | 🟡 P1      | Security   |
| Show/hide password toggle         | 🟢 P2      | Regression |
| SQL injection                     | 🟡 P1      | Security   |
| XSS attempt                       | 🟡 P1      | Security   |
| OAuth button visibility           | 🟢 P2      | Smoke      |
| OAuth redirect                    | 🟢 P2      | Regression |

---

## Rules for AI Code Generation

When generating login flow tests, follow these rules strictly:

1. **Never hardcode credentials.** Always use `os.environ["TEST_USERNAME"]` / `os.environ["TEST_PASSWORD"]` or a `credentials` fixture. Use `"REPLACE_WITH_ENV_VAR"` as the default fallback with a `# TODO` comment.
2. **Use `get_by_label("Email")` and `get_by_label("Password")`** for input fields. Never use `page.fill("#email", ...)` or `page.fill("input[type='password']", ...)`.
3. **Use `get_by_role("button", name="Sign in")` for the submit button.** Never use `page.click("button[type='submit']")`.
4. **Use `expect(page).to_have_url(re.compile(...))` for navigation assertions.** Never use `page.wait_for_url(...)` or raw `assert "dashboard" in page.url`.
5. **Use `expect(locator).to_contain_text(...)` for error messages.** Never use `assert ... in locator.text_content()`.
6. **Use generic error messages in assertions** — assert `"Invalid email or password"` not `"Wrong password"`. Login errors should never reveal which field was wrong (security best practice).
7. **Always assert the user stays on the login page** after failed login attempts: `expect(page).to_have_url(re.compile(r".*/login"))`.
8. **Use the `logged_in_page` fixture** for tests that need an authenticated session. Do not repeat login steps in every test.
9. **Use storage state** (`context.storage_state()`) for session reuse across tests when performance matters. Never inject tokens via `localStorage` or `evaluate()`.
10. **Always add `import re` and `import os`** at the top of generated test files.
11. **Test emails must use `@example.com`** (RFC 2606 reserved). Never use real email domains.
12. **For password reset tests**, assert the confirmation message without verifying whether the email exists — this validates the security practice of not leaking user enumeration.
13. **For OrangeHRM specifically, use `input[name='username']`, `input[name='password']`, `get_by_role("button", name="Login")`, breadcrumb-based dashboard validation, and `.oxd-alert-content-text` for invalid credentials.**
14. **For invalid-login tests, explicitly start from a fresh page/context and assert the app remains on `/auth/login`.**
