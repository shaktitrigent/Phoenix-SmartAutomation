---
title: Login Flow Test Pattern
category: authentication
tags: [login, authentication, user-flow, smoke]
---

# Login Flow Test Pattern

## Description
Standard test pattern for user login functionality. This pattern covers the essential test scenarios for authentication flows.

## Use Cases
- User login with valid credentials
- User login with invalid credentials
- Password reset flow
- Remember me functionality
- Session management

## Test Scenarios

### 1. Successful Login
**Steps:**
1. Navigate to login page
2. Enter valid email/username
3. Enter valid password
4. Click login button
5. Verify redirect to dashboard/home page
6. Verify user session is created

**Expected Result:** User is successfully logged in and redirected to the application.

### 2. Invalid Credentials
**Steps:**
1. Navigate to login page
2. Enter invalid email/username
3. Enter invalid password
4. Click login button
5. Verify error message is displayed
6. Verify user remains on login page

**Expected Result:** Error message displayed, user not logged in.

### 3. Empty Fields Validation
**Steps:**
1. Navigate to login page
2. Leave email/username field empty
3. Leave password field empty
4. Click login button
5. Verify validation errors are displayed

**Expected Result:** Field validation errors are shown.

## Automation Example

```python
def test_login_success(page):
    page.goto("/login")
    page.fill("#email", "user@example.com")
    page.fill("#password", "password123")
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard")
    assert page.locator(".user-menu").is_visible()
```

## When to Use
- Smoke testing
- Regression testing
- Critical user flows
- Authentication features

## Risk Level
**Smoke** - Critical functionality that must work for basic application usage.
