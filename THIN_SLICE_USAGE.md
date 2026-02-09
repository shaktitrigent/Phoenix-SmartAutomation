# Phoenix Thin-Slice Usage Guide

## Simple Workflow

### 1. Initialize Project

```bash
phoenix init --project-name my-project
```

### 2. Generate Tests (User Story + URL)

```bash
phoenix generate \
  --story "As a user, I want to login" \
  --url "https://your-app.com/login" \
  --criteria "User can enter email and password" \
  --criteria "User can click login button" \
  --criteria "User is redirected after login"
```

**Output:**
- Manual test cases saved to `./manual_tests/` (markdown files)
- Automation scripts saved to `./test_results/` (pytest Playwright scripts)

### 3. Run Automation Tests

```bash
pytest -v test_results/
```

## What Gets Generated

### Manual Tests (`./manual_tests/`)
- Markdown files with test steps
- Includes application URL
- Structured test cases ready for QA review

### Automation Scripts (`./test_results/`)
- Runnable pytest + Playwright Python scripts
- Includes `page.goto()` with your URL
- Basic Playwright code based on acceptance criteria
- Ready to run with `pytest`

## Example Generated Script

```python
def test_login(page: Page):
    """As a user, I want to login"""
    # Navigate to application
    page.goto("https://your-app.com/login")
    page.wait_for_load_state('networkidle')
    
    # Step 1: User can enter email and password
    page.get_by_label("Email").fill("test@example.com")
    page.get_by_label("Password").fill("password123")
    
    # Step 2: User can click login button
    page.get_by_role("button", name="Login").click()
    
    # Assertions
    expect(page).to_have_url(containing="dashboard")
```

## Python SDK Usage

```python
from phoenix import PhoenixClient

client = PhoenixClient()
client.set_project("my-project")

result = client.generate_tests(
    user_story="As a user, I want to login",
    application_url="https://your-app.com/login",
    acceptance_criteria=[
        "User can enter credentials",
        "User can click login"
    ]
)

# Manual tests saved to ./manual_tests/
# Automation scripts saved to ./test_results/
```

## Next Steps

1. Review generated manual tests in `./manual_tests/`
2. Review and enhance automation scripts in `./test_results/`
3. Run tests: `pytest -v test_results/`
4. View reports in `./reports/` after execution
