# Playwright Waiting Rules — Knowledge Base

> This file defines the waiting, synchronization, and timeout conventions for all Playwright test automation in this project. Follow these rules when writing, reviewing, or refactoring any Playwright test code.

---

## Golden Rule

**Never add a sleep to fix a flaky test.** Fix the locator, fix the assertion, or wait for the right condition. Playwright's auto-wait handles the vast majority of timing issues — a `sleep` is almost always masking the real problem.

---

## 1. Auto-Waiting — How Playwright Works by Default

Playwright auto-waits before performing any action. Understanding what it waits for prevents unnecessary explicit waits.

### What Auto-Wait Covers

| Action                  | Playwright waits until…                                           |
|-------------------------|-------------------------------------------------------------------|
| `.click()`              | Element is visible, stable, enabled, and receives events          |
| `.fill()`               | Element is visible, enabled, and editable                         |
| `.check()` / `.uncheck()` | Element is visible, stable, enabled, and not already in target state |
| `.select_option()`      | Element is visible, enabled                                       |
| `.press()`              | Element is visible, enabled, and focused                          |
| `.type()`               | Element is visible, enabled, and focused                          |
| `.set_input_files()`    | Element is visible and is an `<input type="file">`                |
| `expect(loc).to_be_visible()` | Element appears in DOM and is visible (retries until timeout) |
| `expect(loc).to_have_text()` | Element text matches (retries until timeout)                 |
| `page.goto()`           | Page reaches `load` state (configurable)                          |

### What This Means for You

```python
# ✅ Correct — just act; Playwright waits automatically
page.get_by_role("button", name="Submit").click()

# ❌ Wrong — redundant manual wait before action
page.get_by_role("button", name="Submit").wait_for(state="visible")   # unnecessary
page.get_by_role("button", name="Submit").click()

# ❌ Wrong — sleep before action
import time
time.sleep(2)
page.get_by_role("button", name="Submit").click()
```

> You do NOT need to wait before actions. Just perform the action — Playwright handles the timing.

---

## 2. Assertion-Based Waiting — The Correct Approach

Instead of "wait → act", use "act → assert". Playwright's `expect()` retries the assertion until it passes or times out.

### Navigation

```python
import re

# ✅ Click then assert the URL changed
page.get_by_role("link", name="Dashboard").click()
expect(page).to_have_url(re.compile(r".*/dashboard"))

# ✅ Goto then assert content loaded
page.goto(f"{base_url}/settings")
expect(page.get_by_role("heading", name="Settings")).to_be_visible()

# ❌ Wrong — sleep after navigation
page.get_by_role("link", name="Dashboard").click()
time.sleep(3)
assert "dashboard" in page.url
```

### Dynamic Content (Loading Spinners, Lazy-Loaded Data)

```python
# ✅ Assert the final state — Playwright retries until content appears
page.get_by_role("button", name="Load More").click()
expect(page.get_by_role("row")).to_have_count(20)

# ✅ Wait for loading indicator to disappear, then assert
expect(page.get_by_test_id("loading-spinner")).to_be_hidden()
expect(page.get_by_role("table")).to_be_visible()

# ❌ Wrong — arbitrary sleep for "loading time"
page.get_by_role("button", name="Load More").click()
time.sleep(5)
rows = page.get_by_role("row").count()
assert rows == 20
```

### Form Submission

```python
# ✅ Submit then assert the outcome
page.get_by_role("button", name="Save").click()
expect(page.get_by_role("alert")).to_contain_text("Saved successfully")

# ❌ Wrong — sleep after submit
page.get_by_role("button", name="Save").click()
time.sleep(2)
assert page.get_by_role("alert").text_content() == "Saved successfully"
```

### Element Appears/Disappears

```python
# ✅ Wait for appearance
expect(page.get_by_role("dialog", name="Confirm")).to_be_visible()

# ✅ Wait for disappearance
expect(page.get_by_role("dialog", name="Confirm")).to_be_hidden()

# ✅ Wait for element to detach from DOM entirely
expect(page.get_by_test_id("loading-overlay")).not_to_be_attached()
```

---

## 3. Explicit Waits — When They Are Appropriate

Some scenarios genuinely require explicit waits. These are the **only** acceptable cases.

### 3a. Dialogs (Alert, Confirm, Prompt)

Register the listener **before** the action that triggers the dialog. Dialogs are synchronous browser events — if you don't listen before they fire, they're missed.

