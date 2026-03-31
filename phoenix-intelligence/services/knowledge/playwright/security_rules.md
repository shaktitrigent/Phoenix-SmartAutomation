# Playwright Security Rules — Knowledge Base

> This file defines the security conventions for all generated Playwright test scripts in this project. Every rule applies to both human-written and AI-generated code. Follow these rules when writing, reviewing, or refactoring any test automation.

---

## Golden Rule

**Never let a test script become a security liability.** Scripts live in version control, run in CI, and produce logs and artifacts — all of which are attack surfaces if secrets or PII leak into them.

---

## 1. No Secrets in Scripts — Ever

Credentials, API keys, tokens, and any authentication material must never appear in test code, fixtures, or configuration files committed to version control.

### Environment Variables (Preferred)

```python
import os

# ✅ Correct — read from environment
username = os.environ["TEST_USERNAME"]
password = os.environ["TEST_PASSWORD"]
api_key  = os.environ.get("API_KEY", "")

page.get_by_label("Email").fill(username)
page.get_by_label("Password").fill(password)
```

### .env File (Local Development Only)

```bash
# .env — MUST be in .gitignore, never committed
TEST_USERNAME=test_user@example.com
TEST_PASSWORD=T3stP@ssw0rd!
API_KEY=sk-test-abc123
BASE_URL=https://staging.example.com
```

```python
# conftest.py — load .env at the start of the session
from dotenv import load_dotenv
load_dotenv()
```

### Placeholder Defaults for Generated Code

When generating code where the real secret is unknown, use obvious placeholders and a comment:

```python
# ✅ Correct — placeholder with instruction
username = os.environ.get("TEST_USERNAME", "REPLACE_WITH_ENV_VAR")
password = os.environ.get("TEST_PASSWORD", "REPLACE_WITH_ENV_VAR")
# TODO: Supply real credentials via environment variables or .env file. Never hardcode.
```

```python
# ❌ Forbidden — real or realistic-looking credentials
password = "P@ssword123!"
api_key = "sk-live-abc123xyz"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### What Counts as a Secret

| Category              | Examples                                          |
|-----------------------|---------------------------------------------------|
| Authentication        | Passwords, PINs, MFA codes, session tokens        |
| API credentials       | API keys, client secrets, bearer tokens            |
| Infrastructure        | Database connection strings, SSH keys, certificates|
| Third-party services  | Stripe keys, AWS credentials, OAuth secrets        |
| Internal URLs         | Production URLs with embedded auth tokens          |

---

## 2. Test Data and PII

Never use real personal data in test scripts. Use obviously synthetic values that cannot be confused with real users.

### Recommended Test Data Patterns

```python
# ✅ Names — obviously fake
name = "Test User"
first_name = "Jane"
last_name = "Testington"

# ✅ Emails — use example.com (RFC 2606 reserved domain)
email = "test.user@example.com"
admin_email = "admin@example.com"

# ✅ Phone numbers — use 555 prefix (North America) or obviously fake
phone = "555-0100"
international_phone = "+44 20 7946 0958"   # Ofcom reserved range

# ✅ Addresses — generic, non-real
address = "123 Test Street, Test City, TS1 1AA"

# ✅ Financial — Stripe/standard test card numbers
card_number = "4242424242424242"       # Stripe test card
card_expiry = "12/30"
card_cvc = "123"

# ❌ Forbidden — real or realistic personal data
email = "john.smith@gmail.com"
phone = "+44 7700 900123"              # could be real
ssn = "123-45-6789"
```

### Dynamic Test Data with Factories

For tests that need unique data per run, generate it programmatically:

```python
import uuid
from datetime import datetime

# Unique per run — avoids collision in shared environments
unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
unique_name = f"Test User {datetime.now().strftime('%H%M%S')}"
```

---

## 3. Environment and Base URL Configuration

Never hardcode environment-specific URLs. All environment configuration must come from external config.

### Playwright Config (playwright.config / conftest.py)

```python
# conftest.py
import os
import pytest

@pytest.fixture(scope="session")
def base_url():
    """Base URL from environment or project config. Never hardcoded."""
    return os.environ.get("BASE_URL", "http://localhost:3000")
```

```python
# Usage in tests
def test_login(page, base_url):
    page.goto(base_url + "/login")
```

### What NOT to Do

```python
# ❌ Hardcoded staging/production URL
page.goto("https://staging.mycompany.com/login")
page.goto("https://app.mycompany.com/api/v2/users")

# ❌ Environment-specific path assumptions
page.goto("http://192.168.1.100:8080/admin")

# ✅ Config-driven
page.goto(f"{base_url}/login")
page.goto(f"{api_base_url}/api/v2/users")
```

---

## 4. File Handling — Uploads, Downloads, and Temp Files

### Upload Files — Use Temporary Files

```python
import tempfile
import os

def test_file_upload(page, base_url):
    # Create a temp file with generic content
    with tempfile.NamedTemporaryFile(
        suffix=".txt", delete=False, mode="w"
    ) as tmp:
        tmp.write("This is test upload content.")
        tmp_path = tmp.name

    try:
        page.goto(f"{base_url}/upload")
        page.get_by_label("Upload document").set_input_files(tmp_path)
        page.get_by_role("button", name="Upload").click()
        # assertions here
    finally:
        # Always clean up
        os.unlink(tmp_path)
```

### Download Files — Secure Storage

```python
import tempfile

def test_file_download(page, base_url):
    with tempfile.TemporaryDirectory() as download_dir:
        # Configure download path
        page.goto(f"{base_url}/reports")

        with page.expect_download() as download_info:
            page.get_by_role("button", name="Export CSV").click()

        download = download_info.value
        download.save_as(os.path.join(download_dir, download.suggested_filename))

        # Assert on the file, then it auto-cleans with the temp directory
```

### Rules

- Never reference real user files or absolute paths (`/Users/john/documents/report.pdf`).
- Always use `tempfile` for both upload and download artifacts.
- Always clean up in `finally` blocks or use context managers.
- Never commit test files containing sensitive content.

---

## 5. Logging, Screenshots, and Trace Security

### No Sensitive Data in Logs

```python
# ❌ Forbidden — logs credentials
print(f"Logging in with password: {password}")
logger.info(f"API response: {response.json()}")      # may contain tokens
logger.debug(f"Page HTML: {page.content()}")          # may contain session data

# ✅ Correct — redacted or safe logging
print(f"Logging in as: {username}")
logger.info(f"API status: {response.status_code}")
logger.debug("Login page loaded successfully")
```

### Screenshots and Traces

```python
# ✅ Store in a gitignored, non-public directory
ARTIFACT_DIR = os.environ.get("TEST_ARTIFACT_DIR", "test-results/")

# ✅ Use generic names — no PII or secrets in filenames
page.screenshot(path=f"{ARTIFACT_DIR}/login-failure.png")

# ❌ Forbidden — PII in filename
page.screenshot(path="screenshots/john.smith-login-fail.png")
```

**CI/CD rules:**
- Screenshots, traces, and video recordings may capture sensitive page content (tokens in URLs, form data, session IDs).
- Store artifacts in CI as ephemeral (auto-deleted after retention period).
- Never publish test artifacts to public storage or logs.
- Add `test-results/`, `traces/`, `screenshots/` to `.gitignore`.

### .gitignore Entries

```gitignore
# Test artifacts — never commit
test-results/
traces/
screenshots/
videos/
*.zip
.env
.env.*
```

---

## 6. Permissions and Test Scope

### Least Privilege Principle

```python
# ✅ Correct — dedicated test account with minimal permissions
username = os.environ.get("TEST_USERNAME")       # role: "viewer" or "test_user"

# ❌ Avoid — admin account for convenience
username = os.environ.get("ADMIN_USERNAME")      # only use when testing admin features
```

**Rules:**
- Tests must use the lowest privilege account that satisfies the test requirement.
- Admin accounts are only acceptable when explicitly testing admin functionality.
- Never reuse production accounts for testing.

### Non-Destructive by Default

```python
# ✅ Safe — creates test data, asserts, then cleans up
def test_create_and_delete_item(page, base_url):
    # Create
    page.get_by_role("button", name="New Item").click()
    page.get_by_label("Name").fill("Test Item - Auto")
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_text("Test Item - Auto")).to_be_visible()

    # Cleanup — delete what we created
    page.get_by_role("row").filter(has_text="Test Item - Auto").get_by_role("button", name="Delete").click()
    page.get_by_role("dialog").get_by_role("button", name="Confirm").click()

# ❌ Dangerous — bulk deletes without safeguards
def test_cleanup_all(page):
    page.get_by_role("button", name="Delete All Records").click()  # irreversible
```

**Rules:**
- Never generate scripts that perform irreversible bulk operations (delete all, drop table, reset environment) without explicit user confirmation in a comment.
- Tests should clean up only the data they create — never wipe shared state.
- If a test requires destructive actions, add a prominent `# WARNING:` comment and require a confirmation flag.

