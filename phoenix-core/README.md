# phoenix-core

The CLI and SDK package. No LLM or AI logic lives here — it communicates with `phoenix-intelligence` over HTTP.

## What it contains

| Module | Purpose |
|---|---|
| `phoenix/cli/` | All CLI commands (`init`, `generate`, `automate`, `run`, `fix`, `report`, `jira`, …) |
| `phoenix/sdk/` | `PhoenixClient`, `IntelligenceClient`, `PhoenixConfig` |
| `phoenix/generators/writer.py` | `ModuleAwareWriter` — one consolidated file per module |
| `phoenix/generators/automation.py` | Normalises and validates LLM-generated Playwright scripts (`CleanCodeGate`) |
| `phoenix/generators/clean_code.py` | Gate rules: WARNING_COMMENT, UNGROUNDABLE_LOCATOR, BUSINESS_TEXT_URL_REGEX |
| `phoenix/generators/manual.py` | `ManualTestQualityGate` + Markdown writer for manual test cases |
| `phoenix/test_data/` | `TestDataEngine` — step-based generic field extraction + realistic value generation |
| `phoenix/documents/loader.py` | `DocumentLoader` — text extraction from PDF, DOCX, XLSX, CSV, JSON, XML, TXT, MD, YAML, HTML |
| `phoenix/integrations/jira/` | `JiraClient`, `JiraConfig`, ADF→text converter — Jira Cloud + Server/DC |
| `phoenix/execution/` | `HealingEngine` (retry loop), `ExecutionLogger`, pytest runner |
| `phoenix/locators/` | `LocatorRegistry` — loads/saves LocatorBundle JSON files |

### SmartLocatorAI integration

`phoenix automate` runs SmartLocatorAI as a non-blocking DOM pre-pass. Its
validated `locators.json` output is translated by `smartlocator_adaptor.py`,
merged with Phoenix-generated locator candidates, and persisted through the
same `LocatorRegistry` path for both flat and POM layouts.

Install the SmartLocatorAI package in the same environment before running the
CLI. During local development with sibling checkouts:

```bash
pip install -e ../Phoenix-SmartLocatorAI
```

If the optional package is absent or the target cannot be scanned, Phoenix
logs a warning and continues with its existing locator-generation flow.

Locators can be scanned, validated, converted, and persisted using SmartLocatorAI:

```powershell
phoenix locators scan --url "https://app.example" --page login
```

By default, this command operates in a safe, deterministic mode (`--no-llm-fallback`) and **never makes paid LLM / Anthropic calls**. Candidates that do not have a browser-verified primary locator are reported as unresolved and are not saved to the registry.

To enable conditional `LocatorExpert` LLM fallback for unresolved or ambiguous elements:

```powershell
phoenix locators scan --url "https://app.example" --page login --llm-fallback
```

### LocatorExpert Fallback & Validation Rules

1. **SmartLocatorAI First**: SmartLocatorAI scans and validates the DOM first. If an element is uniquely resolved (`count == 1`), LocatorExpert is **never called**.
2. **Conditional Invocation**: If an element is missing, invalid, or ambiguous, it is sent to LocatorExpert (when `--llm-fallback` is set and valid credentials are configured).
3. **Strict Validation**:
   - `count == 1`: Accepted and merged into the `LocatorBundle`.
   - `count == 0`: Rejected (not found).
   - `count > 1`: Rejected (ambiguous).
   - Positional selectors (`.first()`, `.last()`, `.nth()`, `:nth-child()`, `//...[1]`) are strictly rejected.
4. **Candidate Preservation**: Validated LLM locators are merged into the bundle without destroying existing SmartLocatorAI primary or alternate locators.
5. **Deduplication**: Repeated scans maintain normalized deduplication to prevent duplicate registry entries.
6. **Scan Summary**: The CLI outputs a scan summary distinguishing between SmartLocatorAI resolutions, LocatorExpert fallback attempts/resolutions, unresolved count, LLM calls, duration, and token usage (when available).

To retain SmartLocatorAI's raw JSON and generated page-object artifacts for inspection:

```powershell
phoenix locators scan --url "https://app.example" --page login --keep-raw
```

| `phoenix/reporting/` | `DataLoader`, `RunAggregator`, `TrendAggregator`, `ReportGenerator`, `render_run_report()` — 10-section self-contained HTML report |
| `phoenix/scaffold.py` | `phoenix init` logic — creates the canonical project layout |
| `phoenix/templates/project/` | Jinja2 templates rendered into the new project |

## Local development

```powershell
cd phoenix-core
pip install -e .
```

## Key design decisions

**ModuleAwareWriter** — instead of one file per test, all tests for a module are merged into a single file (`tests/login/test_login.py`). Dedup is by function name (incoming replaces existing). Smoke tests are sorted to the top.

**TestDataEngine** — generates realistic test data using stdlib only (no faker). Field names are extracted from the actual manual test step text using regex patterns (`_extract_fields_from_steps()`), then classified via `FieldDetector` for type-appropriate value generation. Works for any project domain — no hardcoded module-to-field mappings.

**Manual-First gate** — `ManualTestQualityGate` validates every test case before writing it. Tests with placeholder text, missing steps, or empty expected results are rejected.

**CleanCodeGate** — validates generated scripts before writing. Three rule types: `WARNING` (allowed with a flag), `UNGROUNDABLE_LOCATOR` (XPath, dynamic IDs, app-specific CSS), `BUSINESS_TEXT_URL_REGEX` (hardcoded URLs inferred from business text, not DOM inspection).

**DocumentLoader** — extracts text from supporting documents attached to a user story. Native support for `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.yaml`, `.html`; optional support for `.pdf` (pypdf), `.docx` (python-docx), `.xlsx`/`.xls` (openpyxl). Per-doc limit 8,000 chars; total limit 32,000 chars. Auto-discovers `user_stories/<story_name>/` folder by convention.

**Jira integration** — `JiraClient` auto-detects Jira Cloud (REST v3 / ADF) vs Server/DC (REST v2) via the health check endpoint. `JiraConfig` reads non-sensitive settings from `.phoenixrc [jira]`; the API token is read only from the `JIRA_API_TOKEN` environment variable and is never stored on disk.

**`_llm_with_fallback` pattern** — every agent tries the LLM first; if it fails or is not configured, a deterministic heuristic runs instead. No silent failures.

**Reporting pipeline** — `phoenix run` auto-generates `reports/report_<run_id>.html` via the `phoenix.reporting` package. The report is a single self-contained HTML file (no server, works on `file://`). All data is embedded as a JSON blob; Chart.js is loaded from CDN with an offline fallback. `phoenix report --trend` aggregates the last N JSONL logs to produce a multi-run trend report.

**Screenshot capture** — `conftest.py` contains a `pytest_runtest_makereport` hook that captures `reports/screenshots/<safe_nodeid>.png` on every test failure. The path is also recorded in the JSONL log so the HTML report can link to it.

## Config fields (`PhoenixConfig`)

New fields added alongside legacy ones (backwards-compatible):

| Field | Default | Description |
|---|---|---|
| `project.name` | `"default"` | Project name (new schema) |
| `project.base_url` | `None` | Application URL (new schema) |
| `project.tests_dir` | `"./tests"` | Module-organised test directory |
| `project.test_data_dir` | `"./test_data"` | Generated test data directory |
| `jira.url` | `None` | Jira instance URL (also reads `JIRA_URL` env var) |
| `jira.project_key` | `None` | Jira project key (e.g. `PROJ`) |
| `jira.acceptance_criteria_field` | `"description"` | Jira field name for acceptance criteria |
| `jira.download_attachments` | `True` | Whether to download and extract Jira attachments |
| `jira.max_attachment_size_kb` | `5120` | Skip attachments larger than this (KB) |