```python
# ✅ Single alert — accept
page.once("dialog", lambda d: d.accept())
page.get_by_role("button", name="Delete").click()

# ✅ Single confirm — dismiss
page.once("dialog", lambda d: d.dismiss())
page.get_by_role("button", name="Reset").click()

# ✅ Prompt — accept with input
page.once("dialog", lambda d: d.accept("My input text"))
page.get_by_role("button", name="Rename").click()

# ✅ Assert dialog message before accepting
def handle_dialog(dialog):
    assert dialog.message == "Are you sure?"
    dialog.accept()

page.once("dialog", handle_dialog)
page.get_by_role("button", name="Delete").click()
```

**Dialog rules:**
- Always use `page.once("dialog", ...)` for single dialogs — prevents "already handled" errors.
- Use `page.on("dialog", ...)` only when multiple sequential dialogs are expected, and remove the listener afterward with `page.remove_listener("dialog", handler)`.
- Never accept/dismiss the same dialog more than once.
- Always register the handler **before** the click that triggers the dialog.
- Never use `time.sleep()` to "wait for the dialog to appear".

### 3b. New Tabs / Popups

```python
# ✅ Wait for the new page event
with context.expect_page() as new_page_info:
    page.get_by_role("link", name="Open in new tab").click()

new_page = new_page_info.value
new_page.wait_for_load_state()
expect(new_page).to_have_url(re.compile(r".*/external"))
expect(new_page.get_by_role("heading", name="External Page")).to_be_visible()
```

### 3c. Downloads

```python
# ✅ Wait for the download event
with page.expect_download() as download_info:
    page.get_by_role("button", name="Export CSV").click()

download = download_info.value
assert download.suggested_filename.endswith(".csv")
```

### 3d. Network Requests (API Calls)

```python
# ✅ Wait for a specific API response
with page.expect_response(
    lambda r: "/api/users" in r.url and r.status == 200
) as response_info:
    page.get_by_role("button", name="Refresh").click()

response = response_info.value
data = response.json()
assert len(data["users"]) > 0

# ✅ Wait for network idle after a complex action
page.get_by_role("button", name="Load Dashboard").click()
page.wait_for_load_state("networkidle")
expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
```

### 3e. File Chooser

```python
# ✅ Wait for file chooser event
with page.expect_file_chooser() as fc_info:
    page.get_by_role("button", name="Upload").click()

file_chooser = fc_info.value
file_chooser.set_files("report.pdf")
```

### 3f. Animations / Known Delays (Rare)

Only when a UI animation or debounce has a documented delay that Playwright cannot auto-detect:

```python
# ✅ Acceptable — documented animation delay
page.get_by_role("button", name="Toggle sidebar").click()
# Sidebar has a 500ms CSS transition that Playwright's stability check doesn't cover
page.wait_for_timeout(600)  # Known animation: 500ms slide + 100ms buffer
expect(page.get_by_role("navigation", name="Sidebar")).to_be_visible()
```

> Every `wait_for_timeout` MUST have an inline comment explaining the specific timing requirement. If you can't explain it, you don't need it.

---

## 4. Timeouts — Configuration and Overrides

### Default Timeouts (Production-Tuned)

> **IMPORTANT**: Demo/staging sites are significantly slower than production. Always use these
> minimums when generating scripts for external test applications.

| Scope              | Minimum    | What it covers                                    |
|--------------------|------------|---------------------------------------------------|
| Navigation timeout | 120,000ms  | `.goto()`, `page.wait_for_url()`                  |
| Action timeout     | 30,000ms   | `.click()`, `.fill()`, `.check()`, etc.           |
| Assertion timeout  | 10,000ms   | `expect()` retries                                |

**Never use the Playwright default 30s for `page.goto()`** — demo sites like OrangeHRM, Demoblaze,
and Maxima Apparel routinely take 30–90 seconds to load.

```python
# CORRECT — always pass explicit timeout to goto() for demo/staging apps
page.goto(base_url, timeout=120_000)

# CORRECT — override default timeouts at test start for slow apps
page.set_default_timeout(30_000)
page.set_default_navigation_timeout(120_000)
```

### Per-Action Override

Use when a specific action is known to be slower than default:

```python
# Slow API behind the button — override just this action
page.get_by_role("button", name="Generate Report").click(timeout=30_000)

# Slow page load
expect(page.get_by_role("heading", name="Report")).to_be_visible(timeout=30_000)
# Reason: report generation takes up to 25 seconds
```

### Per-Page Override

Use when an entire page is consistently slow:

```python
# Set for this page instance (affects all actions on this page)
page.set_default_timeout(60_000)

# Set navigation timeout separately
page.set_default_navigation_timeout(60_000)
```

### Global Override (conftest.py)

Use for known slow environments (e.g., remote staging, CI with limited resources):

