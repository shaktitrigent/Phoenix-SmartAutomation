"""Base page locators and common actions shared across all pages."""

PAGE_MAPPING = {
    "page": "global",
    "locators": {
        "page_heading": {
            "element_name": "page_heading",
            "strategy": "role",
            "value": "heading",
            "confidence": 0.90,
        },
        "breadcrumb": {
            "element_name": "breadcrumb",
            "strategy": "css",
            "value": ".breadcrumb, nav[aria-label='breadcrumb']",
            "confidence": 0.80,
        },
        "success_toast": {
            "element_name": "success_toast",
            "strategy": "css",
            "value": ".success, .alert-success, [class*='success']",
            "confidence": 0.80,
        },
        "error_message": {
            "element_name": "error_message",
            "strategy": "css",
            "value": ".alert-danger, .error-message, [class*='error']",
            "confidence": 0.80,
        },
        "save_button": {
            "element_name": "save_button",
            "strategy": "role",
            "value": "button[name='Save']",
            "confidence": 0.85,
        },
        "cancel_button": {
            "element_name": "cancel_button",
            "strategy": "role",
            "value": "button[name='Cancel']",
            "confidence": 0.85,
        },
        "submit_button": {
            "element_name": "submit_button",
            "strategy": "role",
            "value": "button[type='submit']",
            "confidence": 0.85,
        },
    },
    "expected_url_pattern": None,
}
