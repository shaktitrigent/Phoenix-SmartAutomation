# Phoenix SmartAutomation

AI-powered test automation. Write a user story → Phoenix generates manual test cases → you review them → Phoenix generates runnable Playwright scripts, executes them with self-healing retries, and auto-fixes failures.

---

## How it works

```
user_stories/login.txt
        │
        ▼  phoenix generate
  phoenix-intelligence  ←── Claude LLM
        │
        ▼
  manual_tests/login.md       ← review and edit this
  test_data/login.json        ← generated realistic test data
        │
        ▼  phoenix automate
  tests/login/test_login.py   ← Playwright pytest scripts
  locators/login.json         ← stable locator bundles
        │
        ▼  phoenix run / make smoke
  reports/                    ← HTML report
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
├── conftest.py             ← Playwright fixtures + module-aware test data
├── user_stories/
│   └── login.txt           ← starter user story (edit this)
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
└── logs/
```

### 5. Generate manual tests

```powershell
phoenix generate --story-file user_stories/login.txt --url "https://your-app.com"
```

Produces:
- `manual_tests/login.md` — consolidated Markdown spec with all test cases for the module
- `test_data/login.json` — realistic test data (3 scenarios + edge cases per field)

**Open `manual_tests/login.md` and review it.** Add missing steps, fix expected results, adjust test data. This is the only manual step.

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

HTML reports are written to `reports/report_<run_id>.html` automatically after every `phoenix run`. Each report is self-contained — open directly in a browser, no server required.

---

## CLI reference

| Command | What it does |
|---|---|
| `phoenix doctor` | Check API key, server, Playwright, plugins |
| `phoenix init` | Scaffold a new project |
| `phoenix migrate` | Add missing dirs/files to an existing project |
| `phoenix generate` | Generate manual tests + test data from a user story |
| `phoenix automate` | Generate Playwright scripts from reviewed manual tests |
| `phoenix run` | Run tests with self-healing retries |
| `phoenix fix` | Auto-fix failing scripts using error output |
| `phoenix logs` | View execution log history |
| `phoenix locators` | Inspect LocatorBundle JSON files |
| `phoenix report` | Generate HTML report for the latest (or any) run; `--open` opens it in the browser |

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
| `POST` | `/api/v1/tests/generate` | Generate manual test cases from a user story |
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
│       ├── cli/                # All CLI commands
│       ├── sdk/                # PhoenixClient, config
│       ├── generators/
│       │   ├── writer.py       # ModuleAwareWriter (one file per module)
│       │   ├── automation.py   # Normalises generated scripts
│       │   └── manual.py       # Manual test quality gate + writer
│       ├── test_data/
│       │   ├── engine.py       # TestDataEngine
│       │   ├── field_detector.py
│       │   └── generators.py   # stdlib-only data generators
│       ├── execution/          # HealingEngine (self-healing retries + screenshot capture), runner, logger
│       ├── locators/           # LocatorRegistry
│       ├── reporting/          # DataLoader, RunAggregator, TrendAggregator, render_run_report()
│       ├── scaffold.py         # phoenix init scaffold logic
│       └── templates/project/  # Jinja2 templates for new projects
│
└── phoenix-intelligence/       # AI server (FastAPI, port 8001)
    ├── api/                    # REST endpoints
    ├── services/agents/        # TestGenerator, ScriptFixer, LocatorExpert, FailureAnalyzer
    ├── services/llm/           # LLM router (Anthropic / OpenAI / Gemini / Ollama)
    ├── services/knowledge/     # Playwright rules, patterns, domain knowledge
    └── prompts/                # Versioned prompt Markdown files
```

---

## Build & Package

> **When to use this:** Package `phoenix-intelligence` into a standalone executable when you want to distribute the intelligence server to end users **without sharing source code**. The resulting `.exe` bundles all three packages (`shared`, `phoenix-core`, `phoenix-intelligence`) and all dependencies — no Python installation required on the target machine.

### Prerequisites

```powershell
# Python ≥ 3.11 and pip must be available
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

Install the build tool once:

```powershell
pip install build
```

**Single command — clean + build all three artifacts into `dist\`:**

```powershell
.\build.ps1 dist
```

This cleans old artifacts, builds both wheels and the exe, then prints a summary of everything in `dist\`.

If you need to build individual artifacts:

| Artifact | Clean | Build |
|---|---|---|
| All three | `.\build.ps1 clean` | `.\build.ps1 dist` |
| `phoenix-intelligence.exe` only | `.\build.ps1 clean` | `.\build.ps1 package` |
| Wheels only (`shared` + `phoenix-core`) | `.\build.ps1 clean` | `python -m build shared\ --outdir dist\` then `python -m build phoenix-core\ --outdir dist\` |

### Output location

```
Phoenix-SmartAutomation\
└── dist\
    ├── phoenix_shared-0.1.0-py3-none-any.whl    ← distribute to end user (install first)
    ├── phoenix_core-0.1.0-py3-none-any.whl      ← distribute to end user (install second)
    └── phoenix-intelligence.exe                  ← distribute to end user (run the server)
```

> If you bump version numbers in `shared/pyproject.toml` or `phoenix-core/pyproject.toml`, the wheel filenames will reflect the new version. Update the install commands in `END_USER_GUIDE.md` to match.

### Step 3 — Distribute to end users

Hand the three files in `dist\` to end users and point them to `docs/END_USER_GUIDE.md` for setup instructions.
