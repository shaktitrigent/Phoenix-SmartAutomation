Application URL: https://opensource-demo.orangehrmlive.com/web/index.php/auth/login

Test Case: Manual Test: hr_admin_login_dashboard_access

Description: As an HR Admin, I want to log in to the system using valid credentials so that I can access the dashboard.

Steps:
  1. Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login
  2. Step 1: Verify login with username Admin and password admin123.
  3. Step 2: Verify that an error message "Invalid credentials" appears for incorrect passwords.
  4. Step 3: Verify that clicking "Logout" redirects the user back to the Login page and clears the session.
  5. Step 4: Framework Testing Goal: Test Explicit Waits for the dashboard to load and Negative Testing assertions.
  6. Step 5: 2. PIM: Add New Employee (Form Submission)
  7. Step 6: Goal: Test your framework's ability to interact with complex forms and toggles.

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION