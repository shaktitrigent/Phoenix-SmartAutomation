# Playwright Locator Strategy — Knowledge Base

> This file defines the locator conventions, priority order, and patterns for all Playwright test automation in this project. Follow these rules when writing, reviewing, or refactoring any Playwright test code.

---

## Golden Rule

**Write locators that read like user instructions.** If a human can follow your locator description to find the element on screen, it is a good locator.

---

## Locator Priority Order

Always attempt locators in this order. Move to the next tier ONLY when the previous tier cannot uniquely identify the element.

### Priority 1 — `get_by_role` (Default Choice)

Use for ANY interactive or semantic element. This is Playwright's top recommendation.

```python
# Buttons
page.get_by_role("button", name="Submit Order")
page.get_by_role("button", name="Submit Order", exact=True)

# Links
page.get_by_role("link", name="Documentation")

# Form inputs (paired with <label>)
page.get_by_role("textbox", name="Email Address")
page.get_by_role("checkbox", name="Remember me")
page.get_by_role("combobox", name="Country").select_option("GB")

# Headings
page.get_by_role("heading", name="Dashboard", level=1)

# Navigation landmarks
page.get_by_role("navigation").get_by_role("link", name="Pricing")

# Table rows
page.get_by_role("row", name="Alice").get_by_role("button", name="Edit")
```

**Key options for `get_by_role`:**

- `name` — Accessible name (label text, aria-label, button text).
- `exact=True` — Exact string match; default is substring.
- `checked` — Filter checkboxes/radios by checked state.
- `disabled` — Filter by disabled state.
- `expanded` — Filter collapsible elements (accordions, dropdowns).
- `level` — Heading level 1–6.
- `pressed` — Toggle-button pressed state.

**Why first:** Survives DOM restructuring, class renames, CSS refactors. Doubles as accessibility validation.

---

### Priority 2 — User-Facing Text Locators

Use when the element lacks a clear ARIA role or when targeting static/non-interactive content.

```python
# Form fields by label (most stable text locator for inputs)
page.get_by_label("Password")
page.get_by_label("Password", exact=True)

# Placeholder text (inputs without visible labels)
page.get_by_placeholder("Search products…")

# Visible text (spans, paragraphs, badges, messages)
page.get_by_text("Welcome back, Alice")
page.get_by_text("Welcome back", exact=False)   # substring

# Image alt text
page.get_by_alt_text("Company Logo")

# Title attribute (tooltips, icon-only buttons)
page.get_by_title("Close dialog")
```

**Selection guide:**

| Locator              | Best For                                 |
|----------------------|------------------------------------------|
| `get_by_label`       | Form fields — most stable text locator   |
| `get_by_placeholder` | Inputs that only have placeholder text   |
| `get_by_text`        | Static content, messages, badges         |
| `get_by_alt_text`    | Images and icons with meaningful alt     |
| `get_by_title`       | Tooltips, icon-only buttons with title   |

**Caution:** Text locators break on copy changes and i18n. Use `exact=True` when substring matching could hit multiple elements.

---

### Priority 3 — `get_by_test_id`

Use for non-semantic elements, dynamic/generated UIs, third-party widgets, or when role/text locators cannot provide a unique match.

```python
page.get_by_test_id("checkout-summary")
page.get_by_test_id("product-card-42")
```

**Custom attribute configuration (conftest.py or playwright config):**

```python
# Change the default attribute from data-testid to data-qa
playwright.selectors.set_test_id_attribute("data-qa")
```

**Naming convention:**

```
component-element[-qualifier]
──────────────────────────────
login-form
login-email-input
login-submit-button
product-card-{id}
nav-menu-item-{slug}
```

**When to use:** Element has no meaningful role or label, generated/dynamic content, canvas wrappers, complex third-party components.

**When NOT to use:** Do not default to test IDs as a crutch when `get_by_role` or `get_by_label` works.

---

### Priority 4 — CSS Selectors

Use when built-in locators lack specificity. Target **stable HTML attributes**, not visual/utility classes.

