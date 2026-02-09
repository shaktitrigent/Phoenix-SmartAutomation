---
title: CRUD Operations Test Pattern
category: data-management
tags: [crud, create, read, update, delete, data]
---

# CRUD Operations Test Pattern

## Description
Comprehensive test pattern for Create, Read, Update, Delete operations. Essential for testing data management functionality.

## Use Cases
- Form submissions
- Data listing/display
- Data editing
- Data deletion
- Data validation

## Test Scenarios

### 1. Create Operation
**Steps:**
1. Navigate to create page/form
2. Fill in required fields
3. Fill in optional fields
4. Submit form
5. Verify success message
6. Verify data appears in list/view

**Expected Result:** New record is created and displayed.

### 2. Read Operation
**Steps:**
1. Navigate to list/view page
2. Verify data is displayed correctly
3. Verify pagination (if applicable)
4. Verify filtering/search (if applicable)
5. Click on item to view details

**Expected Result:** Data is displayed correctly with all expected information.

### 3. Update Operation
**Steps:**
1. Navigate to edit page/form
2. Modify fields
3. Submit form
4. Verify success message
5. Verify changes are reflected

**Expected Result:** Record is updated successfully.

### 4. Delete Operation
**Steps:**
1. Navigate to list/view page
2. Click delete button/action
3. Confirm deletion
4. Verify success message
5. Verify record is removed from list

**Expected Result:** Record is deleted successfully.

## Automation Example

```python
def test_create_item(page):
    page.goto("/items/create")
    page.fill("#name", "Test Item")
    page.fill("#description", "Test Description")
    page.click("button[type='submit']")
    page.wait_for_selector(".success-message")
    assert "created successfully" in page.locator(".success-message").text_content()
```

## When to Use
- Data management features
- Admin panels
- Content management systems
- API testing

## Risk Level
**Regression** - Important functionality that should be tested regularly.
