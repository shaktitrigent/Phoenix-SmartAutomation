# Phoenix SmartAutomation

AI-powered test automation. Provide a user story (or a Jira ticket) with supporting documents → Phoenix generates manual test cases → you review them → Phoenix generates runnable Playwright scripts, executes them with self-healing retries, and auto-fixes failures.

---

## How it works

```
User story file  ──OR──  Jira ticket (PROJ-123)
  + supporting docs          + attachments (PDF, DOCX, XLSX, …)
  + domain_knowledge/
        │
        ▼  phoenix generate
  phoenix-intelligence  ←── LLM
        │
        ▼
  manual_tests/login.md       ← review and edit this
  test_data/login.json        ← realistic test data (fields extracted from steps)
        │
        ▼  phoenix automate
  tests/login/test_login.py   ← Playwright pytest scripts
  locators/login.json         ← stable locator bundles
        │
        ▼  phoenix run / make smoke
  reports/                    ← HTML report
  reports/screenshots/        ← failure screenshots (auto-captured)
  logs/                       ← JSONL execution log
```

**Manual-First:** generate reads your story → writes manual tests → you edit → automate turns them into code. You always have a human-readable spec before any code is generated.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.11 | |
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com) |
| Node.js ≥ 18 | Only needed for live MCP page inspection |

---

## Installation

```powershell
git clone <repo-url>
cd Phoenix-SmartAutomation

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -e shared/
pip install -e phoenix-core/
pip install -e phoenix-intelligence/

playwright install chromium
```

Optional dependency for PDF / DOCX / XLSX supporting document extraction:

```powershell
pip install pypdf python-docx openpyxl
```

---

## Quick start

### 1. Start the intelligence server

Open a dedicated terminal and leave it running.

```powershell
cd phoenix-intelligence
.\start_server.ps1             # Windows
# python api/server.py        # macOS / Linux
```

Verify: `curl http://localhost:8001/health` should return `{"status":"ok",...}`.

### 2. Set credentials

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:APP_URL            = "https://your-app.com"
$env:TEST_USERNAME      = "your_username"
$env:TEST_PASSWORD      = "your_password"
```

Credentials are **never hardcoded** — always read from environment variables.

### 3. Check setup

```powershell
phoenix doctor
```

Checks the API key, intelligence server, Playwright, and pytest plugins. Fix any issues before continuing.

### 4. Initialize a project

```powershell
mkdir my-project && cd my-project
phoenix init --base-url "https://your-app.com"
```

Creates:

```
my-project/
├── .phoenixrc              ← project config (TOML)
├── .env                    ← env vars template (fill in and use .env.local)
├── pyproject.toml          ← pytest markers (smoke, regression, sanity)
├── Makefile                ← make smoke / make regression / make report
├── conftest.py             ← Playwright fixtures, screenshot-on-failure hook
├── user_stories/
│   ├── login.txt           ← starter user story (edit this)
│   └── SUPPORTING_DOCS.md  ← explains the supporting-docs convention
├── domain_knowledge/       ← project-wide UI patterns, URLs, test credentials
│   ├── README.md
│   ├── navigation.md
│   ├── ui_patterns.md
│   └── data_rules.md
├── fixtures/
│   ├── auth.py             ← login fixture using env vars
│   └── browser.py          ← mobile context fixture
├── config/
│   ├── settings.yaml
│   └── environments/       ← qa.yaml / staging.yaml / prod.yaml
├── tests/login/            ← generated test files live here
├── test_data/              ← generated realistic test data (JSON)
├── locators/               ← stable locator bundles (JSON)
├── manual_tests/           ← human-readable test specs (Markdown)
├── reports/
│   └── screenshots/        ← failure screenshots (auto-captured)
└── logs/
```

### 5. Generate manual tests

**From a user story file:**

```powershell
phoenix generate --story-file user_stories/login.txt --url "https://your-app.com"
```

**From a Jira ticket** (fetches story, criteria and attachments automatically):

```powershell
phoenix generate --jira PROJ-123 --url "https://your-app.com"
```

**With explicit supporting documents** (wireframe PDF, specs spreadsheet, etc.):

```powershell
phoenix generate --story-file user_stories/checkout.txt \
                 --docs user_stories/checkout/ \
                 --url "https://your-app.com"