```python
# conftest.py
import pytest

@pytest.fixture(autouse=True)
def configure_timeouts(page):
    page.set_default_timeout(
        int(os.environ.get("PW_DEFAULT_TIMEOUT", "30000"))
    )
    page.set_default_navigation_timeout(
        int(os.environ.get("PW_NAV_TIMEOUT", "30000"))
    )
    yield
```

### Timeout Rules

- Never increase the global timeout just to make flaky tests pass — fix the root cause.
- Per-action overrides are preferred over per-page or global overrides.
- Always add an inline comment explaining **why** the timeout is overridden.
- Use environment variables for CI vs local differences — never hardcode CI-specific timeouts.

---

## 5. Load States

Playwright supports three load states. Choose the right one based on what you're waiting for.

```python
# Wait for DOM content loaded (HTML parsed, deferred scripts executed)
page.wait_for_load_state("domcontentloaded")

# Wait for full load (all resources including images, stylesheets)
page.wait_for_load_state("load")     # default for page.goto()

# Wait for network idle (no requests for 500ms — useful for SPAs)
page.wait_for_load_state("networkidle")
```

| State               | Use When                                                         |
|----------------------|------------------------------------------------------------------|
| `domcontentloaded`   | You only need the HTML/DOM; don't care about images/fonts        |
| `load`               | Default — appropriate for most navigation                        |
| `networkidle`        | SPA that fires many API calls after initial load — **use sparingly** |

**Rules:**
- `page.goto()` waits for `load` by default — you rarely need to add an explicit load state wait after goto.
- **NEVER use `networkidle` on sites with continuous background requests** (Demoblaze, sites with analytics, websockets) — the state is never reached and the test hangs.
- Prefer asserting on visible content over waiting for load states.

```python
# WRONG — Demoblaze makes continuous background requests; networkidle never fires
page.wait_for_load_state("networkidle")

# CORRECT — wait for the specific element you need
expect(page.get_by_role("link", name="Add to cart")).to_be_visible()
# or wait for navigation to complete
page.wait_for_url("**/cart**")
```

---

## 6. Waiting for Element State (Rare Cases)

Use `locator.wait_for()` only when you need to wait for an element state **without performing an action or assertion**. This is rare.

```python
# ✅ Acceptable — waiting for element to exist before reading its attribute
page.get_by_test_id("dynamic-widget").wait_for(state="attached")
value = page.get_by_test_id("dynamic-widget").get_attribute("data-config")

# ✅ Acceptable — waiting for element to disappear before continuing a flow
page.get_by_test_id("upload-progress").wait_for(state="hidden")
page.get_by_role("button", name="Submit Form").click()
```

**States available:**

| State      | Meaning                               |
|------------|---------------------------------------|
| `visible`  | Element is in DOM and visible         |
| `hidden`   | Element is either not in DOM or not visible |
| `attached` | Element is in DOM (may be invisible)  |
| `detached` | Element is not in DOM                 |

> In 95% of cases, use `expect(locator).to_be_visible()` or `expect(locator).to_be_hidden()` instead. `wait_for` is for the rare case where you need to gate non-assertion logic.

---

## 7. Keyboard and Slider Interactions

For widgets that respond to keyboard input (sliders, steppers, custom controls):

```python
# ✅ Correct — act then assert; no sleep between keypresses
slider = page.get_by_role("slider", name="Volume")
slider.click()
slider.press("ArrowRight")
slider.press("ArrowRight")
slider.press("ArrowRight")
expect(slider).to_have_attribute("aria-valuenow", "30")

# ✅ Correct — if the widget has a known debounce, use a single targeted wait
slider.press("ArrowRight")
# Widget debounces value updates by 300ms
page.wait_for_timeout(400)  # Known debounce: 300ms + 100ms buffer
expect(slider).to_have_attribute("aria-valuenow", "30")

# ❌ Wrong — sleep between every keypress
slider.press("ArrowRight")
time.sleep(0.5)
slider.press("ArrowRight")
time.sleep(0.5)
```

---

## 8. Retry Patterns for Flaky Scenarios

When a test is genuinely flaky due to external factors (unstable staging, third-party services), prefer Playwright's built-in retry over manual loops:

### Pytest Retry Plugin (Preferred for CI)

```bash
pip install pytest-rerunfailures
pytest --reruns 2 --reruns-delay 5
```

### Assertion Retry (Built-In)

`expect()` already retries automatically. Increase timeout for known-slow operations:

```python
# Retries for up to 15 seconds
expect(page.get_by_role("alert")).to_contain_text("processed", timeout=15_000)
```

