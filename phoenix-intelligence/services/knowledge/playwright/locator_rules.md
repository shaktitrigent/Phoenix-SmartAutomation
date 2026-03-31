# Playwright Locator Rules — Knowledge Base

> Concise, enforceable rules for selecting and using locators in generated Playwright test scripts. For detailed examples and the full strategy guide, see `playwright-locator-strategy.md`.

---

## Priority Order (Use in This Order — No Skipping)

Attempt each tier in order. Move to the next ONLY when the current tier cannot uniquely identify the element.

### 1. `get_by_role` — Default Choice for All Interactive Elements

```python
page.get_by_role("button", name="Submit")
page.get_by_role("textbox", name="Email")
page.get_by_role("link", name="Dashboard")
page.get_by_role("checkbox", name="Remember me")
page.get_by_role("combobox", name="Country")
page.get_by_role("heading", name="Settings", level=2)
page.get_by_role("row", name="Alice").get_by_role("button", name="Edit")
```

**Rules:**
- Always provide `name=` for specificity.
- Use `exact=True` when the name could substring-match other elements.
- Use key options: `checked`, `disabled`, `expanded`, `level`, `pressed` to narrow further.
- If multiple elements share the same role+name, **chain from a scoped parent or use `.filter()`** — do not jump to CSS/XPath.

---

### 2. `get_by_label` — Primary Choice for Form Fields

```python
page.get_by_label("Email Address")
page.get_by_label("Password", exact=True)
page.get_by_label("Start date")
```

**Rules:**
- Prefer `get_by_label` over `get_by_placeholder` when both exist.
- Use `exact=True` when labels share common substrings (e.g., "Date" vs "Start Date").
- Works with `<label for="...">`, wrapping `<label>`, and `aria-labelledby`.

---

### 3. `get_by_placeholder` — Inputs Without Visible Labels

```python
page.get_by_placeholder("Search products…")
page.get_by_placeholder("Enter email")
```

**Rules:**
- Use only when no `<label>` or `aria-label` is associated with the input.
- Avoid if placeholder text is likely to change (A/B tests, i18n).

---

### 4. `get_by_text` — Visible, Unique Text Content

```python
page.get_by_text("Welcome back, Alice")
page.get_by_text("Submit", exact=True)
```

**Rules:**
- Use for static, non-interactive content (messages, badges, headings without `heading` role).
- For buttons and links, **prefer `get_by_role` over `get_by_text`** — roles are more stable.
- Always use `exact=True` when the text could substring-match unintended elements.
- Avoid for long text, translated text, or dynamically generated text.

---

### 5. `get_by_alt_text` / `get_by_title` — Images and Tooltips

```python
page.get_by_alt_text("Company Logo")
page.get_by_title("Close dialog")
```

**Rules:**
- `get_by_alt_text` — images and icons with meaningful `alt` attributes.
- `get_by_title` — icon-only buttons or elements with `title` tooltip attributes.

---

### 6. `get_by_test_id` — Non-Semantic or Dynamic Elements

```python
page.get_by_test_id("checkout-summary")
page.get_by_test_id("product-card-42")
```

**Rules:**
- Use when the element has no meaningful role, label, or text.
- Use for dynamic/generated UIs, canvas wrappers, third-party widgets.
- **Do not use test IDs as a shortcut when `get_by_role` or `get_by_label` works.**
- Follow naming convention: `component-element[-qualifier]` (e.g., `login-submit-button`, `product-card-{id}`).
- Custom attribute is configurable: `playwright.selectors.set_test_id_attribute("data-qa")`.

---

### 7. CSS Selectors — Stable Attributes Only

```python
# ✅ Allowed — stable, functional attributes
page.locator("input[type='email']")
page.locator("form[name='login']")
page.locator("a[href='/pricing']")
page.locator("[data-status='active']")
page.locator("#main-content")

# ✅ Allowed — CSS scoping + built-in locator
page.locator("form[name='login']").get_by_role("textbox", name="Email")

# ❌ Forbidden — visual/utility classes
page.locator("button.bg-blue-500.rounded-lg")
page.locator(".mt-4.flex.justify-between")

# ❌ Forbidden — deep nesting / layout classes
page.locator("div.wrapper > section > ul > li > a")
page.locator(".col-md-2 .card .btn")
```

