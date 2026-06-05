# Phoenix SmartAutomation — Architecture

## Overview

Phoenix is a monorepo with three packages and strict dependency isolation:

```
Phoenix-SmartAutomation/
├── shared/                  # Pydantic contracts (zero runtime deps beyond pydantic)
├── phoenix-core/            # CLI + SDK (pip install phoenix-core)
├── phoenix-intelligence/    # AI server (FastAPI, port 8001)
└── docs/                    # Architecture docs
```

**Dependency rule:** `shared` ← `phoenix-core` ← user project.
`phoenix-intelligence` imports `shared` but **never** imports from `phoenix-core`.
`phoenix-core` contains **no AI, LLM, or MCP code** — only HTTP calls to the intelligence server.

---

## Package responsibilities

### `shared/`
Pydantic models that define the API contract between `phoenix-core` and `phoenix-intelligence`. Both packages import from here. Changing a model here is a breaking change.

### `phoenix-core/`
The user-facing package. Users `pip install phoenix-core` in their projects.

| Component | Path | Role |
|---|---|---|
| CLI commands | `phoenix/cli/commands.py` | `phoenix generate`, `phoenix automate`, `phoenix run`, `phoenix fix`, `phoenix report`, `phoenix jira` |
| PhoenixClient | `phoenix/sdk/client.py` | HTTP client for the intelligence API |
| ProjectConfig | `phoenix/sdk/config.py` | Reads `.phoenixrc` TOML, env vars, defaults |
| ModuleAwareWriter | `phoenix/generators/writer.py` | Writes one consolidated file per module: `tests/{module}/test_{module}.py`, `locators/{module}.json`, `manual_tests/{module}.md` |
| CleanCodeGate | `phoenix/generators/clean_code.py` | Validates generated scripts: WARNING_COMMENT, UNGROUNDABLE_LOCATOR, BUSINESS_TEXT_URL_REGEX rules |
| TestDataEngine | `phoenix/test_data/engine.py` | stdlib-only test data generator — extracts field names from manual test steps via regex, infers types via FieldDetector, generates realistic values |
| DocumentLoader | `phoenix/documents/loader.py` | Extracts text from supporting docs attached to user stories: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.json`, `.xml`, `.yaml`, `.html`, `.txt`, `.md` |
| JiraClient | `phoenix/integrations/jira/client.py` | Fetches story, acceptance criteria, and attachments from Jira (Cloud ADF v3 + Server/DC v2 auto-detect) |
| JiraConfig | `phoenix/integrations/jira/config.py` | Non-sensitive Jira settings from `.phoenixrc`; API token read-only from `JIRA_API_TOKEN` env var |
| HealingEngine | `phoenix/execution/healing.py` | Retry loop with self-healing for failed tests |
| ExecutionLogger | `phoenix/execution/logger.py` | Writes per-attempt JSONL records to `logs/run_<ts>_<run_id>.jsonl` |
| LocatorRegistry | `phoenix/locators/registry.py` | Loads `locators/{module}.json` and provides `registry.get("element_id")` |
| Scaffold | `phoenix/scaffold.py` | `phoenix init` — renders Jinja2 templates into a new project directory |
| Reporting | `phoenix/reporting/` | HTML report pipeline: `DataLoader` reads JSONL logs, `RunAggregator`/`TrendAggregator` compute metrics, `render_run_report()` produces the self-contained HTML |

### `phoenix-intelligence/`
AI server. Runs on port 8001. Never called directly by users — only via `phoenix-core`.

| Component | Path | Role |
|---|---|---|
| FastAPI app | `api/server.py` | REST endpoints (`/api/v1/tests/generate`, `/automate`, `/fix`, `/locators/discover`) |
| TestGeneratorAgent | `services/agents/test_generator.py` | LLM-powered manual test + automation script generation; accepts `supporting_documents` and `domain_knowledge` |
| ScriptFixer | `services/agents/script_fixer.py` | Fixes failing scripts using error output |
| LocatorExpert | `services/agents/locator_expert.py` | Discovers stable locators for an element |
| FailureAnalyzer | `services/agents/failure_analyzer.py` | Root-cause analysis for failing tests |
| LLM router | `services/llm/router.py` | Routes to Anthropic / OpenAI / Gemini / Ollama |
| PromptLoader | `services/llm/prompt_loader.py` | Loads versioned prompt files from `prompts/` — auto-selects latest |
| MCPClient | `services/mcp/client.py` | Connects to `@playwright/mcp` via stdio, calls `browser_snapshot` to get DOM accessibility tree |
| KnowledgeBase | `services/knowledge/` | Markdown files loaded as context for agent prompts |

---

## Workflow

```
user_stories/login.txt          ─OR─   Jira ticket (PROJ-123)
  + user_stories/login/                  + attachments (PDF, DOCX, …)
      wireframe.pdf
      field_rules.xlsx
  + domain_knowledge/            ← project-wide UI patterns, URLs, auth flow
        │
        ▼  phoenix generate [--story-file | --jira PROJ-123]
    DocumentLoader (supporting docs → text)
    JiraClient (issue + attachments, if --jira)
    intelligence server
        ├── domain_knowledge injected into every LLM call
        ├── supporting_documents injected into manual test prompt
        ├── manual_test_generator prompt v1.0 (LLM)
        └── writes manual_tests/login.md + test_data/login.json
        │
        ▼  (user reviews manual_tests/login.md)
        │
        ▼  phoenix automate
    intelligence server
        ├── MCPClient → browser_snapshot(url) → DOM accessibility tree
        ├── automation_from_manual prompt v2.0 (LLM)
        │     ├── ### SCRIPT  → test function
        │     ├── ### LOCATORS → locator entries JSON
        │     └── ### RECOMMENDATIONS → issues for review
        └── writes tests/login/test_login.py
                  locators/login.json
        │
        ▼  phoenix run
    pytest + Playwright (local, no AI)
        ├── HealingEngine (retry on failure)
        │     └── conftest.py hook captures screenshots → reports/screenshots/<nodeid>.png
        ├── writes logs/run_<ts>_<run_id>.jsonl
        └── auto-generates reports/report_<run_id>.html (10-section rich report)
        │
        ▼  phoenix fix (if failures)
    intelligence server
        ├── script_fixer prompt v1.0 (LLM)
        └── rewrites failing tests
