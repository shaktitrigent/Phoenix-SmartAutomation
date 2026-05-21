---
title: OrangeHRM Domain Knowledge
category: domain_knowledge
tags: [orangehrm, hrm, leave, login, playwright]
---

# OrangeHRM Playwright Locators and Patterns

Use these locators only when the `application_url` contains `orangehrmlive.com` or the
user story explicitly names OrangeHRM. Do not apply them to other applications.

## Authentication

Credentials must come from environment variables. Never hardcode them.

```python
page.goto(os.environ["APP_URL"], timeout=60_000)
page.locator("input[name='username']").fill(os.environ["TEST_USERNAME"])
page.locator("input[name='password']").fill(os.environ["TEST_PASSWORD"])
page.get_by_role("button", name="Login").click()
expect(page).to_have_url(re.compile(r".*/dashboard.*"), timeout=60_000)
expect(page.locator(".oxd-topbar-header-breadcrumb-module")).to_contain_text("Dashboard")
```

## Navigation (top-level menu)

```python
page.get_by_role("link", name="Leave").click()
expect(page.get_by_role("link", name="Apply")).to_be_visible()
```

## Apply Leave flow

```python
page.get_by_role("link", name="Apply").click()
expect(page).to_have_url(re.compile(r".*/leave/applyLeave.*"))
expect(page.locator(".orangehrm-card-container").first).to_be_visible()

# Leave Type (custom dropdown — NOT a native <select>)
page.locator("div.oxd-input-group").filter(
    has=page.get_by_text("Leave Type", exact=True)
).locator(".oxd-select-text").first.click()
page.get_by_role("option").first.click()

# Date inputs
page.locator("div.oxd-input-group").filter(
    has=page.get_by_text("From Date", exact=True)
).locator("input").first.fill("YYYY-MM-DD")

page.locator("div.oxd-input-group").filter(
    has=page.get_by_text("To Date", exact=True)
).locator("input").first.fill("YYYY-MM-DD")

# Comment
page.locator("textarea").fill("Leave reason text here.")

# Submit
page.get_by_role("button", name="Apply").click()
expect(page.locator(".oxd-toast")).to_be_visible(timeout=10_000)
expect(page.locator(".oxd-toast")).to_contain_text("Success")
```

## My Leave list

```python
page.get_by_role("link", name="My Leave").click()
expect(page).to_have_url(re.compile(r".*/leave/viewMyLeaveList.*"))
expect(page.locator(".orangehrm-paper-container").first).to_be_visible()
```

## Common element locator reference

| Element | Locator |
|---|---|
| Username input | `page.locator("input[name='username']")` |
| Password input | `page.locator("input[name='password']")` |
| Login button | `page.get_by_role("button", name="Login")` |
| Dashboard breadcrumb | `page.locator(".oxd-topbar-header-breadcrumb-module")` |
| Invalid credentials banner | `page.locator(".oxd-alert-content-text").filter(has_text="Invalid credentials")` |
| Top nav link | `page.get_by_role("link", name="<MenuName>")` |
| Leave Type dropdown | `page.locator("div.oxd-input-group").filter(has=page.get_by_text("Leave Type", exact=True)).locator(".oxd-select-text").first` |
| From Date input | `page.locator("div.oxd-input-group").filter(has=page.get_by_text("From Date", exact=True)).locator("input").first` |
| To Date input | `page.locator("div.oxd-input-group").filter(has=page.get_by_text("To Date", exact=True)).locator("input").first` |
| Comment textarea | `page.locator("textarea")` |
| Success toast | `page.locator(".oxd-toast")` |
| Validation error | `page.locator(".oxd-input-field-error-message").first` |
| User dropdown | `page.locator(".oxd-userdropdown-tab")` |

## Validation error assertions

```python
# Submit without required field → field-level error appears
page.get_by_role("button", name="Apply").click()
expect(page.locator(".oxd-input-field-error-message").first).to_be_visible()
```