### Manual Retry (Last Resort)

```python
# ✅ Only for non-assertion waits (e.g., polling an API)
from playwright.sync_api import expect
import time

for attempt in range(5):
    page.get_by_role("button", name="Refresh").click()
    try:
        expect(page.get_by_text("Complete")).to_be_visible(timeout=3_000)
        break
    except AssertionError:
        if attempt == 4:
            raise
        # Retry: external system may not have processed yet
```

---

## Anti-Patterns — Never Generate These

| Anti-Pattern                                         | Why                                          | Correct Alternative                                   |
|------------------------------------------------------|----------------------------------------------|-------------------------------------------------------|
| `time.sleep(n)` / `asyncio.sleep(n)`                | No auto-retry, arbitrary, flaky              | `expect()` assertion or `page.wait_for_timeout()` with comment |
| `page.wait_for_timeout(n)` without comment           | Hides intent; becomes tech debt              | Add inline comment or replace with assertion           |
| `locator.wait_for(state="visible")` before `.click()`| Redundant — `.click()` auto-waits            | Just call `.click()`                                   |
| `expect()` after `time.sleep()`                      | Defeats auto-retry; slow and flaky           | Just use `expect()` — it retries internally            |
| Increasing global timeout to fix one flaky test       | Slows all tests, masks root cause            | Per-action `timeout=` on the specific call             |
| `while True` polling loop without timeout             | Can hang forever                             | Bounded retry with `range()` and explicit raise        |
| `page.wait_for_load_state("networkidle")` everywhere | Flaky with websockets, polling, analytics    | Assert on visible content instead                      |
| Dialog handler registered after the triggering click  | Dialog fires before listener is ready        | Always register `page.once("dialog", ...)` before click|

---

## Decision Flowchart — Do I Need an Explicit Wait?

```
I'm about to perform a Playwright action or assertion.
│
├── Is it a standard action (.click, .fill, .check, etc.)?
│   └── NO explicit wait needed. Playwright auto-waits. Just call it.
│
├── Is it an expect() assertion?
│   └── NO explicit wait needed. expect() retries automatically.
│       └── Too slow? → Increase timeout= on that specific assertion.
│
├── Am I waiting for a browser dialog (alert/confirm/prompt)?
│   └── Register page.once("dialog", handler) BEFORE the triggering click.
│
├── Am I waiting for a new tab/popup?
│   └── Use context.expect_page() as a context manager around the click.
│
├── Am I waiting for a download?
│   └── Use page.expect_download() as a context manager around the click.
│
├── Am I waiting for a specific API response?
│   └── Use page.expect_response(predicate) as a context manager.
│
├── Am I waiting for an animation/transition with a known duration?
│   └── Use page.wait_for_timeout(ms) WITH an inline comment explaining the delay.
│
└── None of the above?
    └── You probably don't need an explicit wait.
        Assert on the final visible state with expect().
```

---

## Rules for AI Code Generation

When generating or modifying Playwright test scripts, follow these waiting rules strictly:

1. **Never generate `time.sleep()` or `asyncio.sleep()`.** These are unconditionally forbidden in Playwright tests.
2. **Never generate `page.wait_for_timeout()` without an inline comment** explaining the specific, documented timing requirement (animation, debounce, known API delay).
3. **Never generate redundant waits before actions.** Do not add `wait_for(state="visible")` before `.click()`, `.fill()`, or any auto-waiting action.
4. **Never generate `page.wait_for_selector()`.** Use `expect(locator).to_be_visible()` or `expect(locator).to_be_hidden()` instead.
5. **Always register dialog handlers before the triggering action.** Use `page.once("dialog", lambda d: d.accept())` — never `page.on()` without cleanup.
6. **Use context managers for events** — `context.expect_page()`, `page.expect_download()`, `page.expect_response()` — always wrapping the triggering action.
7. **Use `expect()` for all post-action verification.** Never read `locator.text_content()` or `page.url` directly after an action — these don't retry.
8. **Per-action timeout overrides over global changes.** If a specific operation is slow, use `timeout=` on that call, not `page.set_default_timeout()`.
9. **Always add `import re` when using regex** in `expect(page).to_have_url(re.compile(...))`.
10. **For flaky external dependencies**, prefer `pytest-rerunfailures` or assertion timeout increases over manual retry loops.
11. **After navigation, assert on visible content** — `expect(heading).to_be_visible()` — not on `page.wait_for_load_state("networkidle")`.
12. **For keyboard/slider interactions**, act then assert. No sleep between keypresses unless there is a documented debounce, in which case use `page.wait_for_timeout(ms)` with a comment.