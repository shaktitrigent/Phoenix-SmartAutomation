"""Login page locators and known actions."""

PAGE_MAPPING = {
    "page": "login",
    "locators": {
        "username_field": {
            "element_name": "username_field",
            "strategy": "label",
            "value": "Username",
            "confidence": 0.95,
        },
        "password_field": {
            "element_name": "password_field",
            "strategy": "label",
            "value": "Password",
            "confidence": 0.95,
        },
        "login_button": {
            "element_name": "login_button",
            "strategy": "role",
            "value": "button",
            "role_name": "Login",
            "confidence": 0.95,
        },
        "forgot_password_link": {
            "element_name": "forgot_password_link",
            "strategy": "text",
            "value": "Forgot your password?",
            "confidence": 0.85,
        },
    },
    "common_actions": {
        "login": (
            'await page.get_by_label("Username").fill(test_data["username"])\n'
            'await page.get_by_label("Password").fill(test_data["password"])\n'
            'await page.get_by_role("button", name="Login").click()'
        ),
    },
    "expected_url_pattern": r".*/auth/login.*",
}