```

---

## Domain knowledge vs supporting documents

| | Domain knowledge | Supporting documents |
|---|---|---|
| **Scope** | Whole project | One user story |
| **Location** | `domain_knowledge/` (project root) | `user_stories/<story_name>/` folder |
| **Content** | Login URL, nav patterns, custom UI widgets, field formats | Wireframes, spec PDFs, DOCX, XLSX, schemas |
| **Injected into** | Every LLM call | Only the generate call for that story |
| **Files** | `navigation.md`, `ui_patterns.md`, `data_rules.md` | Any of: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.json`, `.xml`, `.yaml`, `.html`, `.txt`, `.md` |
| **Auto-discovered** | All files in `domain_knowledge/` | `user_stories/<story_name>/` (same name as story, no extension) |

---

## Jira integration

`phoenix generate --jira PROJ-123` triggers this path:

1. `JiraClient.health_check()` — tries v3 (Cloud) then falls back to v2 (Server/DC)
2. `JiraClient.get_issue(key)` — fetches summary, description, acceptance criteria
3. ADF → text conversion (`adf.py`) for Jira Cloud rich text
4. `JiraIssue.as_user_story()` — formats the issue as a plain-text user story
5. If `download_attachments = true`, `JiraIssue.as_supporting_documents(client)` downloads each attachment and passes it through `DocumentLoader`
6. Supporting documents are merged with any local `--docs` docs and sent to the intelligence server

**Security:** `JIRA_API_TOKEN` is read only from the environment variable — never stored in `.phoenixrc`.

---

## Reporting subsystem (`phoenix/reporting/`)

The reporting package is pure-Python (no external runtime dependencies). It reads from JSONL logs and produces a self-contained HTML report that works on `file://` with no server required.

| Module | Role |
|---|---|
| `data_loader.py` | `DataLoader` — reads `logs/run_*.jsonl`; provides `load_run(run_id)`, `load_last_n_runs(n)`, `list_run_ids()` |
| `aggregator.py` | `RunAggregator` — pass rate, healed count, module breakdown, per-test summary, error-type counts; `TrendAggregator` — trend series, flakiness detection, delta vs previous run |
| `render.py` | `render_run_report()` — produces the full 10-section HTML; Chart.js loaded from CDN with offline fallback; all data embedded as a JSON blob so the file works on `file://` |
| `generator.py` | `ReportGenerator` — high-level API: `generate_run_report(run_id, open_browser)`, `generate_trend_report(last_n_runs)` |

