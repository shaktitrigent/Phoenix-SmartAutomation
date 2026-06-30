# UI Patterns

Document non-standard UI components and interaction patterns here.

## Custom Dropdowns

Example:
- Module: All dropdowns in this app use a custom Vue.js component, not native `<select>`
- Interaction: Click the field → wait for `role="listbox"` → click `role="option"`
- Locator hint: Use `get_by_role("combobox")` for the trigger

YOUR NOTES:
[Add your observations here]

## Date Pickers

Example:
- Library: Our app uses flatpickr.js
- Interaction: Click input → calendar appears → click date cell
- Locator hint: Calendar has class `flatpickr-calendar`

YOUR NOTES:
[Add your observations here]

## Modals / Dialogs

Example:
- Trigger: Some buttons open a confirmation modal before proceeding
- Locator hint: `[role='dialog']` or `[aria-modal='true']`
- Close: Click the X button or press Escape

YOUR NOTES:
[Add your observations here]

## File Uploads

YOUR NOTES:
[Add your observations here]
