"""Employee management page locators and known actions."""

PAGE_MAPPING = {
    "page": "employee",
    "locators": {
        "add_employee_button": {
            "element_name": "add_employee_button",
            "strategy": "role",
            "value": "button",
            "role_name": "Add",
            "confidence": 0.90,
        },
        "first_name_field": {
            "element_name": "first_name_field",
            "strategy": "placeholder",
            "value": "First Name",
            "confidence": 0.90,
        },
        "middle_name_field": {
            "element_name": "middle_name_field",
            "strategy": "placeholder",
            "value": "Middle Name",
            "confidence": 0.85,
        },
        "last_name_field": {
            "element_name": "last_name_field",
            "strategy": "placeholder",
            "value": "Last Name",
            "confidence": 0.90,
        },
        "employee_id_field": {
            "element_name": "employee_id_field",
            "strategy": "label",
            "value": "Employee Id",
            "confidence": 0.85,
        },
        "create_login_toggle": {
            "element_name": "create_login_toggle",
            "strategy": "css",
            "value": "label.oxd-switch-input",
            "confidence": 0.80,
        },
        "username_field": {
            "element_name": "username_field",
            "strategy": "label",
            "value": "Username",
            "confidence": 0.90,
        },
        "password_field": {
            "element_name": "password_field",
            "strategy": "css",
            "value": "input[type='password']:first-of-type",
            "confidence": 0.80,
        },
        "confirm_password_field": {
            "element_name": "confirm_password_field",
            "strategy": "css",
            "value": "input[type='password']:last-of-type",
            "confidence": 0.80,
        },
        "save_button": {
            "element_name": "save_button",
            "strategy": "role",
            "value": "button",
            "role_name": "Save",
            "confidence": 0.90,
        },
        "search_field": {
            "element_name": "search_field",
            "strategy": "placeholder",
            "value": "Type for hints...",
            "confidence": 0.85,
        },
    },
    "common_actions": {
        "navigate": 'await page.goto(config.BASE_URL + "/viewEmployeeList")',
        "add_employee": 'await page.get_by_role("button", name="Add").click()',
    },
    "expected_url_pattern": r".*/viewEmployeeList.*",
}
