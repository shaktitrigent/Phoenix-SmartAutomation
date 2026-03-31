# Playwright CRUD Operations Test Pattern — Knowledge Base

> This file defines the standard patterns for testing Create, Read, Update, and Delete operations in Playwright. All examples follow the project's locator, assertion, waiting, and security rules. See companion files for those conventions.

---

## Golden Rule

**Each CRUD test must be self-contained.** A test creates its own data, verifies it, and cleans up after itself. Never depend on data created by another test or pre-existing in the environment.

---

## 1. Create Operation

### Pattern

```python
import re
import os
from playwright.sync_api import expect

def test_create_item(page, base_url):
    """Create a new item and verify it appears in the list."""
    # Arrange — navigate to the creation form
    page.goto(f"{base_url}/items")
    page.get_by_role("button", name="New Item").click()
    expect(page.get_by_role("heading", name="Create Item")).to_be_visible()

    # Act — fill required fields
    page.get_by_label("Name").fill("Test Item")
    page.get_by_label("Description").fill("Automated test description")
    page.get_by_label("Category").select_option(label="Electronics")
    page.get_by_label("Price").fill("29.99")

    # Act — fill optional fields (if testing full coverage)
    page.get_by_label("Tags").fill("test, automation")

    # Act — submit
    page.get_by_role("button", name="Save").click()

    # Assert — success feedback
    expect(page.get_by_role("alert")).to_contain_text("created successfully")

    # Assert — redirected to list or detail view
    expect(page).to_have_url(re.compile(r".*/items"))

    # Assert — new item appears in the list
    expect(page.get_by_role("row").filter(has_text="Test Item")).to_be_visible()
```

### Variations

#### Create with File Upload

```python
import tempfile, os

def test_create_item_with_attachment(page, base_url):
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as tmp:
        tmp.write("Test attachment content")
        tmp_path = tmp.name

    try:
        page.goto(f"{base_url}/items/new")
        page.get_by_label("Name").fill("Item with Attachment")
        page.get_by_label("Attachment").set_input_files(tmp_path)
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_role("alert")).to_contain_text("created successfully")
        expect(page.get_by_text(os.path.basename(tmp_path))).to_be_visible()
    finally:
        os.unlink(tmp_path)
```

#### Create with Validation Errors

```python
def test_create_item_validation(page, base_url):
    """Submit empty form and verify validation messages."""
    page.goto(f"{base_url}/items/new")

    # Submit without filling required fields
    page.get_by_role("button", name="Save").click()

    # Assert — validation errors appear (do NOT assert success is absent)
    expect(page.get_by_text("Name is required")).to_be_visible()
    expect(page.get_by_text("Category is required")).to_be_visible()

    # Assert — still on the create page
    expect(page).to_have_url(re.compile(r".*/items/new"))
```

#### Create with Duplicate Detection

```python
def test_create_duplicate_item(page, base_url):
    """Attempt to create a duplicate and verify the error."""
    page.goto(f"{base_url}/items/new")
    page.get_by_label("Name").fill("Existing Item Name")
    page.get_by_role("button", name="Save").click()

    expect(page.get_by_role("alert")).to_contain_text("already exists")
```

---

## 2. Read Operation

### Pattern — List View

```python
def test_read_items_list(page, base_url):
    """Verify the items list displays data correctly."""
    page.goto(f"{base_url}/items")

    # Assert — page loaded with expected structure
    expect(page.get_by_role("heading", name="Items")).to_be_visible()
    expect(page.get_by_role("table")).to_be_visible()

    # Assert — data rows are present (at least one)
    expect(page.get_by_role("row")).to_have_count(
        # header row + at least 1 data row
        count  # replace with expected count or use > 1 logic below
    )
```

### Variations

#### Pagination

```python
def test_read_items_pagination(page, base_url):
    """Verify pagination controls and page navigation."""
    page.goto(f"{base_url}/items")

    # Assert — first page loaded
    expect(page.get_by_role("button", name="Previous")).to_be_disabled()
    expect(page.get_by_role("button", name="Next")).to_be_enabled()

    # Act — navigate to next page
    page.get_by_role("button", name="Next").click()

    # Assert — URL updated and content changed
    expect(page).to_have_url(re.compile(r".*page=2"))
    expect(page.get_by_role("button", name="Previous")).to_be_enabled()
```

#### Search / Filter

```python
def test_read_items_search(page, base_url):
    """Verify search filters the list correctly."""
    page.goto(f"{base_url}/items")

    # Act — search
    page.get_by_role("searchbox", name="Search").fill("Test Item")
    page.get_by_role("searchbox", name="Search").press("Enter")

    # Assert — results filtered
    expect(page.get_by_role("row").filter(has_text="Test Item")).to_be_visible()

    # Assert — non-matching items are not shown
    expect(page.get_by_role("row").filter(has_text="Unrelated Item")).to_be_hidden()
```

#### Filter by Category / Status

```python
def test_read_items_filter_by_status(page, base_url):
    """Verify status filter narrows results."""
    page.goto(f"{base_url}/items")

    page.get_by_label("Status").select_option(label="Active")

    # Assert — all visible rows show Active status
    rows = page.get_by_role("row").filter(has_text="Active")
    expect(rows.first).to_be_visible()

    # Assert — no Archived items visible
    expect(page.get_by_role("row").filter(has_text="Archived")).to_have_count(0)
```

#### Sort

```python
def test_read_items_sort(page, base_url):
    """Verify column sorting works."""
    page.goto(f"{base_url}/items")

    # Act — click column header to sort
    page.get_by_role("columnheader", name="Name").click()

    # Assert — first item alphabetically
    first_row = page.get_by_role("row").nth(1)   # nth(0) is header
    expect(first_row).to_contain_text("Alpha Item")
```

#### Detail View

```python
def test_read_item_detail(page, base_url):
    """Click an item and verify its detail page."""
    page.goto(f"{base_url}/items")

    page.get_by_role("row").filter(has_text="Test Item").get_by_role("link", name="View").click()

    # Assert — detail page
    expect(page.get_by_role("heading", name="Test Item")).to_be_visible()
    expect(page.get_by_text("Automated test description")).to_be_visible()
    expect(page.get_by_text("Electronics")).to_be_visible()
    expect(page.get_by_text("29.99")).to_be_visible()
```

---

## 3. Update Operation

### Pattern

```python
def test_update_item(page, base_url):
    """Edit an existing item and verify changes are saved."""
    # Navigate to the item's edit form
    page.goto(f"{base_url}/items")
    page.get_by_role("row").filter(has_text="Test Item").get_by_role("button", name="Edit").click()

    # Assert — edit form loaded with existing data
    expect(page.get_by_label("Name")).to_have_value("Test Item")

    # Act — modify fields
    page.get_by_label("Name").clear()
    page.get_by_label("Name").fill("Updated Item Name")
    page.get_by_label("Description").clear()
    page.get_by_label("Description").fill("Updated description text")

    # Act — submit
    page.get_by_role("button", name="Save").click()

    # Assert — success feedback
    expect(page.get_by_role("alert")).to_contain_text("updated successfully")

    # Assert — changes reflected in list
    expect(page.get_by_role("row").filter(has_text="Updated Item Name")).to_be_visible()
    expect(page.get_by_role("row").filter(has_text="Test Item")).to_have_count(0)
```

### Variations

#### Inline / In-Place Editing

```python
def test_update_item_inline(page, base_url):
    """Edit a field inline (e.g., click-to-edit table cell)."""
    page.goto(f"{base_url}/items")

    row = page.get_by_role("row").filter(has_text="Test Item")

    # Act — double-click to enter edit mode
    row.get_by_role("cell", name="Test Item").dblclick()

    # Act — clear and type new value
    inline_input = row.get_by_role("textbox")
    inline_input.clear()
    inline_input.fill("Inline Updated Name")
    inline_input.press("Enter")

    # Assert — value saved
    expect(row).to_contain_text("Inline Updated Name")
```

#### Update with Validation Errors

```python
def test_update_item_validation(page, base_url):
    """Clear a required field and verify validation prevents save."""
    page.goto(f"{base_url}/items")
    page.get_by_role("row").filter(has_text="Test Item").get_by_role("button", name="Edit").click()

    # Clear required field
    page.get_by_label("Name").clear()
    page.get_by_role("button", name="Save").click()

    # Assert — validation error, still on edit page
    expect(page.get_by_text("Name is required")).to_be_visible()
    expect(page).to_have_url(re.compile(r".*/edit"))
```

#### Cancel Edit (No Changes Saved)

```python
def test_update_item_cancel(page, base_url):
    """Cancel an edit and verify no changes are saved."""
    page.goto(f"{base_url}/items")
    page.get_by_role("row").filter(has_text="Test Item").get_by_role("button", name="Edit").click()

    # Modify but don't submit
    page.get_by_label("Name").clear()
    page.get_by_label("Name").fill("Should Not Be Saved")

    # Cancel
    page.get_by_role("button", name="Cancel").click()

    # Assert — original name still shown
    expect(page.get_by_role("row").filter(has_text="Test Item")).to_be_visible()
    expect(page.get_by_role("row").filter(has_text="Should Not Be Saved")).to_have_count(0)
```

