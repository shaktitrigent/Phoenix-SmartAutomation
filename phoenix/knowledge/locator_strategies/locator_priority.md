---
title: Locator Priority Strategy
category: locators
tags: [locators, selectors, stability, best-practices]
---

# Locator Priority Strategy

## Description
Best practices for selecting stable and maintainable locators in Playwright tests. Priority order ensures maximum stability and minimal maintenance.

## Priority Order

### 1. data-testid (Highest Priority)
**When to use:** When elements have dedicated test IDs.

**Example:**
```python
page.locator("[data-testid='login-button']")
```

**Advantages:**
- Most stable
- Purpose-built for testing
- Not affected by UI changes
- Clear intent

**Disadvantages:**
- Requires developer cooperation
- May not exist in legacy code

### 2. Role-based Locators
**When to use:** For semantic HTML elements with ARIA roles.

**Example:**
```python
page.get_by_role("button", name="Login")
page.get_by_role("textbox", name="Email")
```

**Advantages:**
- Semantic and accessible
- Stable across UI changes
- Aligns with accessibility best practices

**Disadvantages:**
- Requires proper ARIA implementation
- May be less specific

### 3. Text Content
**When to use:** For elements with unique, visible text.

**Example:**
```python
page.get_by_text("Login")
page.get_by_label("Email Address")
```

**Advantages:**
- Easy to understand
- Works with visible text
- Good for user-facing elements

**Disadvantages:**
- Breaks if text changes
- May match multiple elements
- Language-dependent

### 4. CSS Selectors
**When to use:** When other strategies don't work, use stable CSS attributes.

**Example:**
```python
page.locator("button.primary-button")
page.locator("form#login-form input[type='email']")
```

**Advantages:**
- Flexible
- Can target specific attributes
- Works with class names

**Disadvantages:**
- Can break with CSS changes
- Less semantic
- Can be brittle

### 5. XPath (Lowest Priority)
**When to use:** Only when no other option works.

**Example:**
```python
page.locator("xpath=//button[contains(@class, 'login')]")
```

**Advantages:**
- Very flexible
- Can navigate DOM structure

**Disadvantages:**
- Most brittle
- Hard to maintain
- Performance concerns
- Breaks easily with DOM changes

## Anti-Patterns to Avoid

1. **Position-based selectors:** `:nth-child(3)`, `:first-child`
2. **Hardcoded IDs:** IDs that change frequently
3. **Complex CSS chains:** Deeply nested selectors
4. **XPath with text:** `//div[text()='Login']` (use get_by_text instead)

## Stability Guidelines

- **Stable:** data-testid, role-based, semantic attributes
- **Moderate:** Text content, stable CSS classes
- **Unstable:** XPath, position-based, dynamic IDs

## Best Practices

1. Always prefer data-testid when available
2. Use role-based locators for interactive elements
3. Combine strategies when needed (e.g., role + name)
4. Document why a specific locator strategy was chosen
5. Review and update locators regularly
6. Avoid locators that depend on visual styling
