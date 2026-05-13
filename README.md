# Phoenix Smart Automation

Enterprise-grade AI-powered QA automation platform. Describe a user story — Phoenix generates
consolidated manual test cases that you review and edit, then generates one runnable Playwright
script per manual test, executes them with self-healing retries, and automatically fixes failing
scripts using the exact error output.

---

## Quick Reference

| Command | What it does |
|---|---|
| `phoenix doctor` | Check LLM key, intelligence server, database, pytest plugins |
| `phoenix init` | Scaffold a new project (`manual_tests/`, `test_results/`, `logs/`, etc.) |
| `phoenix migrate` | Add missing dirs/files to an existing project (non-destructive) |
| `phoenix generate` | Generate manual test `.md` files from a user story |
| `phoenix automate` | Read `manual_tests/*.md`, generate 1 automation script per test |
| `phoenix run` | Run all automation scripts with self-healing retries |
| `phoenix fix` | Auto-fix failing scripts using error output from the last run |
| `phoenix logs` | View execution log history |
| `phoenix locators` | Inspect extracted LocatorBundle JSON files |
| `phoenix report` | Show execution report summary |

```powershell
# Check setup
phoenix doctor

# One-time project setup
phoenix init --base-url "https://app.com" --browser chromium

# Generate manual tests from a story
phoenix generate --story-file user_story.txt --url "https://app.com"
phoenix generate --story-file user_story.txt --url "https://app.com" --clean   # wipe manual_tests/ first
#   → edit manual_tests/*.md as needed

# Generate automation scripts (1 per manual test)
phoenix automate --url "https://app.com"
phoenix automate --url "https://app.com" --clean                               # wipe test_results/ first

# Run tests
phoenix run
phoenix run --browser firefox
phoenix run --failed-only                                                       # re-run last failures only
phoenix run --heal --max-attempts 3

# Fix failures
phoenix fix
phoenix fix --dry-run                                                           # preview without writing
phoenix fix --url "https://app.com"

# Inspect logs
phoenix logs                        # last 10 runs
phoenix logs --limit 20
phoenix logs --run-id <id>          # all attempts for a specific run
phoenix logs --output json

# Inspect locators
phoenix locators
phoenix locators --page login
phoenix locators --output json

# View report
phoenix report
phoenix report --execution-id <id>
```

---

## How It Works

```
Your user story
      │
      ▼  phoenix generate
phoenix-intelligence  ←── Anthropic Claude (LLM)
  (FastAPI, port 8001)  ←── Playwright rules, test patterns, best practices
      │
      ▼
  manual_tests/         ←── 3–5 Markdown test cases  ← YOU REVIEW / EDIT HERE
      │
      ▼  phoenix automate
phoenix-intelligence  ←── LLM generates 1 script per manual test
      │
      ▼
  test_results/         ←── 1 pytest + Playwright script per manual test (1:1 mapping)
  locators/             ←── LocatorBundle JSON files (per page)
  reports/              ←── HTML execution reports
  logs/                 ←── JSONL execution logs (per run)
```

**Manual-First pipeline:** `phoenix generate` produces manual test cases only. You review
and edit them in `manual_tests/`. Then `phoenix automate` reads those files and generates
exactly one automation script per manual test — guaranteeing 1:1 traceability and that
login is always step 1.

---

## Project Structure

```
Phoenix-SmartAutomation/
├── shared/                    # Pydantic contracts shared by both packages
├── phoenix-core/              # pip-installable SDK + CLI (no AI/LLM deps)
│   └── phoenix/
│       ├── cli/               # Commands: init, migrate, generate, automate, run, fix, logs, locators, report
│       ├── sdk/               # PhoenixClient, IntelligenceClient, config
│       ├── generators/        # Writes manual .md and automation .py files
│       ├── execution/         # HealingEngine, ExecutionLogger, runner
│       ├── locators/          # LocatorRegistry (per-page LocatorBundle JSON)
│       └── storage/           # SQLAlchemy models + SQLite database
│
├── phoenix-intelligence/      # Hosted AI server (FastAPI, port 8001)
│   ├── api/                   # REST endpoints
│   ├── services/agents/       # TestGenerator, ScriptFixer, LocatorExpert, FailureAnalyzer
│   ├── services/llm/          # LLM Router (Anthropic / OpenAI / Gemini / Ollama)
│   ├── services/knowledge/    # Playwright rules, test patterns, best practices
│   ├── services/mcp/          # Playwright MCP client (live page inspection)
│   └── prompts/               # Versioned prompt files (Markdown, per agent)
│
├── examples/sample_project/   # Ready-to-run Playwright test examples
├── infra/                     # Docker, docker-compose, .env.example
├── docs/                      # Architecture, MCP guides, ADRs
└── contracts/openapi.yaml     # API specification
```

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | ≥ 3.9 | |
| Node.js | ≥ 18 | Required for Playwright MCP |
| ANTHROPIC_API_KEY | — | Get one at console.anthropic.com |

---

## Setup

### 1. Clone and create a virtual environment

```powershell
git clone <repo-url>
cd Phoenix-SmartAutomation

python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 2. Install packages

```powershell
pip install -e shared/
pip install -e phoenix-core/
pip install -e phoenix-intelligence/
```

### 3. Install Playwright browsers

```powershell
playwright install chromium
```

### 4. Set your API key

**Windows PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

**Linux / macOS:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

---

## Full Workflow — Step by Step

### Step 1: Start the Intelligence Server

Start once in a dedicated terminal and leave it running.

**Windows PowerShell:**
```powershell
cd phoenix-intelligence
.\start_server.ps1
```

**Linux / macOS:**
```bash
cd phoenix-intelligence
python api/server.py
```

Verify it is running:
```powershell
# Should return {"status":"ok",...}
curl http://localhost:8001/health
```

---

### Step 2: Check everything is configured

```powershell
phoenix doctor
```

Checks LLM API key, intelligence server connectivity, database access, and pytest plugins.
Fix any reported issues before proceeding.

---

### Step 3: Initialize your project

```powershell
cd my-project
phoenix init
```

Creates `.phoenixrc`, `manual_tests/`, `test_results/`, `reports/`, `logs/`, `locators/`.

```powershell
# With options
phoenix init --base-url "https://your-app.com" --browser chromium
```

---

### Step 4: Generate manual test cases

```powershell
# From a user story file (recommended)
phoenix generate --story-file user_story.txt --url "https://your-app.com/login"

# From a string
phoenix generate --story "As a user I want to log in" --url "https://your-app.com/login"

# Regenerate fresh (deletes previous output first)
phoenix generate --story-file user_story.txt --url "https://your-app.com" --clean
```

**What this produces:**
- `manual_tests/manual_test_*.md` — 3–5 consolidated Markdown test cases (one workflow per test)

**Options:**
```powershell
--risk smoke         # Focus on smoke / regression / edge tests
--clean              # Delete previous manual_tests/ output before generating
```

---

### Step 4b: Review and edit manual tests

Open each `manual_tests/manual_test_*.md` file and:

- Confirm the test steps are in the right order
- Add missing steps or expected results
- Adjust test data (usernames, passwords, URLs)
- Remove steps that are not relevant

This is the only manual step in the pipeline. The automation scripts will be generated
directly from what you save here.

---

### Step 5: Generate automation scripts

```powershell
# Generate one script per manual test (reads manual_tests/ automatically)
phoenix automate --url "https://your-app.com"

# Regenerate fresh (deletes previous test_results/ scripts first)
phoenix automate --url "https://your-app.com" --clean

# Specify a different manual tests directory
phoenix automate --manual-dir path/to/manual_tests --url "https://your-app.com"
```

**What this produces:**
- `test_results/test_*.py` — one pytest + Playwright script per manual test (1:1 mapping)
- `locators/<page>.json` — LocatorBundle files extracted from each generated script

**1:1 guarantee:** 5 manual tests → 5 automation scripts. The test name, steps, and expected
results all trace directly back to the originating manual test file.

---

### Step 6: Run the tests

```powershell
# Run all generated tests from the project directory
phoenix run

# Run with a specific browser
phoenix run --browser chromium
phoenix run --browser firefox
phoenix run --browser webkit

# Run with self-healing retries enabled (default)
phoenix run --heal --max-attempts 3

# Re-run only tests that failed in the previous run
phoenix run --failed-only
```

Results are printed to the terminal and written to `logs/run_<timestamp>.jsonl`.

---

### Step 7: Fix failing tests

After a run with failures, use `phoenix fix` to automatically update the broken scripts:

```powershell
phoenix fix
```

**What this does for each failing test:**
1. Reads the exact error message and error type from the run log
2. Sends the broken script + error to the intelligence server
3. The LLM (or heuristic rules if no LLM) rewrites only the broken part
4. Saves the fixed script back to `test_results/` — original backed up as `.py.bak`

**Options:**
```powershell
# Preview what would be fixed without writing files
phoenix fix --dry-run

# Fix failures from a specific run
phoenix fix --run-id <run-id>

# Specify a different logs or test directory
phoenix fix --logs-dir logs/ --test-dir test_results/

# Pass application URL for better LLM context
phoenix fix --url "https://your-app.com"
```

**Heuristic fixes applied when no LLM is configured:**

| Error type | Fix applied |
|---|---|
| `locator_not_found` | `get_by_label` → `get_by_placeholder` |
| `timeout` | All timeout values doubled (max 120s) |
| `assertion_failure` | `to_have_text` → `to_contain_text` |
| `stale_element` | Adds `wait_for_selector` before the action |
| `navigation_failure` | Relaxes URL glob + doubles navigation timeout |

---

### Step 8: Re-run the fixed tests

```powershell
phoenix run --failed-only
```

Repeat Steps 7–8 until all tests pass.

---

### Step 9: View the report

```powershell
phoenix report
phoenix report --execution-id <id>
```

---

## Typical Day-to-Day Commands

```powershell
# 1. Generate manual tests from a story file
phoenix generate --story-file user_story.txt --url "https://app.com" --clean

# 2. Review and edit manual_tests/*.md in your editor

# 3. Generate automation scripts (1 per manual test)
phoenix automate --url "https://app.com"

# 4. Run all tests
phoenix run

# 5. Fix any failures automatically
phoenix fix

# 6. Re-run only the fixed ones
phoenix run --failed-only

# Check the execution log history
phoenix logs

# View a specific run's failures in detail
phoenix logs --run-id <run-id>

# Inspect extracted locators
phoenix locators
```

---

## All CLI Commands

### `phoenix doctor`
Check configuration and connectivity.
```powershell
phoenix doctor
```

### `phoenix init`
Initialise a new project with canonical layout.
```powershell
phoenix init
phoenix init --base-url "https://app.com" --browser chromium --force
phoenix init --non-interactive --dry-run
```

### `phoenix migrate`
Add missing directories/files to an existing project without overwriting anything.
```powershell
phoenix migrate
phoenix migrate --dir /path/to/project --dry-run
```

### `phoenix generate`
Generate manual test cases from a user story. Writes `manual_tests/manual_test_*.md`.
```powershell
phoenix generate --story-file user_story.txt --url "https://app.com"
phoenix generate --story "As a user..." --url "https://app.com" --risk smoke
phoenix generate --story-file stories.txt --url "https://app.com" --clean
```

### `phoenix automate`
Generate automation scripts from reviewed manual test cases. Reads `manual_tests/*.md`
and writes one `test_results/test_*.py` per manual test (1:1 mapping).
```powershell
phoenix automate --url "https://app.com"
phoenix automate --url "https://app.com" --clean
phoenix automate --manual-dir path/to/manual_tests --url "https://app.com"
```

### `phoenix run`
Run automation scripts with self-healing retries and execution logging.
```powershell
phoenix run
phoenix run --browser firefox
phoenix run --failed-only
phoenix run --heal --max-attempts 3
phoenix run --logs-dir logs/ --locators-dir locators/
```

### `phoenix fix`
Fix failing scripts using error output from the last run.
```powershell
phoenix fix
phoenix fix --dry-run
phoenix fix --run-id <id>
phoenix fix --url "https://app.com"
```

### `phoenix logs`
View execution log history.
```powershell
phoenix logs                        # List last 10 runs
phoenix logs --limit 20             # List last 20 runs
phoenix logs --run-id <id>          # Show all attempts for a specific run
phoenix logs --output json          # JSON format
```

### `phoenix locators`
List registered LocatorBundles from `locators/` directory.
```powershell
phoenix locators
phoenix locators --page login
phoenix locators --output json
```

### `phoenix report`
Show execution report summary.
```powershell
phoenix report
phoenix report --execution-id 5
```

---

## Configuration — `.phoenixrc`

`phoenix init` creates a `.phoenixrc` TOML file in your project directory:

```toml
[project]
default_project    = "my-project"
application_url    = "https://your-app.com"
manual_output_dir  = "./manual_tests"
test_output_dir    = "./test_results"
report_output_dir  = "./reports"

[intelligence]
base_url    = "http://localhost:8001/api/v1"
timeout     = 60
retry_count = 3

[execution]
default_browser = "chromium"

[database]
url = "sqlite:///./phoenix.db"
```

---

## LLM Providers

| Provider | Environment Variables |
|----------|-----------------------|
| **Anthropic** (default) | `ANTHROPIC_API_KEY`, `PHOENIX_LLM_MODEL=claude-sonnet-4-20250514` |
| OpenAI | `OPENAI_API_KEY`, `PHOENIX_LLM_PROVIDER=openai`, `PHOENIX_LLM_MODEL=gpt-4o` |
| Google Gemini | `GOOGLE_API_KEY`, `PHOENIX_LLM_PROVIDER=gemini`, `PHOENIX_LLM_MODEL=gemini-1.5-pro` |
| Ollama (local) | `PHOENIX_LLM_PROVIDER=ollama`, `PHOENIX_LLM_MODEL=llama3`, `OLLAMA_BASE_URL=http://localhost:11434` |

---

## Intelligence API Reference

Full interactive docs at `http://localhost:8001/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server and LLM status |
| `POST` | `/api/v1/tests/generate` | Generate manual test cases from a user story |
| `POST` | `/api/v1/tests/automate` | Generate automation scripts from pre-written manual tests (1 per test) |
| `POST` | `/api/v1/tests/fix` | Fix a failing script using its exact error output |
| `POST` | `/api/v1/locators/discover` | Discover stable Playwright locators for page elements |
| `POST` | `/api/v1/failures/analyze` | Analyze a test failure and suggest a targeted fix |

---

## Versioned Prompts

Each agent has its own versioned prompt file under `phoenix-intelligence/prompts/`:

```
prompts/
├── manual_test_generator/1.0.md   # Generates 3–5 consolidated manual tests
├── automation_from_manual/1.0.md  # Translates a manual test into Playwright code
├── script_fixer/1.0.md            # Fixes a failing script given its error output
├── test_generator/1.0.md          # Legacy single-script generator
├── test_name/1.0.md
├── locator_expert/1.0.md
└── failure_analyzer/1.0.md
```

To update a prompt without breaking existing behaviour, create a new version file (e.g. `1.1.md`).
The loader automatically picks up the latest version on the next request.

> **Note:** The intelligence server caches prompts in memory. Restart the server after editing
> a prompt file for changes to take effect.

---

## Knowledge Base

The knowledge base is automatically injected into every LLM prompt. Drop a `.md` file in any
folder under `phoenix-intelligence/services/knowledge/` and it is loaded on the next request.

```
knowledge/
├── playwright/
│   ├── locator_rules.md
│   ├── assertions.md
│   ├── waiting_rules.md
│   └── security_rules.md
├── test_patterns/
│   ├── login_flow.md
│   └── crud_operations.md
├── best_practices/
│   └── test_design.md
└── domain_knowledge/
    └── ecommerce.md
```

---

## Docker

```powershell
cp infra/.env.example infra/.env
# Edit infra/.env and set ANTHROPIC_API_KEY

docker compose -f infra/docker-compose.yml up intelligence
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