---

## 4. Delete Operation

### Pattern

```python
def test_delete_item(page, base_url):
    """Delete an item and verify it's removed from the list."""
    page.goto(f"{base_url}/items")

    # Verify item exists first
    row = page.get_by_role("row").filter(has_text="Test Item")
    expect(row).to_be_visible()

    # Act — click delete
    row.get_by_role("button", name="Delete").click()

    # Act — confirm in dialog
    dialog = page.get_by_role("dialog", name="Confirm deletion")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Confirm").click()

    # Assert — success feedback
    expect(page.get_by_role("alert")).to_contain_text("deleted successfully")

    # Assert — item removed from list
    expect(page.get_by_role("row").filter(has_text="Test Item")).to_have_count(0)
```

### Variations

#### Delete with Browser Dialog (alert/confirm)

```python
def test_delete_item_browser_confirm(page, base_url):
    """Delete with native browser confirm dialog."""
    page.goto(f"{base_url}/items")

    # Register dialog handler BEFORE the click
    page.once("dialog", lambda d: d.accept())

    page.get_by_role("row").filter(has_text="Test Item").get_by_role("button", name="Delete").click()

    # Assert — item removed
    expect(page.get_by_role("row").filter(has_text="Test Item")).to_have_count(0)
```

#### Cancel Delete

```python
def test_delete_item_cancel(page, base_url):
    """Cancel deletion and verify item is preserved."""
    page.goto(f"{base_url}/items")

    row = page.get_by_role("row").filter(has_text="Test Item")
    row.get_by_role("button", name="Delete").click()

    # Dismiss confirmation
    dialog = page.get_by_role("dialog", name="Confirm deletion")
    dialog.get_by_role("button", name="Cancel").click()

    # Assert — item still exists
    expect(row).to_be_visible()
```

#### Bulk Delete

```python
def test_bulk_delete_items(page, base_url):
    """Select multiple items and delete them."""
    page.goto(f"{base_url}/items")

    # Select items via checkboxes
    page.get_by_role("row").filter(has_text="Item A").get_by_role("checkbox").check()
    page.get_by_role("row").filter(has_text="Item B").get_by_role("checkbox").check()

    # Act — bulk delete
    page.get_by_role("button", name="Delete Selected").click()

    # Confirm
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("2 items")
    dialog.get_by_role("button", name="Confirm").click()

    # Assert — both removed
    expect(page.get_by_role("alert")).to_contain_text("2 items deleted")
    expect(page.get_by_role("row").filter(has_text="Item A")).to_have_count(0)
    expect(page.get_by_role("row").filter(has_text="Item B")).to_have_count(0)
```

---

## 5. Full CRUD Lifecycle Test

A single test that exercises all four operations in sequence. Useful as a smoke test or integration check.

```python
def test_full_crud_lifecycle(page, base_url):
    """Complete lifecycle: create → read → update → delete."""
    item_name = f"CRUD Test {uuid.uuid4().hex[:6]}"
    updated_name = f"{item_name} Updated"

    # ── CREATE ──
    page.goto(f"{base_url}/items/new")
    page.get_by_label("Name").fill(item_name)
    page.get_by_label("Description").fill("Lifecycle test item")
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("alert")).to_contain_text("created successfully")

    # ── READ ──
    page.goto(f"{base_url}/items")
    row = page.get_by_role("row").filter(has_text=item_name)
    expect(row).to_be_visible()

    # ── UPDATE ──
    row.get_by_role("button", name="Edit").click()
    page.get_by_label("Name").clear()
    page.get_by_label("Name").fill(updated_name)
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("alert")).to_contain_text("updated successfully")

    # Verify update in list
    page.goto(f"{base_url}/items")
    expect(page.get_by_role("row").filter(has_text=updated_name)).to_be_visible()
    expect(page.get_by_role("row").filter(has_text=item_name)).to_have_count(0)

    # ── DELETE ──
    page.get_by_role("row").filter(has_text=updated_name).get_by_role("button", name="Delete").click()
    page.get_by_role("dialog").get_by_role("button", name="Confirm").click()
    expect(page.get_by_role("alert")).to_contain_text("deleted successfully")
    expect(page.get_by_role("row").filter(has_text=updated_name)).to_have_count(0)
```

> Use `uuid` to generate unique names per run. This prevents collisions in shared test environments and makes cleanup identification easy.

---

## 6. Data Cleanup Patterns

### Fixture-Based Cleanup (Preferred)