```

Supporting docs are also **auto-discovered**: if `user_stories/checkout.txt` exists, Phoenix automatically reads `user_stories/checkout/` (same name, no extension) for any PDFs, DOCX, XLSX, CSV, JSON files.

Produces:
- `manual_tests/login.md` — consolidated Markdown spec with all test cases
- `test_data/login.json` — realistic test data derived from the actual test steps

**Open `manual_tests/login.md` and review it.** Add missing steps, fix expected results. This is the only manual step.

### 6. Generate automation scripts

```powershell
phoenix automate --url "https://your-app.com"
```

Produces:
- `tests/login/test_login.py` — one pytest + Playwright function per manual test case
- `locators/login.json` — LocatorBundle JSON for the login module

### 7. Run the tests

```powershell
# Run everything
phoenix run

# Or use Makefile shortcuts
make smoke       # only @pytest.mark.smoke tests
make regression  # only @pytest.mark.regression tests

# Specific browser
phoenix run --browser firefox

# Re-run only last failures
phoenix run --failed-only
```

### 8. Fix failures

```powershell
phoenix fix
```

Reads the last run log, sends each failing script + its exact error to the intelligence server, and writes the corrected script back.

```powershell
phoenix fix --dry-run       # preview only, no files written
phoenix fix --run-id <id>   # fix a specific run
```

After fixing:
```powershell
phoenix run --failed-only
```

### 9. View results

```powershell
phoenix report                      # terminal summary + generate HTML report
phoenix report --open               # generate and open in the default browser
phoenix report --run-id <id>        # report for a specific run
phoenix report --trend              # multi-run trend report (last 20 runs)
phoenix report --trend --last 5     # trend across the last 5 runs
phoenix report --env QA             # add environment label to the report header
phoenix logs                        # last 10 runs
phoenix logs --run-id <id>          # per-attempt detail
phoenix locators                    # inspect locator bundles
```

HTML reports are written to `reports/report_<run_id>.html` automatically after every `phoenix run`. Failure screenshots land in `reports/screenshots/`. Each report is self-contained — open directly in a browser, no server required.

---

## CLI reference

| Command | What it does |
|---|---|
| `phoenix doctor` | Check API key, server, Playwright, plugins |
| `phoenix init` | Scaffold a new project |
| `phoenix migrate` | Add missing dirs/files to an existing project |
| `phoenix generate` | Generate manual tests + test data from a user story, Jira ticket, or supporting docs |
| `phoenix automate` | Generate Playwright scripts from reviewed manual tests |
| `phoenix run` | Run tests with self-healing retries |
| `phoenix fix` | Auto-fix failing scripts using error output |
| `phoenix clean` | Delete all generated artifacts (scripts, reports, locators, logs) |
| `phoenix logs` | View execution log history |
| `phoenix locators` | Inspect LocatorBundle JSON files |
| `phoenix report` | Generate HTML report; `--open` opens it in the browser |
| `phoenix jira health` | Check Jira connectivity and credentials |
| `phoenix jira show PROJ-123` | Preview what Phoenix would extract from a Jira issue |

### Key `generate` options

```powershell
phoenix generate --story-file <path>      # story from a file
phoenix generate --story "As a user..."   # story inline
phoenix generate --jira PROJ-123          # story + attachments from Jira
phoenix generate --docs <path>            # explicit supporting docs file or folder
phoenix generate --type both              # manual + automation in one step
phoenix generate --url <url>              # application URL
phoenix generate --no-gate                # save all tests regardless of quality (iterating)
phoenix generate --strict-gate            # enforce CI-grade thresholds (≥ 2 steps, ≥ 10-char desc)
```

### Key `automate` options

```powershell
phoenix automate --url <url>              # application URL
phoenix automate --file <path>            # automate a single manual test file
phoenix automate --test-case "name"       # automate one test case by name substring
phoenix automate --clean                  # delete existing scripts before generating
```

Accepted filename patterns in `manual_tests/`: `manual_test_*.md`, `test_*.md`, `*_manual.md`, `TC-*.md`, `*_test.md`.
Steps can be a Phoenix pipe table **or** a plain numbered/bulleted list.

### Key `run` options

```powershell
phoenix run --browser firefox             # chromium (default) | firefox | webkit
phoenix run --failed-only                 # re-run only last failures
phoenix run --headed                      # open a visible browser window (debug)
phoenix run --headed --slow-mo 800        # slow down each action by 800ms
phoenix run --max-attempts 5              # increase healing retries
```

### `phoenix clean`

```powershell
phoenix clean                             # delete all generated artifacts
phoenix clean --dry-run                   # preview what would be deleted
```

---

## Domain knowledge

`domain_knowledge/` holds project-wide context about how the application works. It is injected into every test generation call so the LLM can make better locator and interaction decisions.

| File | What to put here |
|---|---|
| `navigation.md` | Login URL, key page paths, auth flow |
| `ui_patterns.md` | Custom dropdowns, date pickers, modals — non-standard interactions |
| `data_rules.md` | Field formats, required/optional fields, test credentials |

This is **different from supporting documents** — domain knowledge covers the whole project; supporting docs are specific to one user story.

---

## Supporting documents

Attach wireframes, specifications, schemas, and requirement docs to a specific user story. Phoenix extracts text from them and includes it in the LLM prompt.

**Auto-discovery convention:**

```
user_stories/
  checkout.txt          ← the user story
  checkout/             ← supporting docs for this story
    wireframe.pdf
    field_rules.xlsx
    api_schema.json
