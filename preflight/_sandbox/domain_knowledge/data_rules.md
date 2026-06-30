# Data Rules

Document field formats, validation rules, and data constraints for _sandbox.

## Field Formats

Example:
| Field         | Format / Constraint                          |
|---------------|----------------------------------------------|
| Employee ID   | Auto-generated 4-digit number (e.g. 0042)    |
| Phone         | +1 (555) 000-0000 — no extension accepted    |
| Date fields   | MM/DD/YYYY format                            |
| Leave types   | Annual, Casual, Medical, Maternity           |

YOUR TABLE:
| Field | Format / Constraint |
|-------|---------------------|
| (fill in) | (fill in) |

## Required vs Optional Fields

Example:
- Add Employee form: First Name and Last Name are required; Middle Name is optional
- Apply Leave: Leave Type, From Date, To Date are required; Comment is optional

YOUR NOTES:
[Add your observations here]

## Validation Rules

Example:
- Password: minimum 8 characters, at least one uppercase letter
- Employee ID: cannot be changed after creation
- Leave dates: From Date must be before To Date; cannot apply for past dates if policy is strict

YOUR NOTES:
[Add your observations here]

## Test Credentials

Example:
- Admin: username `Admin`, password `admin123`
- Test user: (fill in)

Note: Store actual credentials in `.env`, not here. This file is committed to git.