### No Auth Bypass

```python
# ❌ Forbidden — bypassing login for convenience
page.evaluate("localStorage.setItem('auth_token', 'fake-admin-token')")
page.set_extra_http_headers({"Authorization": "Bearer hardcoded-token"})

# ✅ Correct — authenticate through the UI or a proper API setup
page.goto(f"{base_url}/login")
page.get_by_label("Email").fill(os.environ["TEST_USERNAME"])
page.get_by_label("Password").fill(os.environ["TEST_PASSWORD"])
page.get_by_role("button", name="Sign in").click()

# ✅ Acceptable — API login for speed, but using real credentials from env
api_context = playwright.request.new_context()
response = api_context.post(f"{base_url}/api/auth/login", data={
    "email": os.environ["TEST_USERNAME"],
    "password": os.environ["TEST_PASSWORD"],
})
storage = response.json()["session"]
# Use storage state for subsequent browser tests
```

---

## 7. Dependency and Supply Chain Safety

```python
# ✅ Pin versions in requirements.txt or pyproject.toml
# playwright==1.42.0
# pytest-playwright==0.4.4

# ❌ Avoid unpinned or wildcard versions
# playwright>=1.0
# pytest-playwright
```

**Rules:**
- Pin all test dependency versions to prevent supply chain attacks.
- Audit new test dependencies before adding them.
- Use lock files (`poetry.lock`, `pip-compile`) for reproducible installs.

---

## Quick Reference — Secure Patterns

| Area              | ✅ Do                                           | ❌ Don't                                        |
|-------------------|-------------------------------------------------|-------------------------------------------------|
| Credentials       | `os.environ["TEST_PASSWORD"]`                   | `password = "P@ssword123!"`                     |
| Emails            | `"test@example.com"`                            | `"john.smith@gmail.com"`                        |
| Base URL          | `os.environ.get("BASE_URL")`                    | `"https://staging.company.com"`                 |
| Upload files      | `tempfile.NamedTemporaryFile()`                 | `"/Users/john/report.pdf"`                      |
| Logging           | `f"Login as: {username}"`                       | `f"Password: {password}"`                       |
| Screenshots       | `"test-results/login-failure.png"`              | `"screenshots/john-smith-fail.png"`             |
| Test accounts     | Dedicated, least-privilege test account          | Production admin account                        |
| Cleanup           | Delete only what the test created                | `"Delete All Records"`                          |
| Auth              | UI login or API login with env credentials       | `localStorage.setItem('auth_token', '...')`     |
| Dependencies      | Pinned versions + lock file                      | Unpinned `>=` or wildcard                       |

---

## Rules for AI Code Generation

When generating or modifying Playwright test scripts, follow these security rules strictly:

1. **Never generate real or realistic-looking credentials.** Use `os.environ["VAR_NAME"]` with a `# TODO` comment instructing the user to supply real values via `.env` or CI secrets.
2. **Never hardcode base URLs.** Always read from `os.environ.get("BASE_URL")` or a fixture. Use `http://localhost:3000` as the default fallback only.
3. **Use RFC 2606 reserved domains for test emails** — always `@example.com`, `@example.org`, or `@test.com`. Never `@gmail.com`, `@yahoo.com`, or any real provider.
4. **Use obviously synthetic test data** — `"Test User"`, `"555-0100"`, `"123 Test Street"`. Never generate data that looks like a real person.
5. **Always use `tempfile` for file upload/download tests.** Clean up in `finally` blocks. Never reference absolute or user-specific file paths.
6. **Never generate `print()` or `logger` calls that output credentials, tokens, full HTTP responses, or page HTML.** Log only safe identifiers (username, status code, element text).
7. **Never generate auth bypass code** — no `localStorage.setItem('token', ...)`, no hardcoded `Authorization` headers. Authenticate through the UI or a proper API login fixture using env credentials.
8. **Default to least-privilege test accounts.** Only use admin credentials when the test explicitly tests admin functionality, and add a `# Requires admin role` comment.
9. **Never generate bulk-destructive operations** (delete all, reset, drop) without a prominent `# WARNING: DESTRUCTIVE` comment and a confirmation safeguard.
10. **Always add `.env`, `test-results/`, `traces/`, `screenshots/`, and `videos/` to `.gitignore`** when generating project scaffolding or CI configuration.
11. **Add `import os` at the top** of any generated script that reads environment variables. Add `import tempfile` when using temporary files.
12. **When generating conftest.py or fixtures**, include a docstring explaining which environment variables are required and their purpose.