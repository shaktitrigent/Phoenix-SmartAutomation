# Phoenix Framework - Test Automation Practice Sample Tests

This document demonstrates how Phoenix generates tests for the [Test Automation Practice website](https://testautomationpractice.blogspot.com/).

## Setup

1. **Activate virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Initialize project:**
   ```bash
   phoenix init --project-name test-automation-practice
   ```

## User Stories Tested

### User Story 1: Form Submission

**Story:** As a user, I want to fill in the form with my personal details and submit it, so that the system accepts and processes my registration correctly.

**Acceptance Criteria:**
- User can enter name, email, phone and address
- User can select gender and multiple days
- User can choose a country from the dropdown
- The form must submit successfully without errors

**Generated Manual Test:**
```
Application URL: https://testautomationpractice.blogspot.com/

Test Case: Manual Test: As a user, I want to fill in the form with my pers...

Description: As a user, I want to fill in the form with my personal details and submit it, so that the system accepts and processes my registration correctly

Steps:
  1. Navigate to https://testautomationpractice.blogspot.com/
  2. Step 1: User can enter name, email, phone and address
  3. Step 2: User can select gender and multiple days
  4. Step 3: User can choose a country from the dropdown
  5. Step 4: The form must submit successfully without errors

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION
```

**CLI Command:**
```bash
phoenix generate \
  --story "As a user, I want to fill in the form with my personal details and submit it, so that the system accepts and processes my registration correctly" \
  --url "https://testautomationpractice.blogspot.com/" \
  --criteria "User can enter name, email, phone and address" \
  --criteria "User can select gender and multiple days" \
  --criteria "User can choose a country from the dropdown" \
  --criteria "The form must submit successfully without errors"
```

---

### User Story 2: Table Data Validation

**Story:** As a tester, I want to verify the static web table data for books (Book Name, Author, Subject, Price), so that I can ensure the table displays correct information and sorting behaves as expected.

**Acceptance Criteria:**
- Book table loads with expected column headers
- All rows display accurate book details
- Sorting or filtering functions work if provided

**Generated Manual Test:**
```
Application URL: https://testautomationpractice.blogspot.com/

Test Case: Manual Test: As a tester, I want to verify the static web table...

Description: As a tester, I want to verify the static web table data for books (Book Name, Author, Subject, Price), so that I can ensure the table displays correct information and sorting behaves as expected

Steps:
  1. Navigate to https://testautomationpractice.blogspot.com/
  2. Step 1: Book table loads with expected column headers
  3. Step 2: All rows display accurate book details
  4. Step 3: Sorting or filtering functions work if provided

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION
```

**CLI Command:**
```bash
phoenix generate \
  --story "As a tester, I want to verify the static web table data for books (Book Name, Author, Subject, Price), so that I can ensure the table displays correct information and sorting behaves as expected" \
  --url "https://testautomationpractice.blogspot.com/" \
  --criteria "Book table loads with expected column headers" \
  --criteria "All rows display accurate book details" \
  --criteria "Sorting or filtering functions work if provided"
```

---

### User Story 3: Alert Handling

**Story:** As a user, I want to interact with alerts and popup messages, so that the application displays and handles alert boxes appropriately (accept, cancel, input text).

**Acceptance Criteria:**
- Simple alerts appear when triggered
- Confirmation alerts can be accepted or dismissed
- Prompt alerts allow input and reflect that input correctly

**Generated Manual Test:**
```
Application URL: https://testautomationpractice.blogspot.com/

Test Case: Manual Test: As a user, I want to interact with alerts and popu...

Description: As a user, I want to interact with alerts and popup messages, so that the application displays and handles alert boxes appropriately (accept, cancel, input text)

Steps:
  1. Navigate to https://testautomationpractice.blogspot.com/
  2. Step 1: Simple alerts appear when triggered
  3. Step 2: Confirmation alerts can be accepted or dismissed
  4. Step 3: Prompt alerts allow input and reflect that input correctly

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION
```

**CLI Command:**
```bash
phoenix generate \
  --story "As a user, I want to interact with alerts and popup messages, so that the application displays and handles alert boxes appropriately (accept, cancel, input text)" \
  --url "https://testautomationpractice.blogspot.com/" \
  --criteria "Simple alerts appear when triggered" \
  --criteria "Confirmation alerts can be accepted or dismissed" \
  --criteria "Prompt alerts allow input and reflect that input correctly"
```

---

## Generated Files

### Manual Tests
All manual tests are saved in `./manual_tests/` directory as markdown files:
- `manual_test_001_manual_test_as_a_user_i_want_to_fill_in_the_form_with_my_pers.md`
- `manual_test_001_manual_test_as_a_tester_i_want_to_verify_the_static_web_table.md`
- `manual_test_001_manual_test_as_a_user_i_want_to_interact_with_alerts_and_popu.md`

### Automation Scripts
Automation scripts (when generated) will be saved in `./test_results/` directory as Python pytest + Playwright scripts.

## Next Steps

1. **Review Manual Tests:** Check the generated manual test cases in `./manual_tests/`
2. **Generate Automation Scripts:** The framework will generate automation scripts when the MCP integration is fully configured
3. **Run Tests:** Execute automation tests using `pytest -v test_results/`
4. **View Reports:** After execution, view HTML reports in `./reports/`

## Notes

- The framework currently generates manual tests successfully
- Automation test generation requires full MCP integration (currently in development)
- All tests are stored in the database and can be retrieved programmatically
- Tests are organized by project for easy management

## MCP Configuration Required

To generate automation scripts, you need to configure Playwright MCP integration. See **[MCP Configuration Guide](../docs/MCP_CONFIGURATION.md)** for detailed instructions.

**Quick Summary:**
1. **Option A (HTTP):** Set `PHOENIX_MCP_SERVER_URL` to your MCP server URL
2. **Option B (Stdio):** Set `PHOENIX_MCP_USE_STDIO=true` and configure MCP command
3. Implement MCP client methods in `phoenix/mcp/client.py`
4. Update `TestGeneratorAgent` to call MCP for automation test generation

Once configured, automation scripts will be generated automatically alongside manual tests.
