# Phoenix Smart Automation

Enterprise-grade AI-powered QA automation platform. Describe a user story — Phoenix generates manual test cases and runnable Playwright scripts automatically.

---

## How It Works

```
Your user story
      │
      ▼
phoenix-intelligence  ←── Anthropic Claude (LLM)
  (FastAPI, port 8001)  ←── Playwright MCP (live page inspection)
  (Knowledge Base)      ←── Playwright rules, test patterns, best practices
      │
      ▼
phoenix-core CLI
  └── manual_tests/    ←── Structured Markdown test cases
  └── test_results/    ←── Ready-to-run pytest + Playwright scripts
  └── reports/         ←── HTML execution reports
```

---

## Project Structure

```
Phoenix-SmartAutomation/
├── shared/                    # Pydantic contracts shared by both packages
├── phoenix-core/              # pip-installable SDK + CLI (no AI/LLM deps)
│   └── phoenix/
│       ├── cli/               # Commands: init, generate, execute, run, report
│       ├── sdk/               # PhoenixClient, config (.phoenixrc / phoenix.yaml)
│       ├── generators/        # Writes manual .md and automation .py files
│       ├── execution/         # Runs pytest, collects results
│       ├── reporting/         # HTML report generator
│       └── storage/           # SQLAlchemy models + SQLite database
│
├── phoenix-intelligence/      # Hosted AI server (FastAPI, port 8001)
│   ├── api/                   # REST endpoints
│   ├── services/agents/       # TestGenerator, LocatorExpert, FailureAnalyzer
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

```bash
git clone <repo-url>
cd Phoenix-SmartAutomation

python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 2. Install packages

```bash
pip install -e shared/
pip install -e phoenix-core/
pip install -e phoenix-intelligence/
```

### 3. Install Playwright browsers

```bash
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

## Step 1: Start the Intelligence Server

The intelligence server handles all AI operations. Start it once and leave it running in a dedicated terminal.

**Windows PowerShell:**
```powershell
cd phoenix-intelligence
.\start_server.ps1
```

**Windows CMD:**
```cmd
cd phoenix-intelligence
start_server.bat
```

**Linux / macOS:**
```bash
cd phoenix-intelligence
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
python api/server.py
```

**Verify it is running:**
```bash
curl http://localhost:8001/docs
# or open http://localhost:8001/docs in your browser
```

---

## Step 2: Use the CLI

Open a second terminal with the virtual environment active.

### Initialize a new project

```bash
mkdir my-project && cd my-project
phoenix init
```

Creates a `.phoenixrc` config file and the output directories (`manual_tests/`, `test_results/`, `reports/`).

### Generate test cases

```bash
# From a user story string (generates both manual and automation tests)
phoenix generate \
  --story "As a user, I want to log in with valid credentials so I can access my dashboard" \
  --url "https://your-app.com/login"

# From a file containing multiple user stories
phoenix generate --story-file stories.txt --url "https://your-app.com"

# Manual tests only
phoenix generate --story "..." --type manual

# Automation tests only, smoke level
phoenix generate --story "..." --url "https://..." --type automation --risk smoke

# Regenerate (delete previous outputs first)
phoenix generate --story "..." --url "https://..." --clean
```

### Execute automation tests

```bash
phoenix execute
phoenix execute --browser firefox
phoenix execute --test-ids 1 2 3
```

### View execution report

```bash
phoenix report
phoenix report --execution-id 5
```

### Global options

```bash
phoenix --config /path/to/.phoenixrc generate ...   # explicit config file
phoenix --verbose generate ...                       # show detailed output
phoenix --help                                       # list all commands
```

---

## Configuration — `.phoenixrc`

`phoenix init` creates a `.phoenixrc` TOML file in your project directory:

```toml
[project]
default_project    = "my-project"
application_url    = "https://your-app.com"   # default URL for generate
manual_output_dir  = "./manual_tests"
test_output_dir    = "./test_results"
report_output_dir  = "./reports"

[intelligence]
base_url    = "http://localhost:8001/api/v1"
timeout     = 60
retry_count = 3

[database]
url = "sqlite:///./phoenix.db"
```

> **Legacy:** `phoenix.yaml` is still supported for existing projects.

---

## Running the Example Tests

`examples/sample_project/` contains three ready-to-run tests against `https://the-internet.herokuapp.com`. No intelligence server or API key needed.

```bash
cd examples/sample_project

# Install if needed
pip install pytest pytest-playwright
playwright install chromium

# Run all examples
pytest

# Headed mode (watch the browser)
pytest --headed

# Run a specific file
pytest test_results/test_login.py -v
pytest test_results/test_dynamic_content.py -v
pytest test_results/test_data_table.py -v
```

| File | Covers |
|------|--------|
| `test_login.py` | Valid login, wrong password, wrong username, logout |
| `test_dynamic_content.py` | Checkboxes, dropdown select, dynamic loading (async content) |
| `test_data_table.py` | Table headers, row-level actions, column sorting |

---

## Generating Tests for the Example Site

```bash
cd examples/sample_project

phoenix generate \
  --story "As a user, I want to log in with valid credentials so I can access the secure area" \
  --url "https://the-internet.herokuapp.com/login" \
  --type both \
  --risk smoke
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

## Docker

```bash
cp infra/.env.example infra/.env
# Edit infra/.env and set ANTHROPIC_API_KEY

docker compose -f infra/docker-compose.yml up intelligence
```

---

## Intelligence API Reference

Full interactive docs at `http://localhost:8001/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/tests/generate` | Generate manual + automation tests from a user story |
| `POST` | `/api/v1/locators/discover` | Discover stable Playwright locators for page elements |
| `POST` | `/api/v1/failures/analyze` | Analyze a test failure and suggest a targeted fix |

---

## Knowledge Base

The knowledge base is automatically injected into every LLM prompt. Files live under `phoenix-intelligence/services/knowledge/`:

```
knowledge/
├── playwright/
│   ├── locator_rules.md      # Priority order, strict mode, anti-patterns
│   ├── assertions.md         # expect() patterns
│   ├── waiting_rules.md      # Auto-waiting, networkidle
│   └── security_rules.md     # Auth handling, input sanitization
├── test_patterns/
│   ├── login_flow.md
│   └── crud_operations.md
├── best_practices/
│   └── test_design.md
└── domain_knowledge/
    └── ecommerce.md
```

**Add your own rules**: drop a `.md` file in any folder — it is loaded automatically on the next request.

---

## Versioned Prompts

Each agent has its own versioned prompt file under `phoenix-intelligence/prompts/`:

```
prompts/
├── test_generator/1.0.md
├── manual_test_generator/1.0.md
├── test_name/1.0.md
├── locator_expert/1.0.md
└── failure_analyzer/1.0.md
```

To update a prompt without breaking existing behaviour, create a new version file (e.g., `1.1.md`). The loader automatically uses the latest version.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
