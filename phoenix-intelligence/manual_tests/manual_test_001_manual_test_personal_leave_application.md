Application URL: https://opensource-demo.orangehrmlive.com/web/index.php/auth/login

Test Case: Manual Test: personal_leave_application

Description: As an Employee, I want to apply for a "Personal Leave" for a specific date range so that my manager can approve it.

Steps:
  1. Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login
  2. Step 1: Navigate to Leave > Apply.
  3. Step 2: Select "Leave Type" (e.g., CAN - Personal).
  4. Step 3: Use the Date Picker to select a "From Date" (Tomorrow) and "To Date" (Day after tomorrow).
  5. Step 4: Verify the "Partial Days" dropdown is disabled if only one day is selected.
  6. Step 5: Submit and verify the leave appears in the "My Leave" list.
  7. Step 6: Framework Testing Goal: Test JS-based Date Pickers and Calendar widgets.
  8. Step 7: 5. Recruitment: Candidate Management (Dynamic UI)
  9. Step 8: Goal: Test interaction with dynamic "Add" buttons and autocomplete fields.

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION