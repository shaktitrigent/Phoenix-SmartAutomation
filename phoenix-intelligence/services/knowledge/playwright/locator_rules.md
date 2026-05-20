# Playwright Locator Rules — Knowledge Base

> Concise, enforceable rules for selecting and using locators in generated Playwright test scripts. For detailed examples and the full strategy guide, see `playwright-locator-strategy.md`.

---

## Priority Order (Use in This Order — No Skipping)

Attempt each tier in order. Move to the next ONLY when the current tier cannot uniquely identify the element.

Phoenix generation priority is:
1. `get_by_role()`
2. `get_by_label()`
3. `get_by_placeholder()`
4. Stable CSS selectors using `name`, `type`, `href`, `id`, or `data-*`
5. `get_by_test_id()`
6. Snapshot-backed locators derived from the inspected DOM

Never convert manual-test narration such as `Dashboard loads successfully` or `fields are visible`
into locator text. If no stable DOM-backed locator exists, emit a manual-review warning instead.

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

## Real-World Failure Patterns (From Production Test Reports)

These patterns caused failures across SauceDemo, OrangeHRM, Maxima Apparel, DemoQA, and Demoblaze.
**Never generate these:**

### 1. Bare `locator("form")` — matches hidden localization forms

```python
# WRONG — matched hidden #HeaderCountryMobileForm instead of Contact Us form
page.locator("form").first.fill(...)

# CORRECT — scope by form action or proximity to a heading
page.locator("form[action*='contact']").fill(...)
page.get_by_role("heading", name="Contact Us").locator("..").locator("form")
```

### 2. `input[type='search']` without scoping — matches hidden country filter

```python
# WRONG — matched hidden #country-filter-input
page.locator("input[type='search']").fill("keyword")

# CORRECT — scope to the visible header
page.locator("header input[type='search']").fill("keyword")
page.get_by_placeholder("Search").fill("keyword")
```

### 3. CSS-class-only dropdown selector — matches hidden wrapper

```python
# WRONG — matched hidden div.disclosure__list-wrapper (Shopify)
page.locator(".country-selector").click()

# CORRECT — click the trigger button, then interact with options
page.locator("button[aria-controls='country-selector']").click()
page.get_by_role("option", name="United States").click()
```

### 4. `get_by_label` when field has no `<label>` (OrangeHRM)

```python
# WRONG — OrangeHRM username field has no <label>, only a placeholder
page.get_by_label("Username").fill("Admin")

# CORRECT
page.get_by_placeholder("Username").fill("Admin")
page.locator("input[name='username']").fill("Admin")
```

### 5. `get_by_label` for custom Vue/React dropdowns

```python
# WRONG — OrangeHRM uses custom Vue dropdowns, not native <select>
page.get_by_label("Leave Type").select_option("Annual")

# CORRECT — click trigger to open, then select option
page.get_by_role("combobox", name="Leave Type").click()
page.get_by_role("option", name="Annual Leave").click()
```

### 6. `get_by_role("link", name="2")` for cart badge count

```python
# WRONG — cart badge count is display-only text, not a link name
page.get_by_role("link", name="2").click()

# CORRECT — target the cart link element directly
page.locator(".shopping_cart_link").click()
page.locator("[data-test='shopping-cart-link']").click()
```

### 7. `get_by_role("heading")` for non-heading elements

```python
# WRONG — SauceDemo "Products" is a <span class="title">, not a heading
page.get_by_role("heading", name="Products")

# CORRECT
page.locator(".inventory_list")  # assert container is visible
page.locator("[data-test='inventory-container']")
page.locator(".title").filter(has_text="Products")
```

### 8. Strict mode violation from non-unique class selectors

```python
# WRONG — .inventory_item_img matches both the <div> and the <img>
page.locator(".inventory_item").first.locator(".inventory_item_img").click()

# CORRECT — use a unique data-test attribute
page.locator("[data-test='item-4-title-link']").click()
```

---

## Framework-Specific Patterns

### Shopify / Liquid Sites (Maxima Apparel)
- Hidden localization forms (`#HeaderCountryMobileForm`) exist alongside visible forms — always scope by `form[action*='contact']` or by proximity to headings.
- Country/region selectors use Shopify's disclosure pattern: there is a hidden `div.disclosure__list-wrapper` and a visible trigger `<button>`. Always click the `<button>` trigger.
- Search bar: scope to `header` to avoid matching the hidden country-filter input.

### OrangeHRM (Vue.js framework)
- Login fields: use `input[name='username']` and `input[name='password']` — no `<label>` elements exist.
- All dropdowns are custom Vue components: use `get_by_role("combobox", name=...)` then `get_by_role("option", name=...)`.
- User menu: use `page.locator(".oxd-userdropdown-tab")` — display name is dynamic and must NOT be used in locators.
- Sub-navigation: always click the parent menu item before clicking child items.
- Date pickers: click `input.oxd-date-input` first to open the calendar, then select the date.

### SauceDemo (React)
- Page title "Products" is a `<span class="title">`, not a heading element.
- Cart icon: use `.shopping_cart_link` or `[data-test='shopping-cart-link']`.
- Product items: use `[data-test='item-{id}-title-link']` for unique selection.
- Sort dropdown: use `[data-test='product-sort-container']`.

### DemoQA
- Frames: many elements are inside `<iframe>` — use `page.frame_locator(...)` first.
- Date pickers: use `page.locator("input#dateOfBirth")` and `.fill()` with keyboard submission.
- Upload: use `page.locator("#uploadFile").set_input_files(path)`.

---

## Visibility-First Rules

**Always target visible elements.** Before using a locator, consider:

1. Is the element visible in the current DOM state? Use `.filter(has_text=...)` to exclude hidden duplicates.
2. Is there a hidden sibling with the same selector? Scope to the nearest visible parent (`header`, `main`, `[role="dialog"]`).
3. Does the element require a trigger action first? (dropdown open, accordion expand, menu click)

```python
# Scope to visible parent — prevents matching hidden duplicates
page.locator("main input[type='search']").fill("query")
page.locator("header").get_by_role("button", name="Search").click()

# Filter out invisible elements
page.locator("form").filter(has=page.get_by_role("heading", name="Contact")).fill(...)
```

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