The 10 report sections are: Run Summary · Module Breakdown · Test Results (filterable/searchable) · Failure Analysis · Healing Insights · Error Type Distribution · Trend Charts (pass-rate, duration, healing stacked) · Flakiness Report · Attempt Detail · Environment Info.

---

## Locator strategy (v2.0)

All generated locators follow this priority. Lower tiers are only used when higher tiers cannot uniquely identify the element in the DOM snapshot.

| Priority | Locator | Condition |
|---|---|---|
| 1 | `[data-testid="..."]` | Always preferred when present |
| 2 | `#stable-id` | Only non-framework-generated IDs (no `ember*`, `react-select-*`) |
| 3 | `[name="field"]` | Reliable for form inputs |
| 4 | `get_by_placeholder()` | Placeholder text from DOM snapshot |
| 5 | `get_by_label()` | Only if real `<label>` exists in DOM snapshot |
| 6 | `get_by_role()` | Scoped to a container; last resort for interactive elements |
| 7 | `get_by_text()` | Static read-only text only; ≤6 words; not from criterion prose |

XPath, dynamic IDs, `networkidle`, `time.sleep()`, and app-specific CSS classes (`.oxd-*`, `.mat-*`) are explicitly forbidden.

---

## Prompt versioning

Prompts live in `phoenix-intelligence/prompts/<agent>/<version>.md` with YAML front-matter.
`PromptLoader.get(agent)` auto-selects the highest semantic version. Adding a new version file is all that is needed to upgrade — no code change required.

Current versions:

| Prompt | Version | Purpose |
|---|---|---|
| `automation_from_manual` | 2.0 | Translates manual test → Playwright script (v2.0 = DOM-grounded locators) |
| `manual_test_generator` | 1.0 | Generates structured manual test cases from a user story + supporting documents |
| `script_fixer` | 1.0 | Fixes a failing Playwright script using its error output |
| `locator_expert` | 1.0 | Discovers stable locators for a page element |
| `failure_analyzer` | 1.0 | Root-cause analysis for a failing test |
| `test_name` | 1.0 | Derives a short snake_case function name from a test description |
| `test_quality_standards` | 1.0 | Assertion, waiting, marker, and security rules injected into **every** generation pass |

---

## Generated project structure

A project created with `phoenix init` has this layout:

```
my-project/
├── .phoenixrc               ← TOML config (base_url, browser, optional [jira] section)
├── .env / .env.local        ← env var template (APP_URL, TEST_USERNAME, TEST_PASSWORD, Jira secrets)
├── pyproject.toml           ← pytest markers: smoke, regression, sanity, {module}
├── Makefile                 ← make smoke / regression / report / clean
├── conftest.py              ← page fixture, screenshot-on-failure hook
├── user_stories/
│   ├── login.txt            ← starter user story (edit this)
│   ├── SUPPORTING_DOCS.md   ← explains the supporting-docs convention
│   └── login/               ← (optional) wireframe.pdf, field_rules.xlsx, etc.
├── domain_knowledge/        ← project-wide context injected into every LLM call
│   ├── README.md
│   ├── navigation.md        ← login URL, key page paths, auth flow
│   ├── ui_patterns.md       ← custom dropdowns, date pickers, modals
│   └── data_rules.md        ← field formats, required fields, test credentials format
├── manual_tests/            ← output: one .md file per module
├── test_data/               ← output: one .json file per module
├── tests/{module}/          ← output: one test_{module}.py per module
├── locators/                ← output: one {module}.json per module
├── fixtures/                ← auth.py, browser.py
├── config/                  ← settings.yaml, environments/
├── reports/
│   └── screenshots/         ← failure screenshots (auto-captured by conftest.py hook)
└── logs/                    ← JSONL execution logs (run_<ts>_<run_id>.jsonl)
```

Credentials are **never hardcoded** — always read from `os.environ["APP_URL"]`, `os.environ["TEST_USERNAME"]`, `os.environ["TEST_PASSWORD"]`.