```

**Supported formats:** `.txt` `.md` `.csv` `.json` `.xml` `.yaml` `.html` · `.pdf` (needs `pypdf`) · `.docx` (needs `python-docx`) · `.xlsx` `.xls` (needs `openpyxl`)

---

## Jira integration

One-time setup — configure once, then use `--jira PROJ-123` in any `generate` command.

### Setup

```powershell
# 1. Set secrets as environment variables (never in config files)
$env:JIRA_URL        = "https://yourcompany.atlassian.net"
$env:JIRA_EMAIL      = "you@company.com"
$env:JIRA_API_TOKEN  = "your-api-token"    # from id.atlassian.com

# 2. Uncomment [jira] section in .phoenixrc and set non-sensitive values
```

`.phoenixrc` Jira section:

```toml
[jira]
url                       = "https://yourcompany.atlassian.net"
project_key               = "PROJ"
acceptance_criteria_field = "description"   # or "customfield_XXXXX"
download_attachments      = true
```

### Verify

```powershell
phoenix jira health          # connectivity + credentials check
phoenix jira show PROJ-123   # preview without generating
```

### Use

```powershell
phoenix generate --jira PROJ-123 --url "https://your-app.com"
```

Phoenix fetches the issue summary, description, acceptance criteria, and attachments. Attachments are passed through the same supporting-documents pipeline. The token is **never** stored in `.phoenixrc`.

---

## Configuration — `.phoenixrc`

```toml
[project]
name            = "my-project"
base_url        = "https://your-app.com"
default_browser = "chromium"          # chromium | firefox | webkit

[intelligence]
base_url    = "http://localhost:8001/api/v1"
timeout     = 300
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

---

## Test markers

Generated tests use pytest markers — run subsets without separate directories.

```powershell
pytest -m smoke       # fast, critical-path tests
pytest -m regression  # full suite
pytest -m sanity      # post-deployment checks
pytest -m login       # all login-module tests
```

---

## LLM providers

| Provider | Environment variable |
|---|---|
| Anthropic (default) | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY`, `PHOENIX_LLM_PROVIDER=openai` |
| Google Gemini | `GOOGLE_API_KEY`, `PHOENIX_LLM_PROVIDER=gemini` |
| Ollama (local) | `PHOENIX_LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434` |

---

## Intelligence API

Interactive docs at `http://localhost:8001/docs`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Server and LLM status |
| `POST` | `/api/v1/tests/generate` | Generate manual + automation tests from a user story (supports `supporting_documents`, `domain_knowledge`) |
| `POST` | `/api/v1/tests/automate` | Generate Playwright scripts from manual tests |
| `POST` | `/api/v1/tests/fix` | Fix a failing script using its error output |
| `POST` | `/api/v1/locators/discover` | Discover stable locators for page elements |
| `POST` | `/api/v1/failures/analyze` | Analyze a failure and suggest a fix |

