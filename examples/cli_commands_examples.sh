#!/bin/bash
# Sample CLI commands for Test Automation Practice website
# Website: https://testautomationpractice.blogspot.com/

# Initialize project
phoenix init --project-name test-automation-practice

# User Story 1: Form Submission
phoenix generate \
  --story "As a user, I want to fill in the form with my personal details and submit it, so that the system accepts and processes my registration correctly" \
  --url "https://testautomationpractice.blogspot.com/" \
  --criteria "User can enter name, email, phone and address" \
  --criteria "User can select gender and multiple days" \
  --criteria "User can choose a country from the dropdown" \
  --criteria "The form must submit successfully without errors" \
  --risk smoke

# User Story 2: Table Data Validation
phoenix generate \
  --story "As a tester, I want to verify the static web table data for books (Book Name, Author, Subject, Price), so that I can ensure the table displays correct information and sorting behaves as expected" \
  --url "https://testautomationpractice.blogspot.com/" \
  --criteria "Book table loads with expected column headers" \
  --criteria "All rows display accurate book details" \
  --criteria "Sorting or filtering functions work if provided" \
  --risk regression

# User Story 3: Alert Handling
phoenix generate \
  --story "As a user, I want to interact with alerts and popup messages, so that the application displays and handles alert boxes appropriately (accept, cancel, input text)" \
  --url "https://testautomationpractice.blogspot.com/" \
  --criteria "Simple alerts appear when triggered" \
  --criteria "Confirmation alerts can be accepted or dismissed" \
  --criteria "Prompt alerts allow input and reflect that input correctly" \
  --risk regression

# Execute all generated tests
phoenix execute --project test-automation-practice
