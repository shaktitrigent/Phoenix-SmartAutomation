"""Leave management page locators and known actions."""

PAGE_MAPPING = {
    "page": "leave",
    "locators": {
        "apply_leave_button": {
            "element_name": "apply_leave_button",
            "strategy": "role",
            "value": "button",
            "role_name": "Apply",
            "confidence": 0.90,
        },
        "leave_type_dropdown": {
            "element_name": "leave_type_dropdown",
            "strategy": "label",
            "value": "Leave Type",
            "confidence": 0.90,
        },
        "from_date_field": {
            "element_name": "from_date_field",
            "strategy": "placeholder",
            "value": "yyyy-dd-mm",
            "confidence": 0.80,
        },
        "to_date_field": {
            "element_name": "to_date_field",
            "strategy": "css",
            "value": ".oxd-date-input:last-of-type input",
            "confidence": 0.75,
        },
        "comment_field": {
            "element_name": "comment_field",
            "strategy": "label",
            "value": "Comments",
            "confidence": 0.85,
        },
        "submit_button": {
            "element_name": "submit_button",
            "strategy": "role",
            "value": "button",
            "role_name": "Apply",
            "confidence": 0.90,
        },
        "leave_list_table": {
            "element_name": "leave_list_table",
            "strategy": "css",
            "value": ".oxd-table",
            "confidence": 0.85,
        },
        "my_leave_menu": {
            "element_name": "my_leave_menu",
            "strategy": "text",
            "value": "My Leave",
            "confidence": 0.90,
        },
        "apply_leave_menu": {
            "element_name": "apply_leave_menu",
            "strategy": "text",
            "value": "Apply",
            "confidence": 0.85,
        },
    },
    "common_actions": {
        "navigate": 'await page.goto(config.BASE_URL + "/viewLeaveList")',
        "navigate_apply": 'await page.goto(config.BASE_URL + "/applyLeave")',
    },
    "expected_url_pattern": r".*/(?:viewLeaveList|applyLeave|leave).*",
}
