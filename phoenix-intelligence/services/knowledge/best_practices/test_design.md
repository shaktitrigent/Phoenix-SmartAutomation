# Test Design Principles — Playwright

> Core principles, patterns, and conventions for designing high-quality, maintainable Playwright tests. Follow these rules when writing, reviewing, or generating any test code in this project.

---

## 1. Test Independence & Isolation

Every test must be a self-contained unit that can run alone, in any order, and in parallel.

### Rules

- **No shared state between tests.** Each test gets its own browser context, storage state, and data. Never rely on a previous test's side effects.
- **No execution order dependency.** If test B only passes after test A, the design is broken.
- **Own your setup and teardown.** Each test creates what it needs and cleans up after itself.
- **Use fresh browser context per test.** Playwright does this by default — don't fight it with shared pages.

### Playwright Patterns

```python
# ✅ Good — each test is fully self-contained
def test_user_can_update_profile(page, create_user):
    user = create_user(name="Alice")               # arrange — fixture creates fresh data
    page.goto(f"/users/{user.id}/profile")
    page.get_by_role("textbox", name="Name").fill("Alice Updated")
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("alert")).to_contain_text("Profile updated")

# ❌ Bad — depends on a previous test having created the user
def test_update_profile(page):
    page.goto("/users/1/profile")                  # who is user 1? does it exist?
    page.get_by_role("textbox", name="Name").fill("Alice Updated")
    page.get_by_role("button", name="Save").click()
```

### Fixture Isolation Strategy

```python
# conftest.py — scoped fixtures for clean isolation
import pytest

@pytest.fixture
def authenticated_page(page, create_user):
    """Yields a page already logged in as a fresh user."""
    user = create_user()
    page.goto("/login")
    page.get_by_role("textbox", name="Email").fill(user.email)
    page.get_by_role("textbox", name="Password").fill(user.password)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
    yield page
    # teardown: Playwright auto-closes context; API cleanup if needed

@pytest.fixture
def create_user(api_client):
    """Factory fixture — each call creates a unique user via API."""
    created = []
    def _create(**overrides):
        user = api_client.create_user(**overrides)
        created.append(user)
        return user
    yield _create
    for u in created:
        api_client.delete_user(u.id)
```

---

## 2. Test Structure — The AAA Pattern

Every test follows **Arrange → Act → Assert**. Each section should be visually distinct. No logic blending.

### Structure Template

```python
def test_<action>_<expected_outcome>(page):
    # --- Arrange: set up preconditions ---
    # Navigate, prepare data, reach the starting state

    # --- Act: perform the single user action under test ---
    # Click, fill, submit, navigate

    # --- Assert: verify the expected outcome ---
    # Use expect() with Playwright locators
```

### Real Example

```python
def test_empty_cart_shows_message(authenticated_page):
    page = authenticated_page

    # Arrange
    page.goto("/cart")

    # Act — (no action needed; we're testing the empty state)

    # Assert
    expect(page.get_by_role("heading", name="Your Cart")).to_be_visible()
    expect(page.get_by_text("Your cart is empty")).to_be_visible()
    expect(page.get_by_role("link", name="Continue Shopping")).to_be_visible()
```

### Rules

- Keep Arrange minimal — use fixtures and API setup to avoid long UI navigation in setup.
- Act should be **one logical user action** (a click, a form submission, a navigation). If you need two actions, you likely need two tests.
- Assert against **user-visible outcomes**, not implementation details. Assert what the user sees, not what the DOM looks like.

---

## 3. Single Responsibility

Each test verifies **one behavior**. If the test name needs "and" in it, split it.

```python
# ✅ Good — one behavior per test
def test_login_with_valid_credentials_redirects_to_dashboard(page): ...
def test_login_with_invalid_password_shows_error(page): ...
def test_login_with_empty_email_shows_validation(page): ...

# ❌ Bad — multiple behaviors crammed together
def test_login_scenarios(page):
    # tests valid login, then invalid login, then empty fields...
```

### Exception — Asserting a Coherent Outcome

Multiple `expect()` calls are fine when they assert **different facets of the same outcome**.

```python
def test_successful_checkout_shows_confirmation(authenticated_page):
    # ... arrange and act ...

    # Assert — all facets of the "confirmation" outcome
    expect(page.get_by_role("heading", name="Order Confirmed")).to_be_visible()
    expect(page.get_by_text("Order #")).to_be_visible()
    expect(page.get_by_role("link", name="View Order Details")).to_be_visible()
```

This is **one behavior** (showing a confirmation) with multiple visible indicators — that's fine.

---

## 4. Naming Conventions

Test names are documentation. A reader should understand the scenario without reading the body.

### Format

```
test_<context>_<action>_<expected_outcome>
```

### Examples

