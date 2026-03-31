Application URL: https://opensource-demo.orangehrmlive.com/web/index.php/auth/login

Test Case: Manual Test: user_search_by_role_and_status

Description: As a System Admin, I want to search for existing users by their Role and Status so that I can manage their permissions.

Steps:
  1. Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login
  2. Step 1: Navigate to Admin > User Management.
  3. Step 2: Select "User Role" as ESS and "Status" as Enabled from the dropdowns.
  4. Step 3: Click "Search".
  5. Step 4: Verify that the resulting table contains only users with the ESS role.
  6. Step 5: Verify "No Records Found" logic by searching for a non-existent username.
  7. Step 6: Framework Testing Goal: Test Table scrapers, Dropdown selection, and List validations.
  8. Step 7: 4. Leave: Apply for Leave (Date & Workflow)
  9. Step 8: Goal: Test logic involving date pickers and business workflows.

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION