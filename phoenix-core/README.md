# phoenix-core

The CLI and SDK package. No LLM or AI logic lives here — it communicates with `phoenix-intelligence` over HTTP.

## What it contains

| Module | Purpose |
|---|---|
| `phoenix/cli/` | All CLI commands (`init`, `generate`, `automate`, `run`, `fix`, `report`, …) |
| `phoenix/sdk/` | `PhoenixClient`, `IntelligenceClient`, `PhoenixConfig` |
| `phoenix/generators/writer.py` | `ModuleAwareWriter` — one consolidated file per module |
| `phoenix/generators/automation.py` | Normalises and validates LLM-generated Playwright scripts |
| `phoenix/generators/manual.py` | Quality gate + Markdown writer for manual test cases |
| `phoenix/test_data/` | `TestDataEngine` — generates `test_data/<module>.json` |
| `phoenix/execution/` | `HealingEngine` (retry loop + failure screenshot capture), `ExecutionLogger`, pytest runner |
| `phoenix/locators/` | `LocatorRegistry` — loads/saves LocatorBundle JSON files |
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

**TestDataEngine** — generates realistic test data using stdlib only (no faker). Produces 3 happy-path scenarios and per-field edge cases. Output is `test_data/<module>.json`.

**Manual-First gate** — `ManualTestGenerator` validates every test case before writing it. Tests with placeholder text, missing steps, or empty expected results are rejected.

**`_llm_with_fallback` pattern** — every agent tries the LLM first; if it fails or is not configured, a deterministic heuristic runs instead. No silent failures.

**Reporting pipeline** — `phoenix run` auto-generates `reports/report_<run_id>.html` via the `phoenix.reporting` package. The report is a single self-contained HTML file (no server, works on `file://`). All data is embedded as a JSON blob; Chart.js is loaded from CDN with an offline fallback. `phoenix report --trend` aggregates the last N JSONL logs to produce a multi-run trend report.

**Screenshot capture** — `HealingEngine` passes `--screenshot=only-on-failure --output=test-results` to every pytest invocation. After each attempt it scans `test-results/**/*.png` for new files and records the path in the JSONL log so the HTML report can link to screenshots.

## Config fields (`PhoenixConfig`)

New fields added alongside legacy ones (backwards-compatible):

| Field | Default | Description |
|---|---|---|
| `project.name` | `"default"` | Project name (new schema) |
| `project.base_url` | `None` | Application URL (new schema) |
| `project.tests_dir` | `"./tests"` | Module-organised test directory |
| `project.test_data_dir` | `"./test_data"` | Generated test data directory |