---

## Project structure

```
Phoenix-SmartAutomation/
├── shared/                     # Pydantic models shared by both packages
├── phoenix-core/               # pip-installable CLI + SDK
│   └── phoenix/
│       ├── cli/                # All CLI commands (including `jira` group)
│       ├── sdk/                # PhoenixClient, IntelligenceClient, PhoenixConfig
│       ├── generators/
│       │   ├── writer.py       # ModuleAwareWriter (one file per module)
│       │   ├── automation.py   # Normalises + validates generated scripts (CleanCodeGate)
│       │   ├── clean_code.py   # Gate rules: WARNING, UNGROUNDABLE, business-text URL regex
│       │   └── manual.py       # ManualTestQualityGate + writer
│       ├── test_data/
│       │   ├── engine.py       # TestDataEngine — step-based field extraction (generic)
│       │   ├── field_detector.py
│       │   └── generators.py   # stdlib-only data generators
│       ├── documents/
│       │   └── loader.py       # DocumentLoader — extracts text from PDF, DOCX, XLSX, CSV, JSON, …
│       ├── integrations/
│       │   └── jira/
│       │       ├── config.py   # JiraConfig (non-sensitive in .phoenixrc, secrets via env)
│       │       ├── client.py   # JiraClient — REST API, Cloud + Server/DC auto-detect
│       │       └── adf.py      # Atlassian Document Format → plain text converter
│       ├── execution/          # HealingEngine, TestRunner, ExecutionLogger
│       ├── locators/           # LocatorRegistry
│       ├── reporting/          # DataLoader, RunAggregator, TrendAggregator, render_run_report()
│       ├── scaffold.py         # phoenix init scaffold logic
│       └── templates/project/  # Jinja2 templates for new projects
│
└── phoenix-intelligence/       # AI server (FastAPI, port 8001)
    ├── api/                    # REST endpoints + Pydantic models (SupportingDocument added)
    ├── services/agents/        # TestGenerator, ScriptFixer, LocatorExpert, FailureAnalyzer
    ├── services/llm/           # LLM router (Anthropic / OpenAI / Gemini / Ollama)
    ├── services/knowledge/     # Playwright rules, patterns, domain knowledge
    └── prompts/                # Versioned prompt Markdown files
```

---

## Build & Package

> **When to use this:** Package `phoenix-intelligence` into a standalone executable when you want to distribute the intelligence server to end users **without sharing source code**. The resulting `.exe` bundles all three packages and all dependencies — no Python installation required on the target machine.

### Prerequisites

```powershell
python --version
pip --version
```

### Step 1 — Install build dependencies

```powershell
pip install -e shared/
pip install -e phoenix-core/
pip install -e phoenix-intelligence/
pip install pyinstaller "uvicorn[standard]"
```

Or use the build script shortcut:

```powershell
.\build.ps1 install
```

### Step 2 — Build all three artifacts

```powershell
pip install build
.\build.ps1 dist
```

This cleans old artifacts, builds both wheels and the exe, then prints a summary of everything in `dist\`.

| Artifact | Clean | Build |
|---|---|---|
| All three | `.\build.ps1 clean` | `.\build.ps1 dist` |
| `phoenix-intelligence.exe` only | `.\build.ps1 clean` | `.\build.ps1 package` |
| Wheels only | `.\build.ps1 clean` | `python -m build shared\ --outdir dist\` then `python -m build phoenix-core\ --outdir dist\` |

### Output

```
dist\
├── phoenix_shared-0.1.3-py3-none-any.whl    ← install first
├── phoenix_core-0.1.3-py3-none-any.whl      ← install second
└── phoenix-intelligence.exe                  ← run the server
```

> If you bump version numbers in `pyproject.toml` files, update the install commands in `END_USER_GUIDE.md` to match.

### Step 3 — Distribute to end users

Hand the three files in `dist\` to end users and point them to `docs/END_USER_GUIDE.md`.
