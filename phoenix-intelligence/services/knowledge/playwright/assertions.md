# Playwright Assertion Rules — Knowledge Base

> This file defines the assertion conventions and patterns for all Playwright test automation in this project. Follow these rules when writing, reviewing, or refactoring any Playwright test code.

---

## Golden Rule

**Assert on what the user sees, not what the DOM contains.** Prefer visible text, URLs, input values, and element states over internal attributes, class names, or DOM structure.

---

## Always Use `expect()` with Auto-Waiting

Playwright's `expect()` automatically retries until the condition is met or the timeout expires. Never manually wait before an assertion.

```python
from playwright.sync_api import expect

# ✅ Correct — auto-waits for the heading to appear
expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()

# ❌ Wrong — manual sleep before assertion
import time
time.sleep(3)
assert page.locator("h1").text_content() == "Dashboard"

# ❌ Wrong — raw assert with no auto-wait
assert page.locator("h1").is_visible()
```

> **Never use `time.sleep()`, `asyncio.sleep()`, or raw `assert` with locator state checks.** Always use `expect(locator).to_*` or `expect(page).to_*`.

---

## Assertion Categories — Quick Reference

### URL Assertions

Always use `re.compile()` for flexible URL matching. Never use `containing=` — it is not a valid parameter for `to_have_url`.

```python
import re

# ✅ Exact URL
expect(page).to_have_url("https://example.com/dashboard")

# ✅ Partial / pattern match with regex
expect(page).to_have_url(re.compile(r".*/dashboard.*"))
expect(page).to_have_url(re.compile(r".*testautomationpractice.*"))

# ✅ Match query parameters
expect(page).to_have_url(re.compile(r".*\?tab=settings.*"))

# ❌ Wrong — containing= is not valid
expect(page).to_have_url(containing="/dashboard")
```

> Always add `import re` at the top of the file when using regex in URL assertions.

---

### Visibility and State

```python
# Element is visible on screen
expect(page.get_by_role("button", name="Submit")).to_be_visible()

# Element is hidden / not visible
expect(page.get_by_role("alert")).to_be_hidden()
expect(page.get_by_text("Error")).not_to_be_visible()

# Button or input is enabled / disabled
expect(page.get_by_role("button", name="Submit")).to_be_enabled()
expect(page.get_by_role("button", name="Submit")).to_be_disabled()

# Checkbox or radio is checked / unchecked
expect(page.get_by_role("checkbox", name="Terms")).to_be_checked()
expect(page.get_by_role("checkbox", name="Terms")).not_to_be_checked()

# Input is editable (not readonly)
expect(page.get_by_role("textbox", name="Email")).to_be_editable()

# Element is focused
expect(page.get_by_role("textbox", name="Search")).to_be_focused()
```

---

### Text and Content

```python
# Exact text match
expect(page.get_by_role("heading", name="Dashboard")).to_have_text("Dashboard")

# Substring match
expect(page.get_by_role("alert")).to_contain_text("saved successfully")

# Text with regex
expect(page.get_by_role("status")).to_have_text(re.compile(r"\\d+ items found"))

# Multiple elements — check all text values
expect(page.get_by_role("listitem")).to_have_text(["Apple", "Banana", "Cherry"])
```

---

### Input Values

```python
# Input field value
expect(page.get_by_role("textbox", name="Email")).to_have_value("user@example.com")

# Regex value match
expect(page.get_by_role("textbox", name="Phone")).to_have_value(re.compile(r"\\+\\d{10,}"))

# Select / combobox value
expect(page.get_by_role("combobox", name="Country")).to_have_value("GB")

# Date input
expect(page.get_by_label("Start date")).to_have_value("2026-02-16")
```

---

### Count

```python
# Exact count
expect(page.get_by_role("row")).to_have_count(5)

# At least one exists (unique locator + visible)
expect(page.get_by_role("alert")).to_have_count(1)

# Table has expected rows (minus header)
expect(page.get_by_role("row")).to_have_count(11)  # 10 data rows + 1 header
```

---

### Attribute and CSS Assertions

Use only when user-visible assertions are not possible.

```python
# HTML attribute
expect(page.get_by_role("link", name="Docs")).to_have_attribute("href", "/docs")
expect(page.get_by_role("img", name="Logo")).to_have_attribute("src", re.compile(r".*logo.*"))

# CSS class (use sparingly — prefer visible state assertions)
expect(page.get_by_role("button", name="Submit")).to_have_class(re.compile(r".*active.*"))

# CSS property (visual validation)
expect(page.get_by_role("alert")).to_have_css("background-color", "rgb(255, 0, 0)")
```

---

### Page-Level Assertions

```python
# Page title
expect(page).to_have_title("Dashboard — MyApp")
expect(page).to_have_title(re.compile(r".*Dashboard.*"))

# Page URL (see URL section above)
expect(page).to_have_url(re.compile(r".*/dashboard"))
```

---

## Soft vs Hard Assertions

```python
# Hard assertion (default) — fails the test immediately
expect(page.get_by_role("heading")).to_have_text("Dashboard")

# Soft assertion — records failure but continues the test
expect.soft(page.get_by_role("heading")).to_have_text("Dashboard")
expect.soft(page.get_by_role("button", name="Logout")).to_be_visible()
```

**When to use which:**

