# Playwright Assertion Patterns — Knowledge Base

> Rules for generating correct post-action assertions. The most common source of
> flaky tests and false positives is assuming that the page behaves in a standard way
> (role="alert", heading elements, synchronous validation) when it does not.

---

## Golden Rule

**Never assume the element type, role, or text of a success/error indicator.
Always derive assertions from what you can observe in the DOM snapshot.**

**Never convert manual-test narration into an assertion locator.**
Phrases like `Dashboard loads successfully`, `fields are visible`, or `success message appears`
must become URL checks, real control visibility checks, or stable container assertions.

---

## Form Submission Assertions

### What NOT to assume after form submission

| Wrong assumption | Why it fails | What to do instead |
|-----------------|-------------|-------------------|
| `get_by_role("alert")` exists | Most sites use custom styled elements, not ARIA alerts | Check URL change or visible text |
| `validity.valid` updates synchronously | Browser validation may not apply until after submit | Submit first, then check form state |
| Confirmation appears as a `role="heading"` | May be a `<div>`, `<p>`, or custom element | Use `get_by_text` with regex |
| The page redirects on success | Some forms stay on the same page | Check both URL change and visible feedback |

### Progressive Detection Pattern (use for all form submissions)

```python
import re as _re

# Store original URL before submission
original_url = page.url
page.get_by_role("button", name="Submit").click()

# Strategy 1: Wait for URL change (success usually redirects)
try:
    page.wait_for_url(lambda url: url != original_url, timeout=5_000)
    # URL changed — treat as success
    expect(page).not_to_have_url(original_url)
except Exception:
    # No redirect — check for visible feedback text
    success_locator = page.locator("text=/thank|success|submitted|sent|received/i")
    error_locator = page.locator("text=/error|invalid|required|failed/i")

    success_count = success_locator.count()
    error_count = error_locator.count()

    if success_count > 0:
        expect(success_locator.first).to_be_visible()
    elif error_count > 0:
        expect(error_locator.first).to_be_visible()
    else:
        # Form stayed visible — validation rejected the input
        expect(page.locator("form")).to_be_visible()
```

### Error Validation Pattern

```python
# WRONG — assumes role="alert" that may not exist
expect(page.get_by_role("alert")).to_be_visible()

# WRONG — validity.valid may not be updated synchronously
assert page.locator("input[type='email']").evaluate("el => el.validity.valid") == False

# CORRECT — submit first, then check page state
page.get_by_role("button", name="Submit").click()
# Option A: Look for error text near the field
expect(page.locator("input[type='email']").locator("..")).to_contain_text(
    _re.compile(r"invalid|required|error", _re.IGNORECASE)
)
# Option B: Form stayed on the same page (validation rejected)
expect(page.locator("form")).to_be_visible()
# Option C: Check for any visible error indicator
error_indicators = page.locator("[class*='error'], [class*='invalid'], [aria-invalid='true']")
expect(error_indicators.first).to_be_visible()
```

---

## Element Role Assertions

### Verify actual DOM role before using `get_by_role`

Do NOT assume HTML semantic roles match visual appearance. Always derive the
assertion from the DOM snapshot, not from visual interpretation.

```python
# WRONG — "Products" in SauceDemo is a <span class="title">, not a heading
expect(page.get_by_role("heading", name="Products")).to_be_visible()

# CORRECT — use the observed element type
expect(page.locator(".title").filter(has_text="Products")).to_be_visible()
expect(page.locator("[data-test='inventory-container']")).to_be_visible()
# or: use text assertion which doesn't care about element type
expect(page.get_by_text("Products", exact=True).first).to_be_visible()
```

### Prefer attribute/class assertions over role assumptions

```python
# WRONG — assumes the element has a semantic heading role
expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()

# CORRECT — check the URL (more reliable for navigation success)
expect(page).to_have_url(re.compile(r".*/dashboard"))

# CORRECT — check a container that's always present on the dashboard
expect(page.locator(".dashboard-wrapper")).to_be_visible()
```

---

## Navigation / Redirect Assertions

```python
# CORRECT — after login, verify redirect happened
page.get_by_role("button", name="Login").click()
page.wait_for_url("**/dashboard/**", timeout=30_000)

# CORRECT — verify URL pattern after successful form submission
page.wait_for_url(re.compile(r".*(thank|confirmation|success)"), timeout=10_000)

# CORRECT — verify URL contains expected path segment
expect(page).to_have_url(re.compile(r".*/home"))
```

---

## Cart / Counter Assertions

```python
# WRONG — cart badge text is a display-only number, not a link name
expect(page.get_by_role("link", name="2")).to_be_visible()

# CORRECT — check the cart badge element and its text content
expect(page.locator(".shopping_cart_badge")).to_have_text("2")
expect(page.locator("[data-test='shopping-cart-badge']")).to_have_text("2")
```

---

## Dropdown / Select Assertions

```python
# CORRECT — for native <select>
expect(page.get_by_label("Country")).to_have_value("US")

# CORRECT — for custom dropdown (Vue/React), check the selected display value
expect(
    page.get_by_role("combobox", name="Leave Type")
).to_contain_text("Annual Leave")

# CORRECT — check a data attribute if the component sets it
expect(page.locator("[aria-selected='true']")).to_have_text("Annual Leave")
```

---

## Image / Visual Assertions

```python
# CORRECT — verify image loads (check src attribute, not visual content)
expect(page.get_by_role("img", name="Product Image")).to_be_visible()
expect(page.get_by_role("img", name="Product Image")).to_have_attribute(
    "src", re.compile(r"https://")
)
```

---

## Timing Rules for Assertions

```python
# WRONG — checking state before UI has updated
page.get_by_role("button", name="Sort").click()
assert page.locator(".inventory_item").count() == 6  # no auto-wait

# CORRECT — use expect() which retries until the condition is met
page.get_by_role("button", name="Sort").click()
expect(page.locator(".inventory_item").first).to_be_visible()
expect(page.locator(".inventory_item")).to_have_count(6)
```

---

## Rules for AI Code Generation

1. **Never generate `get_by_role("alert")` for form feedback** unless the DOM snapshot confirms `role="alert"` exists.
2. **Never check `validity.valid` without a preceding wait** — submit first, then inspect.
3. **Never use `get_by_role("heading")` unless the element is confirmed to be `<h1>-<h6>`** — use class-based or text-based locators instead.
4. **Always use progressive detection for form submissions**: check URL change first, then visible text, then form visibility.
5. **Use `expect().to_have_url()` after navigation** — it retries automatically and is more reliable than checking `page.url` directly.
6. **Wrap regex patterns in `re.compile()`** when using `to_have_url` or `to_contain_text` with regex.
7. **Never assert on literal prose copied from a manual step.** Assertions must be backed by a role, label, stable CSS selector, or snapshot-backed locator.
