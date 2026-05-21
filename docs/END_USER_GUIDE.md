# Phoenix SmartAutomation — End User Guide

> This guide is for teams who have received `phoenix-intelligence.exe` from their administrator.
> No source code, Python environment, or build tools are required to run the intelligence server.

---

## What You Receive

| File | Purpose |
|---|---|
| `phoenix-intelligence.exe` | The AI intelligence server — runs locally, never shares your code externally |
| `phoenix_shared-0.1.0-py3-none-any.whl` | Shared data models — must be installed before phoenix-core |
| `phoenix_core-0.1.0-py3-none-any.whl` | The `phoenix` CLI tool — your day-to-day command |

Keep all three files in the same folder. The `.whl` files are installed once via pip — they are **not** available on PyPI and must be installed from the files you received.

The `.exe` is a self-contained server. It does **not** require Python to be installed to run.
It communicates with the Anthropic Claude API using your own API key — your test code and application data never leave your machine.

---

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Python | ≥ 3.11 | Required for the `phoenix` CLI only |
| Node.js | ≥ 18 | Required for live page inspection (optional but recommended) |
| Anthropic API key | — | From [console.anthropic.com](https://console.anthropic.com) |

### Installing Python

If `python --version` returns an error or shows a version below 3.11:

1. Download Python from [python.org/downloads](https://www.python.org/downloads/)
2. Run the installer — **check "Add Python to PATH"** on the first screen before clicking Install
3. Open a new terminal and verify: `python --version`

> If you skip "Add Python to PATH", the `python` and `pip` commands will not be found in your terminal and every step below will fail.

### Installing Node.js (optional but recommended)

If `node --version` returns an error:

1. Download Node.js from [nodejs.org](https://nodejs.org) (choose the LTS version)
2. Run the installer with default settings
3. Open a new terminal and verify: `node --version`

Node.js is only needed for live page inspection during `phoenix automate`. Tests still run without it — locators will be less precise.

### Check your versions

```powershell
python --version
node --version
```

---

## Part 1 — Start the Intelligence Server

The intelligence server must be running before you use any `phoenix` CLI commands.
Start it once and leave it running in a dedicated terminal.

### Step 1.1 — Place the executable

Copy `phoenix-intelligence.exe` to a stable location, for example:

```
C:\Phoenix\phoenix-intelligence.exe
```

### Step 1.2 — Set your API key

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

To set it permanently (so you don't repeat this every session):

```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

### Step 1.3 — Start the server

Run the server **from a terminal** — do not double-click the file in Explorer.

```powershell
C:\Phoenix\phoenix-intelligence.exe
```

> **Windows SmartScreen alert:** The first time you run the `.exe`, Windows may show a blue "Windows protected your PC" dialog. This is normal for new executables.
> Click **"More info"** then **"Run anyway"** to proceed. You only need to do this once.

Expected output:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Step 1.4 — Verify the server is running

Open a new terminal and run:

```powershell
curl http://localhost:8001/health
```

Expected response:

```json
{
  "status": "ok",
  "llm": {"configured": true, "provider": "anthropic", "model": "claude-sonnet-4-6", "warning": null},
  "mcp": {"enabled": true, "configured": true}
}
```

> **Keep this terminal open.** The server must stay running while you use the `phoenix` CLI.

---

## Part 2 — Install the Phoenix CLI

The `phoenix` CLI is the tool you use day-to-day. Install it once per machine.

### Step 2.1 — Create a virtual environment (recommended)

```powershell
python -m venv phoenix-venv
phoenix-venv\Scripts\activate
```

> **Every new terminal session:** The virtual environment is only active in the terminal where you activated it. If you close the terminal and open a new one, you must re-activate before using `phoenix`:
> ```powershell
> phoenix-venv\Scripts\activate
> ```
> You will see `(phoenix-venv)` at the start of your prompt when it is active.

### Step 2.2 — Install from the provided wheel files

> `phoenix-core` is **not** on PyPI. Install from the `.whl` files you received.
> Run these commands from the folder where you saved the three files.

```powershell
# Install shared models first (phoenix-core depends on it)
pip install phoenix_shared-0.1.0-py3-none-any.whl

# Then install the CLI
pip install phoenix_core-0.1.0-py3-none-any.whl
```

### Step 2.3 — Install Playwright browser

`phoenix-core` includes `pytest-playwright` as a dependency — it is installed automatically in the previous step. Now install the Chromium browser it uses:

```powershell
playwright install chromium
```

### Step 2.4 — Verify the CLI

```powershell
phoenix --version
phoenix --help
```

---

## Part 3 — Set Up a Project

Each application you want to test gets its own Phoenix project folder.

### Step 3.1 — Create the project

```powershell
mkdir my-project
cd my-project
phoenix init --base-url "https://your-app.com"
```

This creates the full project structure:

```
my-project/
├── .phoenixrc              ← project config (edit this first)
├── .env                    ← environment variables template
├── pyproject.toml          ← pytest configuration
├── Makefile                ← shortcut commands
├── conftest.py             ← Playwright fixtures
├── user_stories/
│   └── login.txt           ← starter user story (edit this)
├── fixtures/
│   ├── auth.py
│   └── browser.py
├── config/
│   ├── settings.yaml
│   └── environments/       ← qa.yaml / staging.yaml / prod.yaml
├── tests/                  ← generated test files (auto-created)
├── test_data/              ← generated test data (auto-created)
├── locators/               ← generated locator files (auto-created)
├── manual_tests/           ← generated manual test specs (auto-created)
├── reports/
└── logs/
```

### Step 3.2 — Configure the project

Open `.phoenixrc` and verify the intelligence server URL:

```toml
[project]
name             = "my-project"
base_url         = "https://your-app.com"
default_browser  = "chromium"

[intelligence]
base_url    = "http://localhost:8001/api/v1"   ← must match where the server is running
timeout     = 300
retry_count = 3

[llm]
provider = "anthropic"
model    = "claude-sonnet-4-6"
```

### Step 3.3 — Set environment variables

Copy `.env` to `.env.local` and fill in your real values:

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

> **Never commit `.env.local` to version control.** It is already in `.gitignore`.

Load the variables in your terminal session:

```powershell
Get-Content .env.local | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
```

> **Every new terminal session:** Environment variables loaded this way only last for the current terminal window. Each time you open a new terminal to work on your project, re-activate the venv and re-run the snippet above before running any `phoenix` commands.

### Step 3.4 — Check everything is connected

```powershell
phoenix doctor
```

This checks: API key, intelligence server, Playwright, and pytest plugins. Fix any issues flagged before continuing.

Expected output when everything is working:

```
  Phoenix Doctor
  ──────────────────────────────────────
  API key          OK
  Intelligence     OK  http://localhost:8001/api/v1
  Playwright       OK  chromium
  pytest plugins   OK
  ──────────────────────────────────────
  All checks passed. You're ready to go.
```

If any line shows `FAIL` or `UNREACHABLE`, see the Troubleshooting section at the end of this guide.

---

## Session Checklist

Every time you open a new terminal to work with Phoenix, run these three steps before anything else:

```powershell
# 1. Activate the virtual environment (terminal 1 — your working terminal)
phoenix-venv\Scripts\activate

# 2. Load your project credentials
Get-Content .env.local | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}

# 3. Confirm the intelligence server is still running (terminal 2 — server terminal)
#    If it stopped, restart it: C:\Phoenix\phoenix-intelligence.exe
curl http://localhost:8001/health
```

You only need the server terminal once — leave it open all day.

---

## Part 4 — Daily Workflow

### Step 4.1 — Write a user story

Edit `user_stories/login.txt` (or create a new file for each feature):

```
User Story: Login
Application URL: https://your-app.com

As a registered user
I want to log in to the application
So that I can access my account

Acceptance Criteria:
- Navigate to https://your-app.com/login and log in with Username admin and Password secret
- Verify the dashboard page is shown after login
- When I enter an invalid password, I should see an error message
- When I leave the username empty and click Login, I should see a validation error
```

**Tips for writing good user stories:**
- Start with `Navigate to <url> and log in with Username X and Password Y` as the first criterion
- Use plain English — no technical terms needed
- One acceptance criterion per test scenario
- Include both happy-path and error scenarios

### Step 4.2 — Generate manual test cases

```powershell
phoenix generate --story-file user_stories/login.txt --url "https://your-app.com"
```

Phoenix reads your user story and generates:
- `manual_tests/login.md` — structured test cases in Markdown (review this)
- `test_data/login.json` — realistic test data with edge cases

**Open `manual_tests/login.md` and review it.** This is the most important step.
- Add any missing steps
- Fix expected results
- Adjust test data if needed

This is the only manual step in the workflow.

### Step 4.3 — Generate automation scripts

```powershell
phoenix automate --url "https://your-app.com"
```

Phoenix reads the reviewed manual tests and generates:
- `tests/login/test_login.py` — one pytest + Playwright function per test case
- `locators/login.json` — stable element locators for the login module

> If Node.js ≥ 18 is installed, Phoenix will also open a headless browser to inspect the live page and generate more accurate locators.

### Step 4.4 — Run the tests

```powershell
# Run all tests
phoenix run

# Run only smoke tests (fast, critical-path)
phoenix run --marker smoke

# Run only a specific module
phoenix run --module login

# Run in a different browser
phoenix run --browser firefox

# Re-run only the last failures
phoenix run --failed-only
```

Or use the Makefile shortcuts:

```powershell
make smoke       # @pytest.mark.smoke tests
make regression  # @pytest.mark.regression tests
make sanity      # @pytest.mark.sanity tests
```

After each run Phoenix automatically:
- Saves a JSONL log to `logs/run_<timestamp>_<run_id>.jsonl`
- Writes a full HTML report to `reports/report_<run_id>.html`
- Captures failure screenshots to `test-results/<test>-chromium/`

### Step 4.5 — Fix failures automatically

If tests fail, Phoenix can diagnose and fix them:

```powershell
phoenix fix
```

Phoenix reads the failure log, sends each failing script and its error to the intelligence server, and writes corrected scripts back to disk.

Preview what would change without writing files:

```powershell
phoenix fix --dry-run
```

After fixing, re-run the failed tests:

```powershell
phoenix run --failed-only
```

### Step 4.6 — View results

```powershell
phoenix report                         # terminal summary + generate latest HTML report
phoenix report --open                  # terminal summary + open the report in the default browser
phoenix report --run-id <id>           # report for a specific run
phoenix report --trend                 # multi-run trend report (last 20 runs)
phoenix report --trend --last 5        # trend across the last 5 runs
phoenix report --env QA                # add an environment label to the report header
phoenix report --project "My App"      # set the project name shown in the report header
phoenix report --reports-dir ./out     # write the HTML to a custom directory
phoenix logs                           # last 10 run histories
phoenix logs --run-id <id>             # per-attempt detail for a specific run
```

HTML reports are written to `reports/report_<run_id>.html`. Each report is fully self-contained — open it directly in a browser with no server required. The report includes: run summary, module breakdown, filterable test results table, failure analysis, healing insights, error-type distribution, trend charts, flakiness report, and per-attempt detail.

---

## Part 5 — Adding More Features

For each new feature or module, repeat the workflow:

```powershell
# 1. Write a user story
notepad user_stories\checkout.txt

# 2. Generate manual tests
phoenix generate --story-file user_stories/checkout.txt --url "https://your-app.com"

# 3. Review manual_tests/checkout.md — edit as needed

# 4. Generate scripts
phoenix automate --url "https://your-app.com"

# 5. Run
phoenix run --module checkout
```

---

## CLI Reference

| Command | Description |
|---|---|
| `phoenix doctor` | Check API key, server, Playwright, pytest — fix issues before starting |
| `phoenix init` | Scaffold a new project in the current directory |
| `phoenix generate` | Generate manual test cases + test data from a user story |
| `phoenix automate` | Generate Playwright scripts from reviewed manual tests |
| `phoenix run` | Run tests with self-healing retries; auto-generates HTML report |
| `phoenix fix` | Auto-fix failing scripts using their error output |
| `phoenix report` | Generate and view the HTML report for the latest (or any) run |
| `phoenix logs` | View run history |
| `phoenix locators` | Inspect locator files |

### Common flags

```powershell
phoenix generate --story-file <path>   # specify a single story file
phoenix generate --url <url>           # override the application URL
phoenix automate --url <url>           # specify URL for live page inspection
phoenix run --marker <name>            # run only tests with this pytest marker
phoenix run --module <name>            # run only one module (e.g. login)
phoenix run --browser <name>           # chromium (default), firefox, webkit
phoenix run --failed-only              # re-run last failures only
phoenix fix --dry-run                  # preview fixes without writing files
phoenix fix --run-id <id>             # fix failures from a specific run
phoenix report --run-id <id>           # report for a specific run
phoenix report --open                  # open the HTML report in the default browser
phoenix report --trend                 # multi-run trend report
phoenix report --trend --last <n>      # trend across the last N runs
phoenix report --env <label>           # environment label (e.g. QA, staging)
phoenix report --project <name>        # project name shown in the report header
phoenix report --reports-dir <path>    # write HTML to a custom output directory
```

---

## Test Markers

Generated tests are automatically tagged with pytest markers. Use them to run targeted subsets:

```powershell
pytest -m smoke        # fast, critical-path — run on every deployment
pytest -m regression   # full coverage — run nightly
pytest -m sanity       # post-deployment checks
pytest -m negative     # invalid input and error scenarios
pytest -m security     # security and authorization checks
pytest -m login        # all tests for the login module
```

---

## Configuration Reference — `.phoenixrc`

> If `phoenix init` did not create `.phoenixrc` automatically, create it from PowerShell:
> ```powershell
> New-Item .phoenixrc -ItemType File
> ```
> Then paste the content below into it using any text editor.

```toml
[project]
name            = "my-project"
base_url        = "https://your-app.com"
default_browser = "chromium"          # chromium | firefox | webkit

[intelligence]
base_url    = "http://localhost:8001/api/v1"
timeout     = 300                     # seconds to wait for LLM response
retry_count = 3

[llm]
provider = "anthropic"                # anthropic | openai | gemini | ollama
model    = "claude-sonnet-4-6"

[logging]
level = "INFO"                        # DEBUG | INFO | WARNING
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `APP_URL` | Yes | Base URL of the application under test |
| `TEST_USERNAME` | Yes | Username for the test account |
| `TEST_PASSWORD` | Yes | Password for the test account |
| `PHOENIX_BROWSER` | No | Browser override: `chromium`, `firefox`, `webkit` |
| `PHOENIX_LOG_LEVEL` | No | Log verbosity: `DEBUG`, `INFO`, `WARNING` |

---

## Troubleshooting

### `phoenix` command not found after opening a new terminal

**Symptom:** `phoenix : The term 'phoenix' is not recognized...`

Your virtual environment is not activated in this terminal. Run:

```powershell
phoenix-venv\Scripts\activate
```

You should see `(phoenix-venv)` at the start of your prompt. Then retry your command.

If you are not in the folder where you created `phoenix-venv`, use the full path:

```powershell
C:\path\to\phoenix-venv\Scripts\activate
```

---

### `pip install phoenix-core` fails — "no matching distribution found"

**Symptom:** `ERROR: Could not find a version that satisfies the requirement phoenix-core`

- `phoenix-core` is not published on PyPI — it must be installed from the `.whl` files provided to you
- Make sure you are running pip from the folder containing the `.whl` files, then run:

```powershell
pip install phoenix_shared-0.1.0-py3-none-any.whl
pip install phoenix_core-0.1.0-py3-none-any.whl
```

---

### Intelligence server won't start

**Symptom:** `phoenix-intelligence.exe` exits immediately or shows an error.

- Verify `ANTHROPIC_API_KEY` is set: `echo $env:ANTHROPIC_API_KEY`
- Check port 8001 is not already in use: `netstat -ano | findstr :8001`
- If port 8001 is taken, free it or start the server on a different port and update `.phoenixrc`

---

### `phoenix generate` / `phoenix automate` hangs or returns "connection refused"

**Symptom:** Command appears to hang, or shows `Connection refused` / `Failed to connect`.

The intelligence server is not running. It must be running in a separate terminal before you use any `phoenix` commands that call the AI.

1. Open a dedicated terminal
2. Set the API key: `$env:ANTHROPIC_API_KEY = "sk-ant-..."`
3. Start the server: `C:\Phoenix\phoenix-intelligence.exe`
4. Leave that terminal open and return to your working terminal

---

### `phoenix doctor` reports server not reachable

**Symptom:** `Intelligence server: UNREACHABLE`

- Confirm the server terminal is still running — it must stay open
- Confirm `.phoenixrc` has `base_url = "http://localhost:8001/api/v1"`
- Try: `curl http://localhost:8001/health` in a new terminal

---

### Tests fail with "APP_URL not set" or credentials are wrong

**Symptom:** Tests error with `KeyError: 'APP_URL'`, `TEST_USERNAME not set`, or login fails with correct credentials.

Your `.env.local` variables were not loaded in this terminal session. Re-run the load snippet from Step 3.3:

```powershell
Get-Content .env.local | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
```

To verify the variables are set:

```powershell
echo $env:APP_URL
echo $env:TEST_USERNAME
```

---

### `phoenix generate` returns no tests

**Symptom:** Command completes but `manual_tests/` is empty or has minimal content.

- Make sure the user story has clear acceptance criteria (at least 3 lines)
- Check the server logs in the terminal where `phoenix-intelligence.exe` is running
- Verify your API key has available quota at [console.anthropic.com](https://console.anthropic.com)

---

### Tests fail with locator errors

**Symptom:** `playwright._impl._errors.TimeoutError` or `strict mode violation`

- Run `phoenix fix` — it reads the exact error and corrects the locator automatically
- If the page requires login before the test content is visible, ensure your user story's first step is a login step
- For live page inspection accuracy, make sure Node.js ≥ 18 is installed

---

### Node.js not found warning

**Symptom:** `MCP page inspection skipped — Node.js not available`

- Tests still generate and run — locators are inferred from the manual test context instead of the live DOM
- For more accurate locators, install Node.js ≥ 18 from [nodejs.org](https://nodejs.org)

---

### Slow test generation

**Symptom:** `phoenix generate` or `phoenix automate` takes more than 60 seconds.

- This is normal — the LLM reads your story, inspects the live page, and generates complete test cases
- `phoenix automate` opens a real browser to inspect the page — add ~10 seconds
- Increase the timeout in `.phoenixrc` if you get timeout errors: `timeout = 600`

---

## Security Notes

- Your application URL, test credentials, and user stories are sent to the Anthropic API to generate tests. Do not use production credentials or sensitive data in test stories.
- Use a dedicated low-privilege test account (`TEST_USERNAME` / `TEST_PASSWORD`).
- Generated scripts read credentials from environment variables — they are never hardcoded in test files.
- `.env.local` must never be committed to version control — it is excluded by the generated `.gitignore`.

---

## Quick Reference Card

### Every session (before anything else)
```
Terminal 1 (server)    C:\Phoenix\phoenix-intelligence.exe   ← keep open all day
Terminal 2 (work)      phoenix-venv\Scripts\activate
                       [load .env.local snippet from Step 3.3]
```

### Daily workflow
```
1. Write story         user_stories/myfeature.txt
2. Generate manual     phoenix generate --story-file user_stories/myfeature.txt --url <url>
3. Review              open manual_tests/myfeature.md  ← edit this
4. Generate scripts    phoenix automate --url <url>
5. Run                 phoenix run  →  reports/report_<run_id>.html auto-generated
6. Fix failures        phoenix fix  →  phoenix run --failed-only
7. View report         phoenix report --open
```

### Useful one-liners
```
phoenix doctor                   check everything is connected
phoenix report --trend           multi-run trend report
phoenix logs                     last 10 run histories
phoenix run --marker smoke       run only smoke tests
phoenix run --failed-only        re-run last failures
```
