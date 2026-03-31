Application URL: https://opensource-demo.orangehrmlive.com/web/index.php/auth/login

Test Case: Manual Test: candidate_vacancy_association

Description: As a Recruiter, I want to add a new candidate and associate them with an existing vacancy.

Steps:
  1. Navigate to https://opensource-demo.orangehrmlive.com/web/index.php/auth/login
  2. Step 1: Navigate to Recruitment > Candidates.
  3. Step 2: Click the + Add button.
  4. Step 3: Enter candidate details and start typing in the "Vacancy" field to trigger the Autocomplete suggestion.
  5. Step 4: Select a vacancy from the suggestions.
  6. Step 5: Verify that the candidate status is set to "Application Initiated."
  7. Step 6: Framework Testing Goal: Test AJAX/Autocomplete fields and Dynamic Element presence.

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION