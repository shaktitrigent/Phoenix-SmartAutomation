# Phoenix SmartAutomation

AI-powered test automation. Provide a user story (or a Jira ticket) → Phoenix generates manual test cases → you review them → Phoenix generates runnable Playwright scripts, executes them with self-healing retries, and auto-fixes failures.

---

## How it works

```
User story file  ──OR──  Jira ticket (PROJ-123)
  + supporting docs
  + domain_knowledge/
        │
        ▼  phoenix generate
  phoenix-intelligence  ←── LLM
        │
        ▼
  manual_tests/login.md       ← review and edit this
        │
        ▼  phoenix automate  (POM mode)
  pages/login_page.py         ← Page Object class
  tests/login/test_login.py   ← thin pytest wrapper
  locators/login.json         ← stable locator bundles
        │
        ▼  phoenix run
  reports/report_<id>.html    ← HTML report
  logs/                       ← JSONL execution log
```

**Manual-First:** You always have a human-readable spec before any code is generated. The only manual step is reviewing `manual_tests/*.md`.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.11 | |
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com) |

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
python -m uvicorn api.server:app --host 0.0.0.0 --port 8001
```

Verify: `curl http://localhost:8001/health` → `{"status":"ok",...}`

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

### 4. Initialize a project

```powershell
mkdir my-project && cd my-project
phoenix init --base-url "https://your-app.com"
```

Creates:

```
my-project/
├── .phoenixrc              ← project config (TOML)
├── conftest.py             ← Playwright fixtures
├── user_stories/           ← write your stories here
├── domain_knowledge/       ← project-wide UI patterns, URLs, test data rules
├── pages/                  ← Page Object classes (POM mode)
│   └── base_page.py        ← base class for all page objects
├── tests/                  ← generated test files
├── locators/               ← stable locator bundles (JSON)
├── manual_tests/           ← human-readable test specs (Markdown)
├── reports/
│   └── screenshots/        ← failure screenshots (auto-captured)
└── logs/
```

### 5. Generate manual tests

```powershell
phoenix generate --story-file user_stories/login.txt
```

**From a Jira ticket:**
```powershell
phoenix generate --jira PROJ-123
```

Opens `manual_tests/login.md` and review it. Add missing steps, fix expected results. This is the only manual step.

### 6. Generate automation scripts

```powershell
phoenix automate
```

In POM mode (default when `layout = "pom-v1"` in `.phoenixrc`), produces:
- `pages/<module>_page.py` — Page Object class
- `tests/<module>/test_<name>.py` — thin pytest wrapper
- `locators/<module>.json` — LocatorBundle JSON

### 7. Run the tests

```powershell
phoenix run tests/<test-file>.py

# Headed mode (visible browser — useful for debugging)
phoenix run --headed tests/<test-file>.py

# Re-run only last failures
phoenix run --failed-only
```

### 8. Fix failures

```powershell
phoenix fix
phoenix run --failed-only
```

### 9. View results

```powershell
phoenix report --open
phoenix logs
phoenix locators
```

---

## CLI reference

| Command | What it does |
|---|---|
| `phoenix doctor` | Check API key, server, Playwright, plugins |
| `phoenix init` | Scaffold a new project |
| `phoenix migrate` | Add missing dirs/files to an existing project |
| `phoenix generate` | Generate manual tests from a user story or Jira ticket |
| `phoenix automate` | Generate Playwright scripts from reviewed manual tests |
| `phoenix run` | Run tests with self-healing retries |
| `phoenix fix` | Auto-fix failing scripts using error output |
| `phoenix clean` | Delete generated test scripts, reports, locators, logs |
| `phoenix logs` | View execution log history |
| `phoenix locators` | Inspect LocatorBundle JSON files |
| `phoenix report` | Generate HTML report; `--open` opens it in the browser |
| `phoenix jira health` | Check Jira connectivity and credentials |
| `phoenix jira show PROJ-123` | Preview what Phoenix would extract from a Jira issue |

### Key options

```powershell
# generate
phoenix generate --story-file <path>
phoenix generate --jira PROJ-123
phoenix generate --no-gate            # save all tests regardless of quality
phoenix generate --type both          # manual + automation in one step

# automate
phoenix automate                      # reads manual_tests/ directory
phoenix automate --manual-dir <path>  # use a different directory
phoenix automate --file <path>        # automate a single manual test file

# run
phoenix run tests/                    # all tests
phoenix run --headed                  # visible browser
phoenix run --headed --slow-mo 800    # slow down actions (debug)
phoenix run --failed-only             # re-run last failures
phoenix run --browser firefox         # chromium | firefox | webkit
```

---

## Configuration — `.phoenixrc`

```toml
[project]
name            = "my-project"
base_url        = "https://your-app.com"
default_browser = "chromium"          # chromium | firefox | webkit
layout          = "pom-v1"            # pom-v1 = Page Object Model (recommended)

[intelligence]
base_url    = "http://localhost:8001/api/v1"
timeout     = 300
retry_count = 3

[pom]
pages_dir = "./pages"

# Jira integration (optional — remove # to enable)
# [jira]
# url                       = "https://yourcompany.atlassian.net"
# project_key               = "PROJ"
# acceptance_criteria_field = "description"
# download_attachments      = true
```

---

## Domain knowledge

`domain_knowledge/` holds project-wide context injected into every generation call.

| File | What to put here |
|---|---|
| `navigation.md` | Login URL, key page paths, auth flow |
| `ui_patterns.md` | Custom dropdowns, date pickers, modals |
| `data_rules.md` | Field formats, required/optional fields, test credentials |

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
| `POST` | `/api/v1/tests/generate` | Generate manual tests from a user story |
| `POST` | `/api/v1/tests/automate` | Generate Playwright scripts from manual tests |
| `POST` | `/api/v1/tests/fix` | Fix a failing script using its error output |

---

## Project structure

```
Phoenix-SmartAutomation/
├── shared/                     # Pydantic models shared by both packages
├── phoenix-core/               # pip-installable CLI + SDK
│   └── phoenix/
│       ├── cli/                # CLI commands
│       ├── sdk/                # PhoenixClient, IntelligenceClient, PhoenixConfig
│       ├── generators/         # Script normalisation, validation, lint
│       ├── locators/           # LocatorRegistry, extractor, persist helper
│       ├── execution/          # HealingEngine, TestRunner, ExecutionLogger
│       ├── output/             # OutputManager — POM/BDD delta apply
│       ├── reporting/          # HTML report generation
│       └── templates/project/  # Jinja2 templates for new projects
│
└── phoenix-intelligence/       # AI server (FastAPI, port 8001)
    ├── api/                    # REST endpoints + Pydantic models
    ├── services/agents/        # TestGenerator, ScriptFixer, LocatorExpert
    ├── services/llm/           # LLM router (Anthropic / OpenAI / Gemini / Ollama)
    └── prompts/                # Versioned prompt Markdown files
```