**Rules:**
- Only use CSS for **stable HTML attributes**: `type`, `name`, `href`, `data-*`, stable `id`.
- Never use layout/utility classes (`.col-md-2`, `.flex`, `.mt-4`, `.btn-primary`).
- Never write chains deeper than 2 levels — use chaining/filtering instead.

---

### 8. XPath — Absolute Last Resort

```python
page.locator("xpath=//td[text()='Alice']/ancestor::tr//button")
```

**Rules:**
- Use ONLY when upward DOM traversal is required (CSS cannot do `parent`/`ancestor`).
- Prefer short, attribute-based XPath over structure-based.
- **Always add an inline comment** explaining why XPath is necessary and what would replace it.
- Never use `xpath=//*[text()='...']` — use `get_by_text()` instead.

---

## Strict Mode and Uniqueness

Playwright enforces strict mode: a locator **must resolve to exactly one element**. If it matches multiple, the action throws.

**Resolution strategy (in order):**

```python
# 1. Chain from a scoped parent
page.get_by_role("navigation").get_by_role("link", name="Home")

# 2. Use .filter() to narrow
page.get_by_role("row").filter(has_text="Alice").get_by_role("button", name="Edit")

# 3. Use .filter(has=...) for child-based narrowing
page.get_by_role("listitem").filter(
    has=page.get_by_role("img", name="Premium badge")
)

# 4. Use exact=True for text disambiguation
page.get_by_role("button", name="Submit Order", exact=True)

# 5. Use .first / .last / .nth() ONLY when intent is explicitly positional
page.get_by_role("listitem").first    # genuinely want the first item
```

**Rules:**
- Never suppress strict mode errors — fix the locator.
- Prefer `.filter()` over `.nth()` — positional selectors break when order changes.
- Use `.first` / `.last` only when the test genuinely targets a positional element (e.g., "first item in a list").

---

## Chaining and Filtering

Use chaining and filtering as the **primary tool for disambiguation** — not complex selectors.

### Chaining — Scope Top-Down

```python
# Scope to a section
sidebar = page.get_by_role("complementary")
sidebar.get_by_role("link", name="Settings").click()

# Scope to a dialog
dialog = page.get_by_role("dialog", name="Confirm")
dialog.get_by_role("button", name="Delete").click()

# Scope to a form
form = page.locator("form[name='checkout']")
form.get_by_role("textbox", name="Card number").fill("4242...")
```

### Filtering — Narrow by Content or Children

```python
# By text content
page.get_by_role("row").filter(has_text="Alice").get_by_role("button", name="Edit")

# By child element
page.get_by_role("listitem").filter(has=page.get_by_text("Premium"))

# Negative filter
page.get_by_role("listitem").filter(has_not_text="Archived")

# Combine filters
page.get_by_role("row").filter(has_text="Alice").filter(has_not_text="Inactive")
```

---

## Element-Specific Rules

### Buttons

```python
# ✅ Primary approach
page.get_by_role("button", name="Submit")

# ✅ If button is inside a specific form/section
page.locator("form[name='login']").get_by_role("button", name="Submit")

# ✅ Icon-only button with aria-label
page.get_by_role("button", name="Close")     # reads aria-label

# ❌ Avoid
page.locator("button.btn-primary")
```

### Links

```python
# ✅ Primary approach
page.get_by_role("link", name="Documentation")

# ✅ Scoped navigation link
page.get_by_role("navigation").get_by_role("link", name="Pricing")
```

### Text Inputs

```python
# ✅ With label (preferred)
page.get_by_label("Email Address")
page.get_by_role("textbox", name="Email Address")

# ✅ Without label (fallback)
page.get_by_placeholder("Enter email")

# ❌ Avoid
page.locator("input.email-field")
```

### Dropdowns / Select

```python
# ✅ Standard <select>
page.get_by_label("Country").select_option("GB")
page.get_by_role("combobox", name="Country").select_option(label="United Kingdom")

# ✅ Custom dropdown (non-native)
page.get_by_role("combobox", name="Country").click()
page.get_by_role("option", name="United Kingdom").click()
```

### Checkboxes and Radios

