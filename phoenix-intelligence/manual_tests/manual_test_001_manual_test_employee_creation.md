Application URL: https://opensource-demo.orangehrmlive.com/web/index.php/auth/login

Test Case: Manual Test: employee_creation

Description: As a PIM Manager, I want to add a new employee to the system so that their record is officially registered.

Steps:
  1. Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login
  2. Step 1: Navigate to PIM > Add Employee.
  3. Step 2: Input First Name, Middle Name, and Last Name.
  4. Step 3: Toggle the "Create Login Details" switch.
  5. Step 4: Upload an employee profile picture (testing file upload).
  6. Step 5: Click "Save" and verify a "Successfully Saved" toast message appears.
  7. Step 6: Framework Testing Goal: Test File Upload handling and Shadow DOM/Switch toggles.
  8. Step 7: 3. Admin: System User Search (Table Interception)
  9. Step 8: Goal: Test your framework’s capability to handle dynamic web tables and filtering.

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION