# Phoenix SmartAutomation — End User Guide

> For teams who have received `phoenix-intelligence.exe` from their administrator.
> No source code or build tools are required.

---

## What You Receive

| File | What it does |
|---|---|
| `phoenix-intelligence.exe` | The AI brain — runs locally, never shares your code externally |
| `phoenix_shared-0.1.3-py3-none-any.whl` | Shared data models — install this **first** |
| `phoenix_core-0.1.3-py3-none-any.whl` | The `phoenix` CLI — your day-to-day tool |

All three files must stay in the same folder. The `.whl` files are not on PyPI — install them from these files only.

---

## How Phoenix Works

```
You write a user story
        │
        ▼  phoenix generate
Phoenix reads the story → calls Claude AI → writes human-readable test cases
        │
        ▼  You review manual_tests/*.md   ← the only manual step
        │
        ▼  phoenix automate
Phoenix turns your reviewed test cases into Playwright test scripts
        │
        ▼  phoenix run
Phoenix runs all tests, retries failures automatically, saves an HTML report
```

---

## Prerequisites

| Requirement | Where to get it |
|---|---|
| Python ≥ 3.11 | [python.org/downloads](https://www.python.org/downloads/) |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| Node.js ≥ 18 *(optional)* | [nodejs.org](https://nodejs.org) — improves locator accuracy |

**Installing Python:** Run the installer and **check "Add Python to PATH"** on the first screen before clicking Install. Without this, `python` and `pip` will not be found.

**Verify your installs:**
```powershell
python --version   # must be 3.11 or higher
node --version     # optional
```

---

## Part 1 — Start the Intelligence Server

The server must be running before you use any `phoenix` commands. Start it once and leave it running.

### Step 1.1 — Place the executable

Copy `phoenix-intelligence.exe` to a stable location:
```
C:\Phoenix\phoenix-intelligence.exe
```

### Step 1.2 — Set your API key

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

To set it permanently (survives reboots):
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

### Step 1.3 — Start the server

Run from a terminal — do **not** double-click the file in Explorer.
```powershell
C:\Phoenix\phoenix-intelligence.exe
```

> **Windows SmartScreen alert:** First run only — click **"More info"** then **"Run anyway"**.

You will see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**Keep this terminal open all day.** The server must stay running.

### Step 1.4 — Verify the server

Open a second terminal:
```powershell
curl http://localhost:8001/health
```

Expected response:
```json
{"status": "ok", "llm": {"configured": true, "provider": "anthropic"}}
```

---

## Part 2 — Install Phoenix CLI

### For First-Time Users

**Step 2.1 — Create a virtual environment**
```powershell
python -m venv phoenix-venv
phoenix-venv\Scripts\activate
```

You will see `(phoenix-venv)` at the start of your prompt. Every new terminal needs this step.

**Step 2.2 — Install from the wheel files**

Run these from the folder containing the `.whl` files:
```powershell
pip install phoenix_shared-0.1.3-py3-none-any.whl
pip install phoenix_core-0.1.3-py3-none-any.whl
```

**Step 2.3 — Install the Playwright browser**
```powershell
playwright install chromium
```

**Step 2.4 — Verify**
```powershell
phoenix --version
phoenix --help
```

---

## Part 2B — Upgrade (Existing Users)

If you already have Phoenix installed and have received new `.whl` files, follow these steps to cleanly upgrade.

### Step 1 — Stop the old server

If `phoenix-intelligence.exe` is running, close that terminal window.

### Step 2 — Activate your virtual environment

```powershell
phoenix-venv\Scripts\activate
```

### Step 3 — Uninstall the old packages

```powershell
pip uninstall phoenix-core -y
pip uninstall phoenix-shared -y
```

**What happens:** pip removes the installed CLI and shared models. Your project files (`manual_tests/`, `tests/`, `.phoenixrc`) are not affected — they stay on disk exactly as they are.

### Step 4 — Install the new packages

```powershell
pip install phoenix_shared-0.1.3-py3-none-any.whl
pip install phoenix_core-0.1.3-py3-none-any.whl
```

> If your new files have a different version number (e.g. `0.2.0`), use that filename instead.

### Step 5 — Replace the server executable

1. Delete the old `phoenix-intelligence.exe`
2. Copy the new `phoenix-intelligence.exe` to the same location (`C:\Phoenix\`)
3. Start the new server: `C:\Phoenix\phoenix-intelligence.exe`

### Step 6 — Verify the upgrade

```powershell
phoenix --version
phoenix doctor
```

`phoenix doctor` checks the API key, server connection, Playwright, and all plugins. Fix any issues before continuing.

### Full Uninstall (Remove Everything)

To completely remove Phoenix from your machine:

```powershell
# 1. Activate the virtual environment
phoenix-venv\Scripts\activate

# 2. Uninstall both packages
pip uninstall phoenix-core -y
pip uninstall phoenix-shared -y

# 3. Deactivate and delete the virtual environment
deactivate
Remove-Item -Recurse -Force phoenix-venv

# 4. Delete the server executable
Remove-Item C:\Phoenix\phoenix-intelligence.exe
```

Your project folders (with your user stories, manual tests, and generated scripts) are **not** deleted by any of these steps — remove them manually if needed.

---

## Part 3 — Set Up a Project

Each application you test gets its own project folder.

### Step 3.1 — Create the project

```powershell
mkdir my-project
cd my-project
phoenix init --base-url "https://your-app.com"
```

**What happens:** Phoenix creates the full folder structure with a starter user story, domain knowledge files, and configuration. You get:

```
my-project/
├── .phoenixrc          ← project config (edit this first)
├── .env                ← environment variables template
├── conftest.py         ← Playwright fixtures (auto-configured)
├── user_stories/       ← write your user stories here
├── domain_knowledge/   ← project-wide context (URLs, UI patterns, data rules)
├── manual_tests/       ← Phoenix writes test cases here (auto-created)
├── tests/              ← Phoenix writes Playwright scripts here (auto-created)
├── test_data/          ← Phoenix writes test data here (auto-created)
├── locators/           ← Phoenix writes element locators here (auto-created)
├── reports/            ← HTML reports go here (auto-created)
└── logs/               ← execution logs go here (auto-created)
```

### Step 3.2 — Configure the project

Open `.phoenixrc` and verify the URL and intelligence server address:
```toml
[project]
name            = "my-project"
base_url        = "https://your-app.com"
default_browser = "chromium"

[intelligence]
base_url = "http://localhost:8001/api/v1"
timeout  = 300
```

### Step 3.3 — Set your test credentials

Copy `.env` to `.env.local` and fill in your values:
```powershell
copy .env .env.local
```

Edit `.env.local`:
```
APP_URL=https://your-app.com
TEST_USERNAME=your_test_username
TEST_PASSWORD=your_test_password
ANTHROPIC_API_KEY=sk-ant-...
```

Load them in your terminal:
```powershell
Get-Content .env.local | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
```

> Do this in every new terminal session before running `phoenix` commands.

### Step 3.4 — Check everything works

```powershell
phoenix doctor
```

**What happens:** Phoenix checks your API key, intelligence server connection, Playwright browser, and pytest plugins. Each check prints `OK` or `FAIL` with a fix suggestion. Do not proceed until all checks pass.

---

## Part 4 — Session Checklist (Every Day)

Before starting work, run these three things in order:

```powershell
# Terminal 1 — start or verify the server (leave this open)
C:\Phoenix\phoenix-intelligence.exe

# Terminal 2 — your working terminal
phoenix-venv\Scripts\activate
Get-Content .env.local | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
```

---

## Part 5 — Commands Reference

### `phoenix generate` — Create test cases from a user story

**Basic usage:**
```powershell
phoenix generate --story-file user_stories/login.txt --url "https://your-app.com"
```

**What happens:**
1. Phoenix reads your user story file
2. Calls the intelligence server, which asks Claude AI to write test cases
3. Runs a quality check on every generated test
4. Writes passing tests to `manual_tests/` as Markdown files
5. Writes realistic test data to `test_data/<module>.json`

**What you see in the terminal:**
```
Generating test cases...
  Domain knowledge loaded from domain_knowledge/
  ✓ Generated 3 manual test(s)
  ✓ Generated 0 automation test(s)
```

**What to do next:** Open `manual_tests/login.md` and review it. Add missing steps or fix anything that looks wrong. This is the only step that requires your attention before generating scripts.

**All flags:**

| Flag | What it does |
|---|---|
| `--story-file <path>` | Read the user story from a file |
| `--story "text"` | Pass the story text directly on the command line |
| `--jira PROJ-123` | Fetch story + attachments from a Jira ticket |
| `--url <url>` | Application URL (used for live page inspection) |
| `--type manual` | Generate only manual test cases (default) |
| `--type both` | Generate manual + automation scripts in one step |
| `--docs <path>` | Attach a supporting document file or folder |
| `--clean` | Delete existing `manual_tests/` files before generating |
| `--no-gate` | Save all generated tests even if they have short descriptions or few steps |
| `--strict-gate` | Apply strict CI-grade thresholds (≥ 2 steps, ≥ 10-char description) |
| `--verbose` | Show detailed output including loaded documents |

**When to use `--no-gate`:**
If you see `Manual test '...' failed quality gate` and `Generated 0 manual test(s)`, add `--no-gate` to save the tests anyway so you can review and fill in the missing details manually:
```powershell
phoenix generate --story-file user_stories/login.txt --url "https://your-app.com" --no-gate
```

**When to use `--strict-gate`:**
In CI pipelines where you want to enforce that every generated test meets minimum completeness standards before it is saved.

---

### `phoenix automate` — Turn manual tests into Playwright scripts

**Basic usage:**
```powershell
phoenix automate --url "https://your-app.com"
```

**What happens:**
1. Phoenix reads all `manual_test_*.md` files from `manual_tests/`
2. Sends them to the intelligence server, which writes Playwright + pytest scripts
3. Runs a quality check — blocks any script that contains placeholder code or invalid assertions
4. Writes passing scripts to `tests/` and saves element locators to `locators/`

**What you see in the terminal:**
```
Automating 3 manual test(s) from 'manual_tests'
  TC-001: Login — Happy Path  (manual_test_001_login_happy_path.md)
  TC-002: Login — Invalid Password  (manual_test_002_login_invalid_password.md)
  TC-003: Login — Empty Username  (manual_test_003_login_empty_username.md)

Calling intelligence server to generate automation scripts…

✓ Generated 3 automation script(s) → tests/
  TC-001: Login — Happy Path  →  test_001_login_happy_path.py
  TC-002: Login — Invalid Password  →  test_002_login_invalid_password.py
  TC-003: Login — Empty Username  →  test_003_login_empty_username.py

Next: phoenix run
```

**All flags:**

| Flag | What it does |
|---|---|
| `--url <url>` | Application URL for context |
| `--file <path>` | Automate a single manual test file instead of the whole directory |
| `--test-case "name"` | Automate only the test case whose name contains this text |
| `--manual-dir <path>` | Use a different directory instead of `manual_tests/` |
| `--clean` | Delete existing `tests/` scripts before generating |

**Automate a single file:**
```powershell
phoenix automate --file manual_tests/manual_test_001_login.md --url "https://your-app.com"
```

**Automate one specific test case by name:**
```powershell
phoenix automate --test-case "valid login" --url "https://your-app.com"
```
Phoenix will list all available test case names if no match is found.

**Using your own test files (external format):**
Phoenix accepts test files created outside the framework. Supported filename patterns:

| Pattern | Example |
|---|---|
| `manual_test_*.md` | `manual_test_001_login.md` — Phoenix canonical |
| `test_*.md` | `test_login.md` — common short form |
| `*_manual.md` | `login_manual.md` — suffix style |
| `TC-*.md` | `TC-001-login.md` — Jira-style ID |
| `*_test.md` | `login_test.md` — snake-case suffix |

Your files can use either the Phoenix table format or plain numbered/bulleted steps:
```markdown
## Test Steps
1. Navigate to the login page
2. Enter email muthamil_r@trigent.com and click Next
3. Enter the password and click Submit
4. Verify the Dashboard page is displayed
```

---

### `phoenix run` — Execute the generated tests

**Basic usage:**
```powershell
phoenix run
```

**What happens:**
1. Phoenix finds all `test_*.py` files in `tests/`
2. Runs them with pytest + Playwright (headless browser by default)
3. If a test fails, retries it automatically up to 3 times, attempting a fix between each retry
4. Saves a detailed JSONL log to `logs/`
5. Generates a full HTML report in `reports/`

**What you see in the terminal:**
```
Running 3 test(s) — healing=on, max_attempts=3

  ✓ test_001_login_happy_path.py  (1 attempt)  4.2s
  ✗ test_002_login_invalid_password.py  (3 attempts, healed via locator_error)  12.1s
  ✓ test_003_login_empty_username.py  (1 attempt)  3.8s

Run ID: run_20260605_143022
  HTML report: reports/report_run_20260605_143022.html
Self-healed: 1 test(s) recovered after retry
1/3 test(s) failed after 3 attempt(s)
```

**All flags:**

| Flag | What it does |
|---|---|
| `--browser chromium` | Browser to use: `chromium` (default), `firefox`, `webkit` |
| `--heal` | Enable self-healing retries — on by default |
| `--max-attempts 3` | Maximum retry attempts per failing test |
| `--failed-only` | Re-run only tests that failed in the previous run |
| `--headed` | Open a visible browser window — useful for debugging |
| `--slow-mo 500` | Slow down each action by N milliseconds — use with `--headed` |
| `--logs-dir <path>` | Custom directory for execution logs |

**Run in headed mode (see the browser):**
```powershell
phoenix run --headed
```
The browser window opens so you can watch each test step execute in real time.

**Run in headed mode with slow motion:**
```powershell
phoenix run --headed --slow-mo 1000
```
Each click and fill action is slowed down by 1 second — useful for debugging flaky tests.

**Re-run only what failed:**
```powershell
phoenix run --failed-only
```

---

### `phoenix fix` — Auto-repair failing scripts

**Basic usage:**
```powershell
phoenix fix
```

**What happens:**
1. Phoenix reads the most recent run log from `logs/`
2. Finds every test that failed with an error message
3. Sends each failing script and its exact error to the intelligence server
4. Claude AI identifies the root cause and rewrites the broken section
5. Saves the corrected script back to disk, overwriting the old one

**What you see in the terminal:**
```
Fixing 2 failed test(s) from run run_20260605_143022

  Fixing: test_002_login_invalid_password.py  [locator_error]
    Fixed (replaced get_by_text with get_by_role for error message locator)
  Fixing: test_005_checkout_payment.py  [timeout_error]
    Fixed (added explicit wait before card number field interaction)

✓ Fixed 2 script(s).
Re-run fixed tests with: phoenix run --failed-only
```

**All flags:**

| Flag | What it does |
|---|---|
| `--dry-run` | Show what would be fixed without writing any files |
| `--run-id <id>` | Fix failures from a specific run instead of the most recent |
| `--url <url>` | Pass the application URL for additional context |

---

### `phoenix clean` — Remove all generated files

**Basic usage:**
```powershell
phoenix clean
```

**What happens:** Deletes all generated artifacts from the current project directory — test scripts, manual test files, reports, locators, logs, test data, and cache files. Your user stories and source files are never touched.

**What you see in the terminal:**
```
Removed: manual_tests/
Removed: tests/
Removed: reports/
Removed: locators/
Removed: logs/
Removed: test_data/
✓ Clean complete — removed 6 item(s).
```

**Preview what would be deleted first:**
```powershell
phoenix clean --dry-run
```

Use `phoenix clean` before a full regeneration run to ensure no stale files from a previous session contaminate the new output.

---

### `phoenix report` — View test results

**Basic usage:**
```powershell
phoenix report
```

**What happens:** Prints a summary table to the terminal and generates a self-contained HTML report in `reports/`. Open the HTML file in any browser — no server required.

**All flags:**

| Flag | What it does |
|---|---|
| `--open` | Generate the report and open it in your default browser automatically |
| `--run-id <id>` | Report for a specific run (not the most recent) |
| `--trend` | Multi-run trend report across the last 20 runs |
| `--trend --last 5` | Trend across the last 5 runs |
| `--env QA` | Add an environment label (e.g. QA, Staging) to the report header |
| `--project "My App"` | Set the project name shown in the report header |

---

### `phoenix doctor` — Check your setup

```powershell
phoenix doctor
```

**What happens:** Runs four checks and prints a pass/fail for each:
- **API key** — is `ANTHROPIC_API_KEY` set and non-empty?
- **Intelligence server** — can Phoenix reach `http://localhost:8001`?
- **Database** — is the local SQLite database writable?
- **pytest plugins** — are `pytest-json-report` and `pytest-html` installed?

Run this at the start of every new session if something feels wrong.

---

### `phoenix logs` — View run history

```powershell
phoenix logs              # last 10 runs
phoenix logs --run-id <id>  # per-test detail for one run
```

**What you see:**
```
Run ID       Started               Status   T    P    F       s
run_2026..   2026-06-05 14:30:22   passed   3    3    0    20.1
run_2026..   2026-06-05 13:15:08   failed   3    2    1    18.7
```

---

### `phoenix locators` — Inspect element locators

```powershell
phoenix locators             # all saved locators
phoenix locators --page login  # only the login page
```

Shows the element name, page, strategy, confidence score, and number of fallback locators for every element Phoenix has learned.

---

### `phoenix init` — Create a new project

```powershell
phoenix init --base-url "https://your-app.com"
```

Run once per new project. Creates the full folder structure with starter files.

---

### `phoenix migrate` — Update an existing project

```powershell
phoenix migrate
```

Adds any missing directories and configuration files to an existing project without overwriting anything you have already customised.

---

### `phoenix jira health` / `phoenix jira show` — Jira integration

```powershell
phoenix jira health           # check Jira connectivity and credentials
phoenix jira show PROJ-123    # preview what Phoenix would extract from a ticket
```

See Part 7 for full Jira setup instructions.

---

## Part 6 — Daily Workflow

### New feature or module — full cycle

```powershell
# 1. Write a user story
notepad user_stories\checkout.txt

# 2. (Optional) Add wireframes or spec docs in user_stories\checkout\

# 3. Generate manual test cases
phoenix generate --story-file user_stories/checkout.txt --url "https://your-app.com"

# 4. Review manual_tests/checkout.md — add missing steps, fix expected results

# 5. Generate Playwright scripts
phoenix automate --url "https://your-app.com"

# 6. Run the tests
phoenix run

# 7. Fix any failures
phoenix fix
phoenix run --failed-only

# 8. View the report
phoenix report --open
```

### Using a test file written outside of Phoenix

Place your file in the `manual_tests/` folder. It can be named with any of the supported patterns (`TC-001-login.md`, `test_login.md`, etc.) and can use plain numbered steps instead of the pipe-table format. Then run:

```powershell
phoenix automate --url "https://your-app.com"
```

Phoenix will pick it up automatically.

### Automating just one specific test

```powershell
# By file path
phoenix automate --file manual_tests/manual_test_001_login.md --url "https://your-app.com"

# By test case name (case-insensitive substring match)
phoenix automate --test-case "invalid password" --url "https://your-app.com"
```

### Debugging a failing test visually

```powershell
# Watch the browser execute the test step by step
phoenix run --headed --slow-mo 800
```

### Clean start before regenerating everything

```powershell
phoenix clean
phoenix generate --story-file user_stories/login.txt --url "https://your-app.com"
phoenix automate --url "https://your-app.com"
phoenix run
```

---

## Part 7 — Jira Integration (Optional)

### One-time setup

Set these environment variables (add them to `.env.local` so they load automatically):
```powershell
$env:JIRA_URL        = "https://yourcompany.atlassian.net"
$env:JIRA_EMAIL      = "you@company.com"
$env:JIRA_API_TOKEN  = "your-api-token"
```

Get your API token from [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).

Enable the `[jira]` section in `.phoenixrc`:
```toml
[jira]
url                       = "https://yourcompany.atlassian.net"
project_key               = "PROJ"
acceptance_criteria_field = "description"
download_attachments      = true
```

### Verify the connection
```powershell
phoenix jira health
```

### Preview a ticket before generating
```powershell
phoenix jira show PROJ-123
```
Shows the story text, acceptance criteria, and attached files — without calling the AI or writing any files.

### Generate tests from a Jira ticket
```powershell
phoenix generate --jira PROJ-123 --url "https://your-app.com"
```
Phoenix fetches the summary, description, acceptance criteria, and attachments, then follows the same pipeline as the file-based approach.

---

## Part 8 — Writing Good User Stories

The quality of your user story directly determines the quality of the generated tests.

**Minimum that works:**
```
User Story: Login
Application URL: https://your-app.com/login

As a registered user I want to log in.

Acceptance Criteria:
- Navigate to the login page and log in with Username admin and Password secret
- The dashboard should be shown after login
- When I enter a wrong password, an error message should appear
```

**Better (more test scenarios):**
```
User Story: Login to Skylark
Application URL: https://skylark.dev.trigent.com/

As a registered user
I want to log in to Skylark
So that I can access the dashboard and perform my tasks.

Acceptance Criteria:

Scenario 1: Successful Login
- Open the application URL
- Click the Sign in with Google button
- On the Google sign-in page, click Use Another Account
- Enter the email address muthamil_r@trigent.com and click Next
- Enter the password and click Submit
- Verify the Dashboard page is displayed

Scenario 2: Invalid Credentials
- Navigate to the login page
- Enter an incorrect password
- Verify an error message is shown

Scenario 3: Empty Fields
- Navigate to the login page
- Leave the email blank and click Next
- Verify a validation error is shown for the email field
```

**Tips:**
- Use plain English — no technical jargon needed
- One scenario per logical flow (happy path, error, edge case)
- Name the fields users will fill in (email, password, username)
- Specify what the user should see after each key action

---

## Part 9 — Project Configuration

### `.phoenixrc` — full reference

```toml
[project]
name            = "my-project"
base_url        = "https://your-app.com"
default_browser = "chromium"          # chromium | firefox | webkit

[intelligence]
base_url    = "http://localhost:8001/api/v1"
timeout     = 300                     # seconds — increase to 600 for complex stories
retry_count = 3

[logging]
level = "INFO"                        # DEBUG | INFO | WARNING

# Jira integration (optional — remove # to enable)
# [jira]
# url                       = "https://yourcompany.atlassian.net"
# project_key               = "PROJ"
# acceptance_criteria_field = "description"
# download_attachments      = true
```

### Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `APP_URL` | Yes | Application base URL |
| `TEST_USERNAME` | Yes | Test account username |
| `TEST_PASSWORD` | Yes | Test account password |
| `PHOENIX_BROWSER` | No | Override default browser |
| `PWHEADED` | No | Set to `1` to open a visible browser window |
| `PWSLOWMO` | No | Milliseconds to slow down each action (use with `PWHEADED`) |
| `JIRA_URL` | Jira only | Jira instance URL |
| `JIRA_EMAIL` | Jira only | Your Jira account email |
| `JIRA_API_TOKEN` | Jira only | Jira API token — never store in config files |

---

## Part 10 — Troubleshooting

### `phoenix` command not found

```
phoenix : The term 'phoenix' is not recognized
```

Your virtual environment is not active. Run:
```powershell
phoenix-venv\Scripts\activate
```

---

### `Generated 0 manual test(s)` — tests not saved

The quality gate rejected the generated tests. The terminal will now show exactly why, for example:
```
⚠ Manual test 'TC-001: Login' failed quality gate: needs ≥ 1 steps, got 0
⚠ Manual test 'TC-002: Dashboard' failed quality gate: description too short
```

**Fix option 1:** Add more detail to your user story's acceptance criteria — more specific steps lead to better generated tests.

**Fix option 2:** Use `--no-gate` to save the tests anyway so you can edit them manually:
```powershell
phoenix generate --story-file user_stories/login.txt --url "https://your-app.com" --no-gate
```

---

### My manually-written test file is not being picked up

Check the filename. Phoenix looks for these patterns inside `manual_tests/`:

```
manual_test_*.md     ← Phoenix canonical
test_*.md
*_manual.md
TC-*.md
*_test.md
```

Rename your file to match one of these patterns, or move it to `manual_tests/` if it is in a different folder.

---

### `phoenix automate --file` was crashing (old build)

If you are on a build from before June 2026, `phoenix automate --file` would crash with:
```
NameError: name 'manual_path' is not defined
```

This is fixed in the current build. Upgrade using the steps in Part 2B.

---

### Intelligence server won't start

- Confirm `ANTHROPIC_API_KEY` is set: `echo $env:ANTHROPIC_API_KEY`
- Check port 8001 is free: `netstat -ano | findstr :8001`
- If the port is taken, stop the process using it or change the port in `.phoenixrc`

---

### `phoenix generate` or `phoenix automate` hangs or shows "Connection refused"

The intelligence server is not running. Open a new terminal and start it:
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
C:\Phoenix\phoenix-intelligence.exe
```

---

### Tests fail with locator or timeout errors

```powershell
# Let Phoenix fix them automatically
phoenix fix

# Then re-run only the fixed tests
phoenix run --failed-only
```

If the same test keeps failing after fix, run it in headed mode to watch what is happening:
```powershell
phoenix run --headed --slow-mo 1000
```

---

### Supporting documents not being used

- Place the folder next to the story file with the same name:
  `user_stories/checkout.txt` → `user_stories/checkout/wireframe.pdf`
- For PDF/DOCX/XLSX files, install the optional extractors:
  ```powershell
  pip install pypdf python-docx openpyxl
  ```
- Run with `--verbose` to confirm documents were loaded:
  ```powershell
  phoenix generate --story-file user_stories/checkout.txt --url "https://your-app.com" --verbose
  ```

---

### Slow test generation (more than 60 seconds)

This is normal for complex stories — the AI reads the story, optionally inspects the live page, and writes complete test cases. Increase the timeout in `.phoenixrc` if you see timeout errors:
```toml
[intelligence]
timeout = 600
```

---

## Quick Reference Card

### Every session
```
Terminal 1 (server)   C:\Phoenix\phoenix-intelligence.exe     ← keep open
Terminal 2 (work)     phoenix-venv\Scripts\activate
                      [load .env.local]
```

### Full workflow
```
1. Write story        user_stories/myfeature.txt
2. Generate tests     phoenix generate --story-file user_stories/myfeature.txt --url <url>
3. Review             open manual_tests/  ← only manual step
4. Generate scripts   phoenix automate --url <url>
5. Run                phoenix run
6. Fix failures       phoenix fix  →  phoenix run --failed-only
7. View report        phoenix report --open
```

### Key commands at a glance
```
phoenix doctor                          check everything is connected
phoenix generate --story-file <path>    create test cases from a story
phoenix generate ... --no-gate          bypass quality check (save all tests)
phoenix automate                        create Playwright scripts from test cases
phoenix automate --file <path>          automate a single test file
phoenix automate --test-case "name"     automate one specific test by name
phoenix run                             run all tests
phoenix run --headed --slow-mo 800      run with visible browser (debug mode)
phoenix run --failed-only               re-run only what failed
phoenix fix                             auto-repair failing scripts
phoenix clean                           delete all generated files
phoenix clean --dry-run                 preview what would be deleted
phoenix report --open                   view the HTML report in a browser
phoenix logs                            see run history
phoenix doctor                          diagnose connection and setup issues
```

### New in this release
| Feature | How to use |
|---|---|
| Quality gate failures shown in terminal | They now print as yellow warnings so you know exactly why tests were skipped |
| Permissive gate by default | Short tests (1 step, brief description) now pass — no more `Generated 0 manual test(s)` for simple stories |
| `--no-gate` flag | `phoenix generate ... --no-gate` saves all tests regardless of quality |
| `--strict-gate` flag | `phoenix generate ... --strict-gate` enforces strict CI-grade thresholds |
| Flexible filename patterns | `TC-001-login.md`, `test_login.md`, `login_test.md` all work in `manual_tests/` |
| Plain list steps | Write steps as `1. Navigate to page` instead of pipe tables |
| `phoenix clean` command | Removes all generated artifacts in one command |
| `phoenix run --headed` | Opens a visible browser window for debugging |
| `phoenix run --slow-mo N` | Slows down each action by N milliseconds |
| `phoenix automate --file` fixed | Was crashing with NameError in the May 2026 build — now works correctly |