```python
# ✅ By label
page.get_by_role("checkbox", name="Accept terms").check()
page.get_by_role("radio", name="Express shipping").check()

# ✅ Filter by state
page.get_by_role("checkbox").filter(has_text="Marketing").check()
```

### File Inputs

```python
# ✅ With label
page.get_by_label("Upload document").set_input_files("report.pdf")

# ✅ Without label (fallback)
page.locator("input[type='file']").set_input_files("report.pdf")

# ✅ Multiple files
page.get_by_label("Attachments").set_input_files(["doc1.pdf", "doc2.pdf"])
```

### Dialogs / Modals

```python
# ✅ Scope to dialog, then act within it
dialog = page.get_by_role("dialog", name="Delete confirmation")
dialog.get_by_role("button", name="Confirm").click()
```

### Alerts and Toasts

```python
# ✅ Role-based
page.get_by_role("alert")
page.get_by_role("status")

# ✅ With text filtering
page.get_by_role("alert").filter(has_text="saved")
```

### Tables

```python
# ✅ Target a specific row by content, then act
row = page.get_by_role("row").filter(has_text="Alice Johnson")
row.get_by_role("button", name="Edit").click()

# ✅ Specific cell
row.get_by_role("cell").nth(2)
```

---

## Anti-Patterns — Never Generate These

| Anti-Pattern                              | Why                                     | Correct Alternative                              |
|-------------------------------------------|-----------------------------------------|--------------------------------------------------|
| `page.query_selector("...")` / `page.$`   | No auto-wait, returns ElementHandle     | `page.locator(...)` / `get_by_*`                 |
| `page.wait_for_selector("...")`           | Manual waits are error-prone            | `expect(locator).to_be_visible()`                |
| `time.sleep()` / `asyncio.sleep()`        | Flaky and slow                          | Playwright auto-wait / `expect()` assertions     |
| `:nth-child(3)`, `:first-child`           | Breaks on DOM reorder                   | `.filter(has_text=...)` or `get_by_role + name`  |
| `div > ul > li > a` deep chains           | Breaks on structural changes            | Chain built-in locators or `data-testid`         |
| `xpath=//*[text()='Login']`               | Slower, less readable                   | `get_by_text("Login")`                           |
| `.btn-primary`, `.bg-blue-500`            | Breaks on redesign / CSS changes        | `get_by_role("button", name="...")`              |
| Auto-generated IDs `#ember-1234`          | Changes per session/build               | `get_by_test_id(...)` or `get_by_role(...)`      |
| `locator.text_content()` in raw assert    | No auto-wait                            | `expect(locator).to_have_text(...)`              |
| `locator.is_visible()` in raw assert      | No auto-wait                            | `expect(locator).to_be_visible()`                |

---

## Rules for AI Code Generation

When generating or modifying Playwright locators, follow these rules strictly:

1. **Always start with `get_by_role`.** Only fall to lower priorities when role-based cannot work.
2. **Always provide `name=`** with `get_by_role` for specificity.
3. **Use `get_by_label` for form fields** when a label exists. Prefer it over `get_by_placeholder`.
4. **Use `get_by_test_id` only for non-semantic/dynamic elements** — never as a shortcut when role or label works.
5. **Never generate `page.query_selector`, `page.$`, `page.wait_for_selector`, `time.sleep()`, or `asyncio.sleep()`.**
6. **Never use visual/utility CSS classes** in locators.
7. **Never write CSS chains deeper than 2 levels.** Use chaining and filtering instead.
8. **Resolve strict mode violations** with scoping, filtering, or `exact=True` — never suppress the error.
9. **Prefer `.filter()` over `.nth()`** — positional selectors are fragile.
10. **If forced to use CSS or XPath**, add an inline `# comment` explaining why and what would replace it.
11. **Use `exact=True`** when text could substring-match unintended elements.
12. **For dropdowns**, use `get_by_label(...).select_option(...)` or `get_by_role("combobox", name=...)`.
13. **For file inputs**, use `get_by_label(...).set_input_files(...)` or `locator("input[type='file']").set_input_files(...)`.
14. **For dialogs/modals**, always scope with `get_by_role("dialog", name=...)` before targeting child elements.