```python
import pytest, uuid

@pytest.fixture
def create_test_item(page, base_url):
    """Create a test item and clean it up after the test."""
    item_name = f"Fixture Item {uuid.uuid4().hex[:6]}"

    page.goto(f"{base_url}/items/new")
    page.get_by_label("Name").fill(item_name)
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("alert")).to_contain_text("created")

    yield item_name

    # Teardown — delete the item
    page.goto(f"{base_url}/items")
    row = page.get_by_role("row").filter(has_text=item_name)
    if row.count() > 0:
        row.get_by_role("button", name="Delete").click()
        page.get_by_role("dialog").get_by_role("button", name="Confirm").click()


def test_update_item(page, base_url, create_test_item):
    """Test only the update — fixture handles create and cleanup."""
    page.goto(f"{base_url}/items")
    page.get_by_role("row").filter(has_text=create_test_item).get_by_role("button", name="Edit").click()
    page.get_by_label("Name").clear()
    page.get_by_label("Name").fill(f"{create_test_item} Edited")
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_role("alert")).to_contain_text("updated")
```

### API-Based Cleanup (Fastest)

```python
@pytest.fixture
def create_test_item_via_api(request, base_url):
    """Create via API for speed, clean up via API after test."""
    import requests

    item_name = f"API Item {uuid.uuid4().hex[:6]}"
    resp = requests.post(
        f"{base_url}/api/items",
        json={"name": item_name, "description": "API-created test item"},
        headers={"Authorization": f"Bearer {os.environ['TEST_API_TOKEN']}"},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    yield {"id": item_id, "name": item_name}

    # Teardown — API delete
    requests.delete(
        f"{base_url}/api/items/{item_id}",
        headers={"Authorization": f"Bearer {os.environ['TEST_API_TOKEN']}"},
    )
```

---

## Anti-Patterns — Do NOT Generate These

| Anti-Pattern                                           | Why                                           | Correct Alternative                                    |
|--------------------------------------------------------|-----------------------------------------------|--------------------------------------------------------|
| `page.fill("#name", "Test")`                           | Raw CSS ID selector — fragile                 | `page.get_by_label("Name").fill("Test")`               |
| `page.click("button[type='submit']")`                  | Generic CSS — may match multiple buttons      | `page.get_by_role("button", name="Save").click()`      |
| `page.wait_for_selector(".success-message")`           | Manual wait — no auto-retry                   | `expect(page.get_by_role("alert")).to_contain_text(…)`  |
| `assert "created" in page.locator(…).text_content()`   | Raw assert — no auto-wait                     | `expect(locator).to_contain_text("created")`           |
| `time.sleep(2)` between CRUD steps                     | Arbitrary delay — flaky                       | `expect()` assertions between steps                    |
| Tests depending on data from other tests                | Order-dependent, fragile                      | Each test creates its own data                         |
| Hardcoded item names without unique suffixes            | Collisions in shared/parallel environments    | `f"Test Item {uuid.uuid4().hex[:6]}"`                  |
| No cleanup after create/update                          | Pollutes environment, breaks other tests      | Fixture with teardown or API cleanup                   |
| `page.locator(".success-message")`                      | CSS class selector — fragile                  | `page.get_by_role("alert")` or `get_by_text(…)`       |

---

## Rules for AI Code Generation

When generating CRUD test scripts, follow these rules strictly:

1. **Use `get_by_role`, `get_by_label`, and `get_by_text`** for all element interactions. Never use raw CSS selectors like `#name`, `.btn`, or `button[type='submit']`.
2. **Use `expect()` for all assertions.** Never use raw `assert` with `text_content()`, `is_visible()`, or `page.url`.
3. **Never generate `time.sleep()`, `wait_for_selector()`, or `wait_for_timeout()` without a documented reason.**
4. **Generate unique test data per run** using `uuid.uuid4().hex[:6]` or `datetime` suffixes. Never use static names like `"Test Item"` without a unique qualifier.
5. **Always clean up created data** — either in a fixture teardown (`yield` + cleanup) or within the test itself. Never leave orphaned test data.
6. **Use `base_url` from fixture or environment.** Never hardcode URLs.
7. **Use `os.environ` for credentials.** Never hardcode passwords or API tokens.
8. **Assert outcomes, not intermediate state.** After submit, assert the success message or URL change — don't re-read every form field.
9. **Scope row actions with `.filter(has_text=…)`** — never use `.nth()` to target specific table rows by position.
10. **Register dialog handlers before the triggering click** — use `page.once("dialog", lambda d: d.accept())` for browser confirm dialogs.
11. **Use `page.get_by_role("dialog", name=…)` for modal confirmations** — scope all button clicks inside the dialog to avoid strict mode violations.
12. **For CRUD lifecycle tests**, follow the sequence: create → read → update → delete, with assertions after each step.