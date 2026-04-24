# Web Controls Hafsa Testing Strategy

## 1. Objective

Evaluate Phoenix Smart Automation in its current state for Web Controls testing by using the existing `phoenix generate`, `phoenix execute`, and `phoenix report` CLI flows without modifying code, prompts, or system behavior.

## 2. Scope of Scenarios

Covered scenarios:

| Scenario ID | Scenario Name | URL |
|---|---|---|
| WC-01 | Login Textbox + Password + Button | https://the-internet.herokuapp.com/login |
| WC-02 | Invalid Login Validation | https://the-internet.herokuapp.com/login |
| WC-04 | Dropdown Selection | https://the-internet.herokuapp.com/dropdown |
| WC-05 | Dynamic Loading | https://the-internet.herokuapp.com/dynamic_loading/1 |
| WC-07 | File Upload | https://the-internet.herokuapp.com/upload |
| WC-12 | Multiple Inputs | https://the-internet.herokuapp.com/inputs |
| WC-16 | OrangeHRM Login | https://opensource-demo.orangehrmlive.com/web/index.php/auth/login |
| WC-17 | OrangeHRM Add Candidate + Vacancy Autocomplete | https://opensource-demo.orangehrmlive.com/web/index.php/auth/login |
| WC-18 | OrangeHRM Search Filters | https://opensource-demo.orangehrmlive.com/web/index.php/auth/login |
| WC-19 | SauceDemo Login | https://www.saucedemo.com/ |
| WC-20 | SauceDemo Sort Dropdown | https://www.saucedemo.com/ |

## 3. Scenario Matrix

| Scenario ID | Control Focus | Manual Output Expected | Automation Output Expected | Execution Importance |
|---|---|---|---|---|
| WC-01 | Username, password, submit button | Clear valid login steps | Login flow with assertions | High |
| WC-02 | Validation message on failed login | Negative path coverage | Invalid credentials + flash validation | High |
| WC-04 | Select dropdown | Option selection steps | Stable select handling | Medium |
| WC-05 | Dynamic loading and wait behavior | Async behavior documented | Wait-aware script after Start click | High |
| WC-07 | File input upload | Upload steps and verification | `set_input_files` or equivalent | High |
| WC-12 | Numeric/text input behavior | Input interaction coverage | Input value change assertions | Medium |
| WC-16 | OrangeHRM login | Realistic login case | Login using demo credentials | High |
| WC-17 | OrangeHRM autocomplete | Candidate creation flow | Multi-step form + vacancy autocomplete | High |
| WC-18 | OrangeHRM filters | Search workflow | Filter selection and result validation | High |
| WC-19 | SauceDemo login | Valid login case | Login and inventory landing check | High |
| WC-20 | Sort dropdown | Sort selection steps | Sort choice + inventory reorder validation | High |

## 4. Exact CLI Command for Each Scenario

Run all commands from `Phoenix Smart Automation/my-project`.