```python
# Feature: Authentication
def test_login_with_valid_credentials_redirects_to_dashboard(page): ...
def test_login_with_expired_session_redirects_to_login(page): ...
def test_logout_clears_session_and_redirects(page): ...

# Feature: Shopping Cart
def test_adding_item_updates_cart_count(authenticated_page): ...
def test_removing_last_item_shows_empty_cart_message(authenticated_page): ...
def test_quantity_exceeding_stock_shows_limit_warning(authenticated_page): ...

# Feature: Search
def test_search_with_no_results_shows_empty_state(page): ...
def test_search_results_highlight_matching_terms(page): ...
```

### Rules

- Use snake_case.
- Start with `test_`.
- Include the context (feature/page), the action (what the user does), and the expected outcome.
- Never use generic names: `test_page_1`, `test_feature_works`, `test_basic`.

---

## 5. Test Data Management

### Principles

- **Never hardcode data that could change.** Use fixtures, factories, or API setup.
- **Each test owns its data.** Create it in setup, use it in the test, clean it up in teardown.
- **Use realistic but deterministic data.** Avoid random data in assertions; use it only for uniqueness.
- **Prefer API setup over UI setup.** Creating data through the UI is slow and fragile. Use API calls or direct DB access for preconditions.

### Patterns

```python
# ✅ Factory fixture — fast, isolated, API-driven
@pytest.fixture
def create_product(api_client):
    created = []
    def _create(**overrides):
        defaults = {"name": "Test Widget", "price": 29.99, "stock": 100}
        product = api_client.create_product(**{**defaults, **overrides})
        created.append(product)
        return product
    yield _create
    for p in created:
        api_client.delete_product(p.id)

def test_product_page_shows_details(page, create_product):
    product = create_product(name="Wireless Mouse", price=49.99)
    page.goto(f"/products/{product.id}")
    expect(page.get_by_role("heading", name="Wireless Mouse")).to_be_visible()
    expect(page.get_by_text("$49.99")).to_be_visible()
```

```python
# ✅ Parameterized data-driven testing
import pytest

@pytest.mark.parametrize("email,error_message", [
    ("", "Email is required"),
    ("not-an-email", "Enter a valid email address"),
    ("a" * 256 + "@test.com", "Email is too long"),
])
def test_registration_email_validation(page, email, error_message):
    page.goto("/register")
    page.get_by_role("textbox", name="Email").fill(email)
    page.get_by_role("button", name="Register").click()
    expect(page.get_by_text(error_message)).to_be_visible()
```

```python
# ❌ Bad — hardcoded IDs, fragile, not isolated
def test_view_product(page):
    page.goto("/products/42")     # what if product 42 doesn't exist?
```

---

## 6. Page Object Model (POM)

Encapsulate page interactions behind a clean API. Tests read like user stories; page objects handle the mechanics.

### Structure

```
pages/
├── login_page.py
├── dashboard_page.py
├── product_page.py
└── checkout_page.py
tests/
├── test_login.py
├── test_dashboard.py
└── test_checkout.py
```

### Page Object Template

```python
# pages/login_page.py
from playwright.sync_api import Page, expect

class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        # Locators — defined once, reused everywhere
        self.email_input = page.get_by_role("textbox", name="Email")
        self.password_input = page.get_by_role("textbox", name="Password")
        self.submit_button = page.get_by_role("button", name="Sign in")
        self.error_alert = page.get_by_role("alert")

    def goto(self):
        self.page.goto("/login")
        return self

    def login(self, email: str, password: str):
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.submit_button.click()
        return self

    def expect_error(self, message: str):
        expect(self.error_alert).to_contain_text(message)
        return self

    def expect_redirect_to_dashboard(self):
        expect(self.page).to_have_url("/dashboard")
        return self
```

### Test Using POM

```python
# tests/test_login.py
from pages.login_page import LoginPage

def test_login_with_invalid_password_shows_error(page, create_user):
    user = create_user(password="correct-password")

    (LoginPage(page)
        .goto()
        .login(user.email, "wrong-password")
        .expect_error("Invalid email or password"))
```

### POM Rules

- **Locators live in the page object**, never in tests.
- **Page methods return `self`** for chaining (fluent API).
- **Assertions can live in page objects** as `expect_*` methods for reusable outcome checks.
- **Never put test logic in page objects.** No conditionals, no branching, no "if element exists then...".
- **One page object per page/component.** Compose complex flows by calling multiple page objects in the test.

---

## 7. Assertions — Expect Pattern

Always use Playwright's `expect()` API. Never use raw Python `assert` for UI state.

### Core Assertions

```python
from playwright.sync_api import expect

# Visibility
expect(locator).to_be_visible()
expect(locator).to_be_hidden()

# Text content
expect(locator).to_have_text("Exact text")
expect(locator).to_contain_text("Partial text")

# Input values
expect(locator).to_have_value("user@example.com")

# State
expect(locator).to_be_enabled()
expect(locator).to_be_disabled()
expect(locator).to_be_checked()

# Count
expect(locator).to_have_count(5)

# URL and title (on page object)
expect(page).to_have_url("/dashboard")
expect(page).to_have_url(re.compile(r"/orders/\d+"))
expect(page).to_have_title("Dashboard — MyApp")

# Attributes and CSS
expect(locator).to_have_attribute("aria-expanded", "true")
expect(locator).to_have_css("color", "rgb(255, 0, 0)")
expect(locator).to_have_class(re.compile(r"active"))
```

### Rules

- **`expect()` auto-retries** until timeout. This replaces manual waits and sleep().
- **Assert user-visible outcomes.** Prefer `to_be_visible()` and `to_contain_text()` over checking DOM attributes.
- **Use `to_have_url`** after navigation actions instead of manual URL checks.
- **Use `re.compile()`** for flexible pattern matching on URLs, classes, and text.
- **Never use `assert locator.is_visible()`** — it doesn't auto-retry and causes flakiness.

```python
# ✅ Good — auto-retries until element is visible or timeout
expect(page.get_by_role("alert")).to_be_visible()

# ❌ Bad — one-shot check, no retry, flaky
assert page.get_by_role("alert").is_visible()
```

---

## 8. Reliability — Eliminating Flakiness

### Never Use Fixed Delays

```python
# ❌ Never
import time
time.sleep(3)
page.get_by_role("button", name="Submit").click()

# ✅ Playwright auto-waits for actionability before clicking
page.get_by_role("button", name="Submit").click()

# ✅ If you need to wait for a specific condition
expect(page.get_by_role("table")).to_be_visible()
page.get_by_role("row").first.click()
```

### Handle Network and Loading States

```python
# Wait for API response before asserting
with page.expect_response("**/api/orders") as response_info:
    page.get_by_role("button", name="Load Orders").click()
response = response_info.value
assert response.status == 200

# Wait for navigation after form submission
with page.expect_navigation():
    page.get_by_role("button", name="Submit").click()
```

### Handle Dynamic Content

```python
# Wait for content to stabilize before asserting count
expect(page.get_by_role("listitem")).to_have_count(10)

# Wait for loading indicator to disappear
expect(page.get_by_text("Loading...")).to_be_hidden()
expect(page.get_by_role("table")).to_be_visible()
```

### Retry-Friendly Assertions

```python
# ✅ Good — all expect() calls auto-retry
expect(page.get_by_role("status")).to_contain_text("3 items")

# ❌ Bad — snapshot check, no retry
count = page.get_by_role("listitem").count()
assert count == 3    # flaky if items are still loading
```

---

## 9. Test Categorization & Organization

### Test Markers (pytest)

```python
import pytest

@pytest.mark.smoke
def test_homepage_loads(page):
    """Critical path — must pass on every build."""
    page.goto("/")
    expect(page.get_by_role("heading", name="Welcome")).to_be_visible()

@pytest.mark.regression
def test_bug_12345_duplicate_order_fix(authenticated_page):
    """Regression for BUG-12345 — prevents re-introduction."""
    ...

@pytest.mark.edge
def test_form_handles_unicode_input(page):
    """Edge case — unusual but valid input."""
    ...

@pytest.mark.slow
def test_bulk_import_100_products(authenticated_page):
    """Long-running — excluded from fast CI pipelines."""
    ...
```

### Category Definitions

| Category       | Runs When              | Scope                                        | Characteristics                 |
|----------------|------------------------|----------------------------------------------|---------------------------------|
| `@smoke`       | Every build / PR       | Critical user paths, login, core CRUD        | < 30s each, minimal setup       |
| `@regression`  | Pre-release / nightly  | Previously broken flows, integration points  | Linked to bug IDs               |
| `@edge`        | Nightly / weekly       | Boundaries, error states, unusual inputs     | Data-driven with parametrize    |
| `@slow`        | Scheduled / manual     | Bulk operations, complex workflows           | > 30s, resource-intensive       |

### Running by Category

```bash
# Smoke tests only (fast CI gate)
pytest -m smoke

# Everything except slow
pytest -m "not slow"

# Regression + smoke
pytest -m "smoke or regression"
```

### File Organization

```
tests/
├── conftest.py                # shared fixtures, hooks, plugins
├── pages/                     # page objects
│   ├── login_page.py
│   ├── dashboard_page.py
│   └── checkout_page.py
├── helpers/                   # utilities, API clients, data builders
│   ├── api_client.py
│   └── data_factory.py
├── auth/
│   ├── test_login.py
│   ├── test_logout.py
│   └── test_password_reset.py
├── products/
│   ├── test_product_listing.py
│   ├── test_product_detail.py
│   └── test_product_search.py
└── checkout/
    ├── test_cart.py
    ├── test_payment.py
    └── test_order_confirmation.py
```

### Rules

- **Group by feature**, not by test type. A feature folder contains its smoke, regression, and edge tests together.
- **One test file per page/workflow.** Don't put all tests in one massive file.
- **Shared fixtures in `conftest.py`** — Pytest discovers them automatically. Use