```python
# ✅ Good — stable, functional attributes
page.locator("input[type='email']")
page.locator("form[name='login']")
page.locator("a[href='/pricing']")
page.locator("[data-status='active']")
page.locator("#main-content")                        # only if ID is stable

# ✅ Good — CSS as a scoping container, then built-in locator
page.locator("form[name='login']").get_by_role("textbox", name="Email")

# ❌ Bad — visual/utility classes break on redesign
page.locator("button.bg-blue-500.rounded-lg")

# ❌ Bad — long chains break on structural changes
page.locator("div.wrapper > ul.list > li:nth-child(3) > a.link")
```

---

### Priority 5 — XPath (Last Resort Only)

Use ONLY when no other strategy works — typically for upward DOM traversal or deeply nested legacy/third-party widgets.

```python
# Navigating to a parent (CSS cannot do this)
page.locator("xpath=//td[text()='Alice']/ancestor::tr//button")

# Combining conditions
page.locator("xpath=//div[@class='card' and .//span[text()='Premium']]")
```

**Always add a comment explaining why XPath is necessary and what would make it replaceable.**

---

## Chaining & Filtering

Use chaining and filtering to narrow scope instead of writing complex CSS or XPath.

### Chaining — Narrow Scope Top-Down

```python
# Scope to a section, then find within it
sidebar = page.get_by_role("complementary")
sidebar.get_by_role("link", name="Settings").click()

# Scope to a specific card
card = page.locator("[data-testid='product-card-42']")
card.get_by_role("button", name="Add to Cart").click()

# Scope to a modal dialog
dialog = page.get_by_role("dialog", name="Confirm deletion")
dialog.get_by_role("button", name="Delete").click()
```

### Filtering — Narrow by Content or Children

```python
# Filter rows by text content
page.get_by_role("row").filter(has_text="Alice").get_by_role("button", name="Edit").click()

# Filter by child locator
page.get_by_role("listitem").filter(
    has=page.get_by_role("img", name="Premium badge")
).click()

# Negative filter — exclude items
page.get_by_role("listitem").filter(has_not_text="Archived")

# Combine multiple filters
page.get_by_role("row").filter(has_text="Alice").filter(has_not_text="Inactive")
```

### Positional Selection (Use Sparingly)

```python
page.get_by_role("listitem").first
page.get_by_role("listitem").last
page.get_by_role("listitem").nth(2)    # 0-indexed
```

> Prefer `.filter()` over `.nth()` — positional selectors break when order changes.

---

## Decision Flowchart

```
Is the element interactive (button, link, input, checkbox, select, etc.)?
│
├── YES → get_by_role(role, name="...")
│         ├── Unique? ✅ Done
│         └── Not unique? → Chain from parent scope or .filter()
│
└── NO → Does it have a visible label, text, or placeholder?
          │
          ├── YES → get_by_label / get_by_text / get_by_placeholder
          │         ├── Unique? ✅ Done
          │         └── Not unique? → Chain or filter
          │
          └── NO → Does it have a data-testid?
                    │
                    ├── YES → get_by_test_id("...")
                    │
                    └── NO → Use a stable CSS attribute
                              page.locator("[data-status='active']")
                              │
                              └── Still can't target?
                                    → Request data-testid from dev team
                                    → XPath only as absolute last resort
```

---

## Anti-Patterns — Do NOT Use

| Anti-Pattern                                  | Why It's Bad                            | Use Instead                                       |
|-----------------------------------------------|-----------------------------------------|---------------------------------------------------|
| `:nth-child(3)`, `:first-child`              | Breaks on DOM reorder                   | `.filter(has_text=...)` or `get_by_role + name`   |
| Long CSS chains `div > ul > li > a`          | Breaks on structural changes            | Chain built-in locators or `data-testid`          |
| Dynamic/auto-generated IDs `#ember-1234`     | Changes every session/build             | `data-testid` or role-based locator               |
| XPath with text `//div[text()='Login']`      | Slower, less readable                   | `get_by_text("Login")` or `get_by_role`           |
| Visual class selectors `.btn-blue`, `.mt-4`  | Break on redesigns / utility CSS swaps  | `get_by_role("button", name="...")`               |
| `page.query_selector` / `page.$`             | No auto-wait, returns ElementHandle     | Always use `page.locator` / `get_by_*`            |
| `page.wait_for_selector`                     | Manual waits are error-prone            | Locators auto-wait; use `expect()` for assertions |
| Hardcoded `time.sleep()` / `asyncio.sleep()` | Flaky, slow                             | Playwright auto-wait or `expect().to_be_visible()`|
| `>>` CSS piercing combinator                 | Hard to debug, confusing                | Explicit `.locator()` chaining                    |

---

## Stability Tiers

| Tier          | Locator Types                                            | Typical Break Triggers                     |
|---------------|----------------------------------------------------------|--------------------------------------------|
| 🟢 Stable     | `get_by_role`, `get_by_label`, `get_by_test_id`         | Accessibility contract or test-id change   |
| 🟡 Moderate   | `get_by_text`, `get_by_placeholder`, stable CSS attrs    | Copy changes, i18n, placeholder edits      |
| 🔴 Fragile    | XPath, positional CSS, visual classes, dynamic IDs       | Any DOM or styling refactor                |

---

## Common Patterns — Quick Reference

### Login Form

```python
page.get_by_role("textbox", name="Email").fill("user@example.com")
page.get_by_role("textbox", name="Password").fill("secret")    # or get_by_label("Password")
page.get_by_role("button", name="Sign in").click()
```

### Data Table — Act on a Specific Row

```python
row = page.get_by_role("row").filter(has_text="Alice Johnson")
row.get_by_role("button", name="Edit").click()
```

### Modal / Dialog

```python
dialog = page.get_by_role("dialog", name="Delete confirmation")
dialog.get_by_role("button", name="Confirm").click()
```

### Navigation

```python
page.get_by_role("navigation").get_by_role("link", name="Settings").click()
```

### Dropdown / Select

```python
page.get_by_role("combobox", name="Country").select_option("GB")
```

### Search

```python
page.get_by_role("searchbox", name="Search").fill("playwright")
page.get_by_role("searchbox", name="Search").press("Enter")
```

### File Upload

```python
page.get_by_label("Upload document").set_input_files("report.pdf")
```

### Assertions

```python
from playwright.sync_api import expect

expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
expect(page.get_by_role("alert")).to_contain_text("Saved successfully")
expect(page.get_by_role("button", name="Submit")).to_be_enabled()
expect(page.get_by_role("row")).to_have_count(5)
```

---

## Tooling Tips

- **Codegen:** Run `playwright codegen <url>` to auto-discover locators, then refine by hand using this priority order.
- **Inspector:** Run with `PWDEBUG=1` to step through tests and validate locator uniqueness in the Playwright Inspector.
- **Trace Viewer:** Use `playwright show-trace trace.zip` to debug locator failures post-run.
- **Strict mode:** Playwright throws if a locator matches multiple elements. This is intentional — fix ambiguity with chaining or filtering, never suppress it.

---

## Rules for AI Code Generation

When generating Playwright test code, follow these rules strictly:

1. **Follow the v2.0 locator priority — in this order:**
   1. `[data-testid="..."]` — always preferred when present
   2. `#stable-id` — only IDs without framework-generated digit patterns (`ember*`, `react-select-*`)
   3. `[name="field"]` — reliable for form inputs
   4. `get_by_placeholder()` — placeholder text from the DOM snapshot
   5. `get_by_label()` — ONLY when the DOM snapshot shows a real `<label>` or `aria-labelledby`
   6. `get_by_role()` — scoped to a container; last resort for interactive elements
   7. `get_by_text()` — only for static read-only text: ≤ 6 words, no action verbs, verbatim in the DOM snapshot

2. **Every locator must be traceable to the DOM snapshot.** If the element is absent from the snapshot, mark it `# UNGROUNDABLE` — never guess.

3. **Never use criterion/step prose as a locator.** Text from the manual test step describes intent, not DOM state.

4. **Never generate `page.query_selector`, `page.$`, or `page.wait_for_selector`.** Use `page.locator` / `get_by_*` with `expect()` assertions.

5. **Never generate `time.sleep()`, `asyncio.sleep()`, or `wait_for_load_state("networkidle")`.**

6. **Never use visual/utility CSS classes** (`.btn-primary`, `.mt-4`, `.flex`, `.oxd-*`, `.mat-*`).

7. **Never use dynamic/framework-generated IDs** (`ember123`, `react-select-2`, `ng-model-1`).

8. **Never use XPath.** If there is genuinely no other option, add an inline comment explaining why and what would replace it.

9. **When an element is not unique,** chain from a scoped parent container or use `.filter()` — never suppress the strict mode error.

10. **Use `expect()` for all assertions** — never use raw `assert` with locator state checks.