| Scenario ID | Exact CLI Command |
|---|---|
| WC-01 | `phoenix --verbose generate --project hafsa-wc-01 --story "As a returning user, I want to log in with valid username and password using the Login button so I can access the secure area." --url "https://the-internet.herokuapp.com/login" --criteria "Enter username tomsmith" --criteria "Enter password SuperSecretPassword!" --criteria "Click the Login button" --criteria "Verify the Secure Area page is shown" --criteria "Verify success flash message is displayed" --type both --risk regression --clean` |
| WC-02 | `phoenix --verbose generate --project hafsa-wc-02 --story "As a returning user, I want an error message when I submit invalid login credentials so that failed authentication is clearly validated." --url "https://the-internet.herokuapp.com/login" --criteria "Enter username tomsmith" --criteria "Enter password invalidPassword" --criteria "Click the Login button" --criteria "Verify the login attempt is rejected" --criteria "Verify an error flash message is displayed" --type both --risk regression --clean` |
| WC-04 | `phoenix --verbose generate --project hafsa-wc-04 --story "As a user, I want to select an option from a dropdown so the selected value is applied correctly." --url "https://the-internet.herokuapp.com/dropdown" --criteria "Open the dropdown" --criteria "Select Option 2" --criteria "Verify Option 2 remains selected" --type both --risk regression --clean` |
| WC-05 | `phoenix --verbose generate --project hafsa-wc-05 --story "As a user, I want dynamically loaded content to appear after clicking Start so asynchronous loading is handled correctly." --url "https://the-internet.herokuapp.com/dynamic_loading/1" --criteria "Click the Start button" --criteria "Wait for Hello World to become visible" --criteria "Verify the loaded text is Hello World!" --criteria "Handle dynamic loading without fixed sleep" --type both --risk regression --clean` |
| WC-07 | `phoenix --verbose generate --project hafsa-wc-07 --story "As a user, I want to upload a file and confirm it was uploaded successfully." --url "https://the-internet.herokuapp.com/upload" --criteria "Choose a file from the local system" --criteria "Click the Upload button" --criteria "Verify the File Uploaded page or confirmation is shown" --criteria "Verify the uploaded file name is displayed" --type both --risk regression --clean` |
| WC-12 | `phoenix --verbose generate --project hafsa-wc-12 --story "As a user, I want to interact with the number input control and verify the entered value is handled correctly." --url "https://the-internet.herokuapp.com/inputs" --criteria "Click into the input control" --criteria "Enter the value 42" --criteria "Verify the input value is 42" --type both --risk regression --clean` |
| WC-16 | `phoenix --verbose generate --project hafsa-wc-16 --story "As an OrangeHRM user, I want to log in with valid credentials so I can access the dashboard." --url "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login" --criteria "Enter username Admin" --criteria "Enter password admin123" --criteria "Click the Login button" --criteria "Verify the OrangeHRM dashboard is displayed" --type both --risk regression --clean` |
| WC-17 | `phoenix --verbose generate --project hafsa-wc-17 --story "As a recruiter, I want to add a candidate and associate the candidate with a vacancy using autocomplete so recruitment data can be captured correctly." --url "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login" --criteria "Log in with username Admin and password admin123" --criteria "Navigate to Recruitment and open Candidates" --criteria "Click Add candidate" --criteria "Enter first name Hafsa, last name QA" --criteria "Use the Vacancy field autocomplete to search and select a vacancy" --criteria "Save the candidate" --criteria "Verify candidate creation succeeds" --type both --risk regression --clean` |
| WC-18 | `phoenix --verbose generate --project hafsa-wc-18 --story "As a recruiter, I want to use OrangeHRM candidate search filters so I can narrow the results list accurately." --url "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login" --criteria "Log in with username Admin and password admin123" --criteria "Navigate to Recruitment and open Candidates" --criteria "Use available search filters such as job title, vacancy, hiring manager, and status where applicable" --criteria "Click Search" --criteria "Verify filtered candidate results are displayed" --type both --risk regression --clean` |
| WC-19 | `phoenix --verbose generate --project hafsa-wc-19 --story "As a SauceDemo shopper, I want to log in with valid credentials so I can access the inventory page." --url "https://www.saucedemo.com/" --criteria "Enter username standard_user" --criteria "Enter password secret_sauce" --criteria "Click the Login button" --criteria "Verify the inventory page is displayed" --type both --risk regression --clean` |
| WC-20 | `phoenix --verbose generate --project hafsa-wc-20 --story "As a SauceDemo shopper, I want to change the product sort order using the sort dropdown so product ordering updates correctly." --url "https://www.saucedemo.com/" --criteria "Log in with username standard_user and password secret_sauce" --criteria "Open the product sort dropdown" --criteria "Select Name (Z to A)" --criteria "Verify the inventory list order changes accordingly" --type both --risk regression --clean` |

## 5. What to Validate in Output

For each scenario, validate:

| Area | Validation Points |
|---|---|
| Console output | Generation completed, counts are sensible, no hidden runtime error text |
| Manual tests | Scenario-specific title, steps, expected results, criteria reflected, realistic negative/positive flow |
| Automation tests | Uses correct URL, meaningful locators/actions/assertions, scenario-specific data, usable Playwright syntax |
| Test quality | Handles control type correctly, avoids generic filler, includes logical verification |
| Dynamic behavior | Wait strategy is appropriate for async or autocomplete scenarios |
| Execution | Script runs or fails with evidence that reveals current system limitations |
| Report | `reports/` receives an execution report when automation tests are run |

## 6. Expected Behavior

Phoenix should:

| Area | Expected Behavior |
|---|---|
| Story understanding | Interpret the scenario intent from story + criteria accurately |
| Criteria handling | Preserve and operationalize acceptance criteria in generated outputs |
| Manual generation | Produce actionable, complete manual test cases |
| Automation generation | Produce executable Playwright tests aligned to the target page |
| Control coverage | Handle login forms, dropdowns, upload controls, dynamic content, autocomplete, filters, and sort controls correctly |
| Output structure | Write artifacts into `manual_tests/`, `test_results/`, and `reports/` |

## 7. PASS / FAIL / NEEDS REVIEW Criteria

| Status | Definition |
|---|---|
| PASS | Phoenix generates scenario-specific manual and automation outputs, execution is usable, and the core control behavior is represented correctly |
| FAIL | Phoenix misses the scenario intent, produces generic or broken outputs, ignores key criteria, or execution clearly fails due to poor generated logic |
| NEEDS REVIEW | Partial success exists, but evidence is inconclusive because of environment limits, unstable third-party data, or a mixed-quality output that cannot be confidently classified as pass |

## 8. Common Failure Patterns

Expected failure patterns to watch for:

1. Generic fallback scripts with placeholder comments instead of real actions.
2. Manual tests that contain only navigation and omit the core control interaction.
3. Acceptance criteria copied as comments but not implemented.
4. Negative validation scenarios treated like positive happy paths.
5. Dynamic content scenarios missing reliable waits or assertions.
6. File upload scenarios missing file selection mechanics.
7. OrangeHRM autocomplete or filters handled too vaguely for real execution.
8. Weak assertions that check only URL and nothing functional.
9. Output files overwritten without scenario isolation.
10. Reports missing because execution flow is not used or execution fails too early.

## 9. Final Summary Section

Use this section after execution to capture:

| Metric | Result |
|---|---|
| Total Tested | 11 |
| Passed | TBD |
| Failed | TBD |
| Needs Review | TBD |

Also record:

1. Top 10 problems found.
2. Repeated root cause patterns.
3. Scenario-specific strengths.
4. How to improve testing accuracy, effectiveness, and efficiency without changing code.