| Type   | Use When                                                          |
|--------|-------------------------------------------------------------------|
| Hard   | Default for all assertions. First failure = test fails.           |
| Soft   | Only when intentionally collecting multiple checks in one test (e.g., verifying an entire form's prefilled values). |

> Default to hard assertions. Use soft assertions sparingly and intentionally.

---

## Negative Assertions

```python
# Element not visible
expect(page.get_by_role("dialog")).not_to_be_visible()
expect(page.get_by_text("Error message")).to_be_hidden()

# Element not attached to DOM (use with caution — prefer visibility checks)
expect(page.get_by_test_id("loading-spinner")).not_to_be_attached()

# Checkbox not checked
expect(page.get_by_role("checkbox", name="Terms")).not_to_be_checked()

# Text not present
expect(page.get_by_role("alert")).not_to_contain_text("Error")
```

**Best practice:** Prefer asserting that a **success state is visible** rather than that an error state is absent, when both options exist.

```python
# ✅ Preferred — assert the positive outcome
expect(page.get_by_role("alert")).to_contain_text("Saved successfully")

# 🟡 Acceptable but weaker — assert the error is gone
expect(page.get_by_text("Validation error")).not_to_be_visible()
```

---

## Custom Timeout

Override the default timeout (5s) for slow operations. Use this instead of `time.sleep()`.

```python
# Wait up to 15 seconds for a slow page transition
expect(page.get_by_role("heading", name="Report")).to_be_visible(timeout=15_000)

# Wait for a file download confirmation
expect(page.get_by_text("Download complete")).to_be_visible(timeout=30_000)
```

> Only override timeout when there is a documented reason (slow API, file processing, etc.). Add an inline comment explaining why.

---

## Common Test Patterns

### Form Submission — Assert Outcome

```python
# Fill and submit
page.get_by_role("textbox", name="Email").fill("user@example.com")
page.get_by_role("textbox", name="Password").fill("secret123")
page.get_by_role("button", name="Sign in").click()

# Assert outcome — NOT re-reading every field
expect(page).to_have_url(re.compile(r".*/dashboard"))
expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
```

### File Upload — Assert Confirmation

```python
page.get_by_label("Upload document").set_input_files("report.pdf")
page.get_by_role("button", name="Upload").click()

expect(page.get_by_text("report.pdf")).to_be_visible()
# or
expect(page.get_by_role("alert")).to_contain_text("uploaded successfully")
```

### Table Data — Assert Row Content

```python
row = page.get_by_role("row").filter(has_text="Alice Johnson")
expect(row).to_be_visible()
expect(row).to_contain_text("Active")
expect(row.get_by_role("cell").nth(2)).to_have_text("Engineering")
```

### Toast / Notification — Assert and Disappear

```python
toast = page.get_by_role("alert")
expect(toast).to_contain_text("Changes saved")
expect(toast).to_be_hidden()   # auto-waits for it to disappear
```

### Navigation — Assert Page Changed

```python
page.get_by_role("link", name="Settings").click()

expect(page).to_have_url(re.compile(r".*/settings"))
expect(page.get_by_role("heading", name="Settings")).to_be_visible()
```

### Modal / Dialog — Assert Open and Close

```python
# Open
page.get_by_role("button", name="Delete").click()
dialog = page.get_by_role("dialog", name="Confirm deletion")
expect(dialog).to_be_visible()

# Close
dialog.get_by_role("button", name="Cancel").click()
expect(dialog).not_to_be_visible()
```

---

## Assertion Selection Flowchart

```
What are you verifying?
│
├── Page navigated? → expect(page).to_have_url(re.compile(...))
│
├── Page title? → expect(page).to_have_title(...)
│
├── Element visible/hidden? → expect(locator).to_be_visible() / .to_be_hidden()
│
├── Text content? → expect(locator).to_have_text(...) / .to_contain_text(...)
│
├── Input value? → expect(locator).to_have_value(...)
│
├── Element state?
│   ├── Enabled/Disabled → .to_be_enabled() / .to_be_disabled()
│   ├── Checked → .to_be_checked() / .not_to_be_checked()
│   ├── Editable → .to_be_editable()
│   └── Focused → .to_be_focused()
│
├── Element count? → expect(locator).to_have_count(n)
│
└── HTML attribute? → expect(locator).to_have_attribute(name, value)
    (use only when visible state assertions are not possible)
```

---

## Rules for AI Code Generation

When generating or modifying Playwright assertions, follow these rules strictly:

1. **Always use `expect()` from `playwright.sync_api`.** Never use raw `assert`, `assertTrue`, or manual boolean checks on locator states.
2. **Never generate `time.sleep()` or `asyncio.sleep()` before assertions.** Use `expect()` auto-waiting. If a longer wait is needed, use the `timeout=` parameter with an inline comment.
3. **Always use `re.compile()` for URL assertions** that are not exact matches. Never use `containing=` — it does not exist.
4. **Always add `import re`** at the top of the file when using regex in any assertion.
5. **Assert on user-observable outcomes** — visible text, URL, input values, element visibility. Do not assert on class names, internal IDs, or DOM structure unless explicitly required.
6. **One or few assertions per test** that directly map to the acceptance criteria. Do not over-assert.
7. **After form submission, assert the outcome** (success message, URL change, next visible element) — do not re-read every form field.
8. **Prefer positive assertions over negative** — assert the success state is visible rather than the error state is absent.
9. **Default to hard assertions.** Only use `expect.soft()` when intentionally collecting multiple checks.
10. **Never assert on `locator.text_content()`, `locator.inner_text()`, or `locator.get_attribute()` directly.** Use `expect(locator).to_have_text()`, `.to_contain_text()`, or `.to_have_attribute()` instead — these auto-wait.