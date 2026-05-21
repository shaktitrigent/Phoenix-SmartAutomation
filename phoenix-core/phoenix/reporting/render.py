"""HTML report renderer for Phoenix SmartAutomation.

Generates a complete self-contained HTML file.  All dynamic content is encoded
as a single JSON blob in a <script id="PHOENIX_DATA"> tag so the page works on
the file:// protocol without a server.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix.execution.logger import AttemptRecord
from phoenix.reporting.aggregator import RunAggregator, TrendAggregator


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def render_run_report(
    run_record: Dict[str, Any],
    attempts: List[AttemptRecord],
    trend_runs: List,            # list[tuple[dict, list[AttemptRecord]]]
    project_name: str = "Phoenix Project",
    environment: str = "",
) -> str:
    """Return a complete self-contained HTML string."""

    agg = RunAggregator(run_record, attempts)
    trend_agg = TrendAggregator(trend_runs) if trend_runs else None

    run_id = run_record.get("run_id", "unknown")
    started_at_raw = run_record.get("started_at", "")
    finished_at_raw = run_record.get("finished_at", "")
    total = run_record.get("total", 0)
    passed = run_record.get("passed", 0)
    failed = run_record.get("failed", 0)
    skipped = run_record.get("skipped", 0)
    duration = run_record.get("duration_seconds", 0.0)

    started_display = _fmt_dt(started_at_raw)
    duration_display = _fmt_duration(duration)

    pass_rate = agg.pass_rate
    healed_count = agg.healed_count
    healed_pct = agg.healed_pct
    error_type_counts = agg.error_type_counts()
    error_type_healing = agg.error_type_healing()
    top_error = (list(error_type_counts.keys())[0]) if error_type_counts else "none"
    top_error_count = (list(error_type_counts.values())[0]) if error_type_counts else 0

    delta = trend_agg.prev_run_delta() if trend_agg else {"pass_rate_delta": None, "duration_delta": None}
    pr_delta = delta["pass_rate_delta"]
    dur_delta = delta["duration_delta"]

    per_test = agg.per_test_summary()
    module_breakdown = agg.module_breakdown()

    trend_pass_rate = trend_agg.pass_rate_trend() if trend_agg else []
    trend_duration = trend_agg.duration_trend() if trend_agg else []
    trend_healing = trend_agg.healing_trend() if trend_agg else []
    flaky_tests = trend_agg.flaky_tests() if trend_agg else []

    has_trends = len(trend_runs) >= 2
    has_flakiness = len(trend_runs) >= 3
    has_healing = healed_count > 0
    has_failures = any(t["status"] in ("failed", "error") for t in per_test)

    # -----------------------------------------------------------------------
    # Build the JSON data blob
    # -----------------------------------------------------------------------
    phoenix_data = {
        "run_id": run_id,
        "project_name": project_name,
        "environment": environment,
        "started_at": started_at_raw,
        "finished_at": finished_at_raw,
        "started_display": started_display,
        "duration_display": duration_display,
        "duration_seconds": duration,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": pass_rate,
        "healed_count": healed_count,
        "healed_pct": healed_pct,
        "top_error": top_error,
        "top_error_count": top_error_count,
        "pr_delta": pr_delta,
        "dur_delta": dur_delta,
        "per_test": per_test,
        "module_breakdown": module_breakdown,
        "error_type_counts": error_type_counts,
        "error_type_healing": error_type_healing,
        "trend_pass_rate": trend_pass_rate,
        "trend_duration": trend_duration,
        "trend_healing": trend_healing,
        "flaky_tests": flaky_tests,
    }

    data_json = json.dumps(phoenix_data, ensure_ascii=False, default=str)

    # -----------------------------------------------------------------------
    # CSS
    # -----------------------------------------------------------------------
    css = _build_css()

    # -----------------------------------------------------------------------
    # JS
    # -----------------------------------------------------------------------
    js = _build_js()

    # -----------------------------------------------------------------------
    # Static HTML sections
    # -----------------------------------------------------------------------
    env_badge_class = {
        "qa": "env-qa",
        "staging": "env-staging",
        "prod": "env-prod",
        "production": "env-prod",
    }.get((environment or "").lower(), "env-other")

    env_badge = (
        f'<span class="env-badge {env_badge_class}">{html.escape(environment)}</span>'
        if environment
        else ""
    )

    run_id_short = run_id[:8]

    # Pass-rate arrow
    pr_arrow = ""
    pr_delta_cls = ""
    if pr_delta is not None:
        if pr_delta > 0:
            pr_arrow = f'<span class="trend-up">▲ {pr_delta:+.1f}%</span>'
        elif pr_delta < 0:
            pr_arrow = f'<span class="trend-down">▼ {pr_delta:.1f}%</span>'
        else:
            pr_arrow = '<span class="trend-flat">— no change</span>'

    dur_arrow = ""
    if dur_delta is not None:
        if dur_delta > 0:
            dur_arrow = f'<span class="trend-down">▲ +{_fmt_duration(dur_delta)}</span>'
        elif dur_delta < 0:
            dur_arrow = f'<span class="trend-up">▼ {_fmt_duration(abs(dur_delta))}</span>'

    # -----------------------------------------------------------------------
    # Assemble
    # -----------------------------------------------------------------------
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phoenix Report — {html.escape(project_name)} — {html.escape(run_id_short)}</title>
<style>{css}</style>
</head>
<body>

<!-- =====================================================================
     Section 1 — Sticky Header
     ===================================================================== -->
<header class="top-bar" role="banner">
  <div class="top-bar-inner">
    <div class="top-bar-left">
      <span class="project-name">{html.escape(project_name)}</span>
      <span class="separator">|</span>
      <span class="run-id-label">Run&nbsp;<code id="run-id-text">{html.escape(run_id_short)}</code></span>
      <span class="separator">|</span>
      <span class="ts-label">{html.escape(started_display)}</span>
      {env_badge}
      <span class="watermark">Phoenix SmartAutomation</span>
    </div>
    <div class="top-bar-right">
      <button class="btn-header" onclick="window.print()" title="Print / Save PDF">Print&nbsp;/&nbsp;PDF</button>
      <button class="btn-header" onclick="copyRunId()" title="Copy run ID">Copy&nbsp;Run&nbsp;ID</button>
      <button class="btn-header" id="theme-btn" onclick="toggleTheme()" title="Toggle dark/light theme">Toggle&nbsp;Theme</button>
    </div>
  </div>
</header>

<!-- =====================================================================
     Data blob
     ===================================================================== -->
<script id="PHOENIX_DATA" type="application/json">{data_json}</script>

<main class="main-content">

<!-- =====================================================================
     Section 2 — Summary Cards
     ===================================================================== -->
<section class="cards-section" aria-label="Run summary">
  <div class="cards-grid">

    <div class="card card-accent">
      <div class="card-label">Pass Rate</div>
      <div class="card-value" id="card-pass-rate">{pass_rate:.1f}%</div>
      <div class="card-sub">{pr_arrow}</div>
    </div>

    <div class="card">
      <div class="card-label">Total Tests</div>
      <div class="card-value">{total}</div>
      <div class="card-sub">
        <span class="c-pass">{passed} passed</span>
        &nbsp;/&nbsp;
        <span class="c-fail">{failed} failed</span>
        {f'&nbsp;/ <span class="c-skip">{skipped} skipped</span>' if skipped else ''}
      </div>
    </div>

    <div class="card card-heal">
      <div class="card-label">Healed</div>
      <div class="card-value c-heal">{healed_count}</div>
      <div class="card-sub">({healed_pct:.1f}%) — Phoenix headline metric</div>
    </div>

    <div class="card">
      <div class="card-label">Top Error Type</div>
      <div class="card-value card-value-sm">{html.escape(top_error)}</div>
      <div class="card-sub">{top_error_count} occurrence{"s" if top_error_count != 1 else ""}</div>
    </div>

    <div class="card">
      <div class="card-label">Duration</div>
      <div class="card-value">{duration_display}</div>
      <div class="card-sub">{dur_arrow}</div>
    </div>

  </div>
</section>

<!-- =====================================================================
     Section 3 — Trend Charts (only when ≥ 2 runs)
     ===================================================================== -->
{"" if not has_trends else _build_chart_section()}

<!-- =====================================================================
     Section 4 — Module Breakdown
     ===================================================================== -->
<section class="section" id="section-modules" aria-label="Module breakdown">
  <h2 class="section-title">Module Breakdown</h2>
  <div id="module-bars" class="module-bars"></div>
</section>

<!-- =====================================================================
     Section 5 — Test Results Table
     ===================================================================== -->
<section class="section" id="section-tests" aria-label="Test results">
  <h2 class="section-title">Test Results</h2>

  <div class="filter-bar" id="filter-bar">
    <input
      type="search"
      id="search-input"
      class="search-input"
      placeholder="Search tests…"
      aria-label="Search tests"
    >
    <div class="filter-pills" role="group" aria-label="Filter tests">
      <button class="pill active" data-filter="all">All</button>
      <button class="pill" data-filter="failed">Failed</button>
      <button class="pill" data-filter="healed">Healed</button>
      <button class="pill" data-filter="passed">Passed</button>
      <button class="pill" data-filter="slowest">Slowest 10</button>
    </div>
    <span class="count-label" id="count-label"></span>
    <button class="btn-sm" id="clear-filter-btn" onclick="clearModuleFilter()" style="display:none">
      ✕ Clear module filter
    </button>
  </div>

  <div class="table-wrap">
    <table class="results-table" id="results-table">
      <thead>
        <tr>
          <th style="width:36px"></th>
          <th>Test Name</th>
          <th style="width:110px">Module</th>
          <th style="width:90px">Duration</th>
          <th style="width:80px">Attempts</th>
          <th>Error</th>
          <th style="width:36px"></th>
        </tr>
      </thead>
      <tbody id="results-tbody">
        <!-- populated by JS -->
      </tbody>
    </table>
  </div>
</section>

<!-- =====================================================================
     Section 7 — Healing Insights
     ===================================================================== -->
{_build_healing_section_placeholder(has_healing)}

<!-- =====================================================================
     Section 8 — Failure Analysis
     ===================================================================== -->
{_build_failure_section_placeholder(has_failures)}

<!-- =====================================================================
     Section 9 — Flakiness (only when ≥ 3 runs)
     ===================================================================== -->
{"" if not has_flakiness else _build_flakiness_section_placeholder()}

<!-- =====================================================================
     Section 10 — Footer
     ===================================================================== -->
<footer class="footer">
  Phoenix SmartAutomation
  &nbsp;·&nbsp; Run&nbsp;<code>{html.escape(run_id)}</code>
  &nbsp;·&nbsp; Generated&nbsp;{html.escape(_fmt_dt_now())}
  &nbsp;·&nbsp; Source:&nbsp;logs/
</footer>

</main>

<!-- Detail panel template (hidden, cloned by JS) -->
<template id="detail-tpl">
  <tr class="detail-row" aria-live="polite">
    <td colspan="7">
      <div class="detail-panel">
        <div class="detail-meta"></div>
        <div class="attempt-timeline"></div>
        <pre class="error-block"></pre>
        <div class="screenshot-area"></div>
        <div class="healing-history"></div>
      </div>
    </td>
  </tr>
</template>

<script>{js}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Sub-section builders
# ---------------------------------------------------------------------------

def _build_chart_section() -> str:
    return """
<section class="section" id="section-trends" aria-label="Trend charts">
  <h2 class="section-title">Run Trends</h2>
  <div class="charts-grid">

    <div class="chart-card">
      <h3 class="chart-title">Pass Rate (%)</h3>
      <div class="chart-wrap">
        <canvas id="chart-passrate" aria-label="Pass rate trend"></canvas>
        <div class="chart-offline" id="chart-passrate-offline" style="display:none">
          Charts require internet connection
        </div>
      </div>
    </div>

    <div class="chart-card">
      <h3 class="chart-title">Duration (seconds)</h3>
      <div class="chart-wrap">
        <canvas id="chart-duration" aria-label="Duration trend"></canvas>
        <div class="chart-offline" id="chart-duration-offline" style="display:none">
          Charts require internet connection
        </div>
      </div>
    </div>

    <div class="chart-card">
      <h3 class="chart-title">Healing Activity</h3>
      <div class="chart-wrap">
        <canvas id="chart-healing" aria-label="Healing activity"></canvas>
        <div class="chart-offline" id="chart-healing-offline" style="display:none">
          Charts require internet connection
        </div>
      </div>
    </div>

  </div>
</section>
"""


def _build_healing_section_placeholder(has_healing: bool) -> str:
    cls = "" if has_healing else ' style="display:none"'
    return f"""
<section class="section" id="section-healing" aria-label="Healing insights"{cls}>
  <h2 class="section-title">Phoenix Healing Activity</h2>
  <p class="section-desc">Errors encountered and how many resolved through healing</p>
  <div id="healing-bars" class="module-bars"></div>
</section>
"""


def _build_failure_section_placeholder(has_failures: bool) -> str:
    cls = "" if has_failures else ' style="display:none"'
    return f"""
<section class="section" id="section-failures" aria-label="Failure analysis"{cls}>
  <h2 class="section-title">Failure Analysis</h2>
  <div id="failure-groups"></div>
</section>
"""


def _build_flakiness_section_placeholder() -> str:
    return """
<section class="section" id="section-flakiness" aria-label="Flakiness">
  <h2 class="section-title">Flakiness Report</h2>
  <p class="section-desc">Tests with mixed pass/fail outcomes across recent runs</p>
  <div id="flakiness-content"></div>
</section>
"""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def _build_css() -> str:
    return """
/* =========================================================================
   CSS Custom Properties
   ========================================================================= */
:root {
  --bg: #f8fafc;
  --card: #ffffff;
  --border: #e2e8f0;
  --text: #0f172a;
  --text-2: #475569;
  --pass: #10b981;
  --heal: #f59e0b;
  --fail: #ef4444;
  --skip: #94a3b8;
  --accent: #6366f1;
  --header-bg: #ffffff;
  --header-border: #e2e8f0;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 8px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: 'Consolas', 'JetBrains Mono', monospace;
}

html.dark {
  --bg: #020617;
  --card: #0f172a;
  --border: #1e293b;
  --text: #f1f5f9;
  --text-2: #94a3b8;
  --header-bg: #0f172a;
  --header-border: #1e293b;
  --shadow: 0 1px 3px rgba(0,0,0,0.4);
}

@media (prefers-color-scheme: dark) {
  :root:not(.light) {
    --bg: #020617;
    --card: #0f172a;
    --border: #1e293b;
    --text: #f1f5f9;
    --text-2: #94a3b8;
    --header-bg: #0f172a;
    --header-border: #1e293b;
    --shadow: 0 1px 3px rgba(0,0,0,0.4);
  }
}

/* =========================================================================
   Reset & Base
   ========================================================================= */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  min-height: 100vh;
}

code, pre {
  font-family: var(--mono);
  font-size: 0.85em;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* =========================================================================
   Header
   ========================================================================= */
.top-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 56px;
  background: var(--header-bg);
  border-bottom: 1px solid var(--header-border);
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.top-bar-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 20px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.top-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.project-name {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--accent);
  white-space: nowrap;
}

.run-id-label { font-size: 0.82rem; color: var(--text-2); white-space: nowrap; }
.ts-label { font-size: 0.82rem; color: var(--text-2); white-space: nowrap; }
.separator { color: var(--border); }
.watermark { font-size: 0.72rem; color: var(--text-2); margin-left: 8px; opacity: 0.7; }

.top-bar-right { display: flex; gap: 6px; flex-shrink: 0; }

.btn-header {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text);
  cursor: pointer;
  font-size: 0.78rem;
  padding: 4px 10px;
  transition: background 0.15s;
  white-space: nowrap;
}
.btn-header:hover { background: var(--border); }

/* Environment badge */
.env-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.env-qa      { background: #3b82f622; color: #3b82f6; }
.env-staging { background: #f59e0b22; color: #d97706; }
.env-prod    { background: #ef444422; color: #ef4444; }
.env-other   { background: #94a3b822; color: #64748b; }

/* =========================================================================
   Main Layout
   ========================================================================= */
.main-content {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 20px 40px;
}

.section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 4px;
}

.section-desc {
  font-size: 0.82rem;
  color: var(--text-2);
  margin-bottom: 12px;
}

/* =========================================================================
   Cards
   ========================================================================= */
.cards-section { margin: 20px 0 28px; }

.cards-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

@media (max-width: 900px) {
  .cards-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 540px) {
  .cards-grid { grid-template-columns: repeat(2, 1fr); }
}

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.card-accent { border-top: 3px solid var(--accent); }
.card-heal   { border-top: 3px solid var(--heal); }

.card-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
}
.card-value {
  font-size: 2rem;
  font-weight: 800;
  line-height: 1;
  color: var(--text);
}
.card-value-sm {
  font-size: 1.1rem;
  word-break: break-all;
}
.card-sub {
  font-size: 0.78rem;
  color: var(--text-2);
  margin-top: 2px;
}

/* Color helpers */
.c-pass  { color: var(--pass); }
.c-fail  { color: var(--fail); }
.c-heal  { color: var(--heal); }
.c-skip  { color: var(--skip); }
.c-accent { color: var(--accent); }

.trend-up   { color: var(--pass); font-size: 0.8rem; }
.trend-down { color: var(--fail); font-size: 0.8rem; }
.trend-flat { color: var(--text-2); font-size: 0.8rem; }

/* =========================================================================
   Charts
   ========================================================================= */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
@media (max-width: 768px) {
  .charts-grid { grid-template-columns: 1fr; }
}

.chart-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px;
}
.chart-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-2);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.chart-wrap {
  position: relative;
  height: 200px;
}
.chart-wrap canvas { width: 100% !important; height: 100% !important; }
.chart-offline {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-2);
  font-size: 0.82rem;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: 4px;
}

/* =========================================================================
   Module Bars
   ========================================================================= */
.module-bars { display: flex; flex-direction: column; gap: 8px; }

.module-bar-row {
  display: grid;
  grid-template-columns: 130px 1fr 120px 24px;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 0;
}
.module-bar-row:hover .module-name { color: var(--accent); }

.module-name {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
}
.module-bar-track {
  height: 14px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.module-bar-fill {
  height: 100%;
  border-radius: 4px;
}
.module-bar-label {
  font-size: 0.78rem;
  color: var(--text-2);
  text-align: right;
  white-space: nowrap;
}
.module-warn { color: var(--heal); font-size: 0.9rem; }

/* Healing bars (Section 7) */
.heal-bar-row {
  display: grid;
  grid-template-columns: 160px 1fr 60px 100px;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}
.heal-bar-name { font-size: 0.82rem; font-weight: 600; color: var(--text); }
.heal-bar-track {
  height: 10px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.heal-bar-fill {
  height: 100%;
  background: var(--heal);
  border-radius: 4px;
}
.heal-bar-count { font-size: 0.78rem; color: var(--text-2); text-align: right; }
.heal-bar-detail { font-size: 0.75rem; color: var(--text-2); }

/* =========================================================================
   Filter Bar
   ========================================================================= */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.search-input {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text);
  font-size: 0.85rem;
  padding: 6px 10px;
  width: 220px;
  outline: none;
}
.search-input:focus { border-color: var(--accent); }

.filter-pills { display: flex; gap: 6px; }
.pill {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--text-2);
  cursor: pointer;
  font-size: 0.78rem;
  padding: 3px 12px;
  transition: all 0.15s;
  white-space: nowrap;
}
.pill:hover { border-color: var(--accent); color: var(--accent); }
.pill.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.count-label { font-size: 0.78rem; color: var(--text-2); }

.btn-sm {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-2);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 3px 8px;
}
.btn-sm:hover { border-color: var(--fail); color: var(--fail); }

/* =========================================================================
   Results Table
   ========================================================================= */
.table-wrap {
  overflow-x: auto;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--card);
  /* NOTE: no overflow:hidden here — it breaks position:sticky on thead */
}

.results-table th {
  background: var(--border);
  color: var(--text-2);
  font-size: 0.72rem;
  font-weight: 600;
  padding: 9px 12px;
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  border-bottom: 2px solid var(--accent);
  position: sticky;
  top: 0;
  z-index: 2;
}
.results-table td {
  padding: 9px 12px;
  border-top: 1px solid var(--border);
  font-size: 0.83rem;
  vertical-align: middle;
}
.results-table tbody tr { background: var(--card); }
.results-table tbody tr:hover td { background: color-mix(in srgb, var(--accent) 4%, var(--card)); }

/* Status icons */
.icon-pass   { color: var(--pass); font-size: 1rem; }
.icon-heal   { color: var(--heal); font-size: 1rem; }
.icon-fail   { color: var(--fail); font-size: 1rem; }
.icon-skip   { color: var(--skip); font-size: 1rem; }
.icon-error  { color: #f97316; font-size: 1rem; }

.test-name-cell {
  max-width: 280px;
  word-break: break-word;
  font-weight: 500;
}
.module-tag {
  display: inline-block;
  background: var(--border);
  border-radius: 4px;
  font-size: 0.72rem;
  padding: 1px 7px;
  color: var(--text-2);
}
.error-cell {
  color: var(--text-2);
  font-size: 0.78rem;
  max-width: 260px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.expand-btn {
  background: transparent;
  border: none;
  color: var(--text-2);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 6px;
  border-radius: 4px;
  transition: transform 0.2s;
}
.expand-btn:hover { color: var(--accent); }
.expand-btn.open { transform: rotate(90deg); color: var(--accent); }

/* =========================================================================
   Detail Panel (Section 6)
   ========================================================================= */
.detail-row td { padding: 0; }
.detail-panel {
  background: color-mix(in srgb, var(--accent) 3%, var(--card));
  border-left: 3px solid var(--accent);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-meta {
  font-size: 0.82rem;
  color: var(--text-2);
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.detail-meta span { display: flex; align-items: center; gap: 4px; }

/* Attempt timeline */
.attempt-timeline {
  display: flex;
  align-items: center;
  gap: 0;
  flex-wrap: wrap;
}
.attempt-node {
  display: flex;
  align-items: center;
  gap: 4px;
}
.attempt-bubble {
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  flex-shrink: 0;
}
.attempt-bubble.pass { background: #10b98122; color: var(--pass); border: 2px solid var(--pass); }
.attempt-bubble.fail { background: #ef444422; color: var(--fail); border: 2px solid var(--fail); }
.attempt-bubble.error { background: #f9731622; color: #f97316; border: 2px solid #f97316; }
.attempt-bubble.skip { background: #94a3b822; color: var(--skip); border: 2px solid var(--skip); }

.attempt-info {
  font-size: 0.72rem;
  color: var(--text-2);
  text-align: center;
  max-width: 70px;
}
.attempt-connector {
  width: 24px;
  height: 2px;
  background: var(--border);
  flex-shrink: 0;
}

.error-block {
  background: color-mix(in srgb, var(--fail) 5%, var(--bg));
  border: 1px solid color-mix(in srgb, var(--fail) 20%, var(--border));
  border-radius: 5px;
  color: var(--text);
  font-size: 0.78rem;
  max-height: 200px;
  overflow-y: auto;
  padding: 10px 14px;
  white-space: pre-wrap;
  word-break: break-word;
}
.error-block:empty { display: none; }

.screenshot-area img {
  max-width: 320px;
  max-height: 200px;
  border-radius: 4px;
  border: 1px solid var(--border);
  display: block;
}

/* Healing history inside detail */
.healing-history-table {
  font-size: 0.78rem;
  border-collapse: collapse;
  width: 100%;
}
.healing-history-table th {
  color: var(--text-2);
  font-weight: 600;
  text-align: left;
  padding: 4px 8px;
  background: var(--border);
}
.healing-history-table td {
  padding: 4px 8px;
  border-top: 1px solid var(--border);
}

/* =========================================================================
   Failure Groups (Section 8)
   ========================================================================= */
.failure-groups { display: flex; flex-direction: column; gap: 16px; }
.failure-group {
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--fail);
  border-radius: var(--radius);
  padding: 14px 16px;
}
.failure-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.error-type-badge {
  background: #ef444422;
  color: var(--fail);
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 2px 8px;
}
.failure-count { font-size: 0.82rem; color: var(--text-2); }
.failure-test-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.failure-test-list li {
  font-size: 0.82rem;
  color: var(--text);
  padding-left: 10px;
  border-left: 2px solid var(--fail);
}

/* =========================================================================
   Flakiness (Section 9)
   ========================================================================= */
.flaky-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--card);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
}
.flaky-table th {
  background: var(--border);
  color: var(--text-2);
  font-size: 0.72rem;
  font-weight: 600;
  padding: 8px 12px;
  text-align: left;
  text-transform: uppercase;
}
.flaky-table td {
  padding: 8px 12px;
  border-top: 1px solid var(--border);
  font-size: 0.82rem;
}
.run-dots { display: flex; gap: 3px; flex-wrap: wrap; }
.run-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.run-dot.pass { background: var(--pass); }
.run-dot.fail { background: var(--fail); }

/* =========================================================================
   Footer
   ========================================================================= */
.footer {
  border-top: 1px solid var(--border);
  color: var(--text-2);
  font-size: 0.75rem;
  margin-top: 40px;
  padding-top: 16px;
  text-align: center;
}

/* =========================================================================
   Print
   ========================================================================= */
@media print {
  .top-bar { position: static; box-shadow: none; }
  .btn-header, #filter-bar { display: none !important; }
  .detail-panel { display: flex !important; }
  .main-content { padding: 0; }
  .detail-row { break-inside: avoid; }
  .chart-offline { display: flex !important; }
  canvas { display: none !important; }
}
"""


# ---------------------------------------------------------------------------
# JS
# ---------------------------------------------------------------------------

def _build_js() -> str:
    return r"""
/* =========================================================================
   Phoenix Report — Vanilla JS
   ========================================================================= */
'use strict';

// -------------------------------------------------------------------------
// Data
// -------------------------------------------------------------------------
const DATA = JSON.parse(document.getElementById('PHOENIX_DATA').textContent);

// -------------------------------------------------------------------------
// Theme
// -------------------------------------------------------------------------
(function initTheme() {
  const stored = localStorage.getItem('phoenix-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (stored === 'dark' || (!stored && prefersDark)) {
    document.documentElement.classList.add('dark');
  } else if (stored === 'light') {
    document.documentElement.classList.remove('dark');
  }
})();

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('phoenix-theme', isDark ? 'dark' : 'light');
}

// -------------------------------------------------------------------------
// Copy Run ID
// -------------------------------------------------------------------------
function copyRunId() {
  const text = DATA.run_id;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => flashMsg('Run ID copied!'));
  } else {
    const el = document.createElement('textarea');
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    flashMsg('Run ID copied!');
  }
}

function flashMsg(msg) {
  const el = document.createElement('div');
  el.textContent = msg;
  el.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#6366f1;color:#fff;padding:8px 14px;border-radius:6px;font-size:0.82rem;z-index:9999;pointer-events:none;opacity:1;transition:opacity 0.5s';
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 600); }, 1800);
}

// -------------------------------------------------------------------------
// Status helpers
// -------------------------------------------------------------------------
function statusIcon(row) {
  if (row.healed) return '<span class="icon-heal" title="Healed — passed after retry">⚡</span>';
  switch (row.status) {
    case 'passed':  return '<span class="icon-pass" title="Passed">✓</span>';
    case 'failed':  return '<span class="icon-fail" title="Failed">✕</span>';
    case 'error':   return '<span class="icon-error" title="Error">⚠</span>';
    case 'skipped': return '<span class="icon-skip" title="Skipped">⊘</span>';
    default:        return '<span>?</span>';
  }
}

function fmtDuration(s) {
  if (s == null || s === 0) return '—';
  if (s < 60) return s.toFixed(1) + 's';
  const m = Math.floor(s / 60);
  const r = (s % 60).toFixed(0);
  return m + 'm ' + r + 's';
}

function esc(s) {
  if (!s) return '';
  return s.toString()
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

// -------------------------------------------------------------------------
// Module Breakdown (Section 4)
// -------------------------------------------------------------------------
function renderModuleBars(filterModule) {
  const container = document.getElementById('module-bars');
  if (!container) return;
  const rows = DATA.module_breakdown;
  if (!rows || rows.length === 0) {
    container.innerHTML = '<p style="color:var(--text-2);font-size:0.82rem">No module data.</p>';
    return;
  }
  const maxTotal = Math.max(...rows.map(r => r.total), 1);
  container.innerHTML = rows.map(r => {
    const pct = r.total > 0 ? r.total / maxTotal * 100 : 0;
    const passW  = r.total > 0 ? (r.passed  / r.total * 100) : 0;
    const healW  = r.total > 0 ? (r.healed  / r.total * 100) : 0;
    const failW  = r.total > 0 ? (r.failed  / r.total * 100) : 0;
    const passRate = r.total > 0 ? ((r.passed + r.healed) / r.total * 100) : 0;
    const warn = passRate < 70 ? '<span class="module-warn" title="Pass rate < 70%">⚠</span>' : '';
    const active = filterModule === r.module ? 'style="color:var(--accent)"' : '';
    const gradient = `linear-gradient(to right, var(--pass) ${passW}%, var(--heal) ${passW}% ${passW+healW}%, var(--fail) ${passW+healW}% ${passW+healW+failW}%, var(--border) ${passW+healW+failW}%)`;
    return `<div class="module-bar-row" onclick="setModuleFilter('${esc(r.module)}')" title="Click to filter: ${esc(r.module)}">
      <span class="module-name" ${active}>${esc(r.module)}</span>
      <div class="module-bar-track"><div class="module-bar-fill" style="width:${pct}%;background:${gradient}"></div></div>
      <span class="module-bar-label">${r.passed + r.healed}/${r.total} (${passRate.toFixed(0)}%)</span>
      ${warn}
    </div>`;
  }).join('');
}

// -------------------------------------------------------------------------
// Filter state
// -------------------------------------------------------------------------
let activeFilter = 'all';
let activeModule = null;
let searchTerm = '';
let searchTimer = null;

function setModuleFilter(mod) {
  if (activeModule === mod) {
    activeModule = null;
    document.getElementById('clear-filter-btn').style.display = 'none';
  } else {
    activeModule = mod;
    document.getElementById('clear-filter-btn').style.display = '';
  }
  renderModuleBars(activeModule);
  renderTable();
}

function clearModuleFilter() {
  activeModule = null;
  document.getElementById('clear-filter-btn').style.display = 'none';
  renderModuleBars(null);
  renderTable();
}

function filterTests(tests) {
  let result = tests;
  // Module filter
  if (activeModule) {
    result = result.filter(t => t.module === activeModule);
  }
  // Search
  if (searchTerm) {
    const q = searchTerm.toLowerCase();
    result = result.filter(t =>
      t.test_name.toLowerCase().includes(q) ||
      (t.module && t.module.toLowerCase().includes(q)) ||
      (t.error_type && t.error_type.toLowerCase().includes(q))
    );
  }
  // Pill filter
  if (activeFilter === 'failed') {
    result = result.filter(t => t.status === 'failed' || t.status === 'error');
  } else if (activeFilter === 'healed') {
    result = result.filter(t => t.healed);
  } else if (activeFilter === 'passed') {
    result = result.filter(t => t.status === 'passed' && !t.healed);
  } else if (activeFilter === 'slowest') {
    result = [...result].sort((a, b) => b.duration_seconds - a.duration_seconds).slice(0, 10);
  }
  return result;
}

// -------------------------------------------------------------------------
// Test Table (Section 5)
// -------------------------------------------------------------------------
function renderTable() {
  const tbody = document.getElementById('results-tbody');
  if (!tbody) return;

  const filtered = filterTests(DATA.per_test || []);
  const total = (DATA.per_test || []).length;
  const label = document.getElementById('count-label');
  if (label) label.textContent = `Showing ${filtered.length} of ${total} tests`;

  tbody.innerHTML = '';
  filtered.forEach((row, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.idx = idx;
    tr.dataset.testName = row.test_name;
    const errTxt = row.error_message ? esc(row.error_message.slice(0, 80)) : '';
    const errCell = errTxt ? `<span title="${esc(row.error_message)}">${errTxt}…</span>` : '';
    tr.innerHTML = `
      <td>${statusIcon(row)}</td>
      <td class="test-name-cell">${esc(row.test_name)}</td>
      <td><span class="module-tag">${esc(row.module)}</span></td>
      <td>${fmtDuration(row.duration_seconds)}</td>
      <td style="text-align:center">${row.total_attempts}</td>
      <td class="error-cell">${errCell}</td>
      <td><button class="expand-btn" aria-expanded="false" aria-label="Expand details" onclick="toggleDetail(this, ${JSON.stringify(row.test_name)})">▶</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// -------------------------------------------------------------------------
// Test Detail Expansion (Section 6)
// -------------------------------------------------------------------------
const openDetails = new Set();

function toggleDetail(btn, testName) {
  const tr = btn.closest('tr');
  const existingDetail = tr.nextSibling;

  if (existingDetail && existingDetail.classList && existingDetail.classList.contains('detail-row')) {
    existingDetail.remove();
    btn.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
    openDetails.delete(testName);
    return;
  }

  btn.classList.add('open');
  btn.setAttribute('aria-expanded', 'true');
  openDetails.add(testName);

  const row = (DATA.per_test || []).find(t => t.test_name === testName);
  if (!row) return;

  const tpl = document.getElementById('detail-tpl');
  const clone = tpl.content.cloneNode(true);
  const detailTr = clone.querySelector('.detail-row');

  // Meta
  const meta = detailTr.querySelector('.detail-meta');
  meta.innerHTML = `
    <span>📄 <strong>File:</strong> ${esc(row.test_path)}</span>
    <span>🧩 <strong>Module:</strong> ${esc(row.module)}</span>
  `;

  // Attempt timeline
  const timeline = detailTr.querySelector('.attempt-timeline');
  const atts = row.all_attempts || [];
  timeline.innerHTML = atts.map((a, i) => {
    const cls = a.status === 'passed' ? 'pass' : a.status === 'error' ? 'error' : a.status === 'skipped' ? 'skip' : 'fail';
    const label = a.error_type ? a.error_type.slice(0, 12) : a.status;
    const connector = i < atts.length - 1 ? '<div class="attempt-connector"></div>' : '';
    return `<div class="attempt-node">
      <div class="attempt-bubble ${cls}" title="${esc(a.error_type || a.status)}">${a.attempt}</div>
      <div class="attempt-info">${esc(label)}<br>${fmtDuration(a.duration_seconds)}</div>
    </div>${connector}`;
  }).join('');

  // Error block
  const errBlock = detailTr.querySelector('.error-block');
  const lastFailed = atts.slice().reverse().find(a => a.status !== 'passed');
  if (lastFailed && lastFailed.error_message) {
    errBlock.textContent = lastFailed.error_message;
  }

  // Screenshot
  const shotArea = detailTr.querySelector('.screenshot-area');
  if (row.screenshot_path) {
    const href = row.screenshot_path.replace(/\\/g, '/');
    shotArea.innerHTML = `<a href="${esc(href)}" target="_blank">
      <img src="${esc(href)}" alt="Screenshot" onerror="this.parentElement.innerHTML='<a href=&quot;${esc(href)}&quot; target=&quot;_blank&quot;>📷 View screenshot</a>'">
    </a>`;
  }

  // Healing history table
  const healDiv = detailTr.querySelector('.healing-history');
  if (atts.length > 1) {
    healDiv.innerHTML = `<table class="healing-history-table">
      <thead><tr><th>#</th><th>Status</th><th>Error Type</th><th>Duration</th></tr></thead>
      <tbody>
        ${atts.map(a => `<tr>
          <td>${a.attempt}</td>
          <td>${esc(a.status)}</td>
          <td>${esc(a.error_type || '—')}</td>
          <td>${fmtDuration(a.duration_seconds)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  }

  tr.after(detailTr);
}

// -------------------------------------------------------------------------
// Healing Insights (Section 7)
// -------------------------------------------------------------------------
function renderHealingBars() {
  const container = document.getElementById('healing-bars');
  if (!container) return;
  const data = DATA.error_type_healing || {};
  const entries = Object.entries(data);
  if (entries.length === 0) return;
  const maxCount = Math.max(...entries.map(([, v]) => v.count), 1);
  container.innerHTML = entries.map(([et, v]) => {
    const pct = v.count / maxCount * 100;
    return `<div class="heal-bar-row">
      <span class="heal-bar-name">${esc(et)}</span>
      <div class="heal-bar-track"><div class="heal-bar-fill" style="width:${pct}%"></div></div>
      <span class="heal-bar-count">${v.count}</span>
      <span class="heal-bar-detail c-heal">${v.healed} healed</span>
    </div>`;
  }).join('');
}

// -------------------------------------------------------------------------
// Failure Analysis (Section 8)
// -------------------------------------------------------------------------
function renderFailureGroups() {
  const container = document.getElementById('failure-groups');
  if (!container) return;
  const tests = (DATA.per_test || []).filter(t => t.status === 'failed' || t.status === 'error');
  if (tests.length === 0) return;

  // Group by error_type
  const groups = {};
  tests.forEach(t => {
    const key = t.error_type || 'unknown';
    if (!groups[key]) groups[key] = [];
    groups[key].push(t.test_name);
  });

  container.innerHTML = Object.entries(groups).map(([et, names]) => `
    <div class="failure-group">
      <div class="failure-group-header">
        <span class="error-type-badge">${esc(et)}</span>
        <span class="failure-count">${names.length} test${names.length !== 1 ? 's' : ''}</span>
      </div>
      <ul class="failure-test-list">
        ${names.map(n => `<li>${esc(n)}</li>`).join('')}
      </ul>
    </div>
  `).join('');
}

// -------------------------------------------------------------------------
// Flakiness (Section 9)
// -------------------------------------------------------------------------
function renderFlakiness() {
  const container = document.getElementById('flakiness-content');
  if (!container) return;
  const tests = DATA.flaky_tests || [];
  if (tests.length === 0) {
    container.innerHTML = '<p style="color:var(--text-2);font-size:0.82rem">No flaky tests detected in the loaded runs.</p>';
    return;
  }
  const rows = tests.map(t => {
    const dots = (t.runs_history || []).slice(-10).map(s =>
      `<span class="run-dot ${s}" title="${s}"></span>`
    ).join('');
    return `<tr>
      <td>${esc(t.test_name)}</td>
      <td><div class="run-dots">${dots}</div></td>
      <td>${t.flake_rate.toFixed(1)}%</td>
      <td>${t.total_runs}</td>
    </tr>`;
  }).join('');

  container.innerHTML = `<table class="flaky-table">
    <thead><tr><th>Test Name</th><th>Last 10 Runs</th><th>Flake Rate</th><th>Total Runs</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// -------------------------------------------------------------------------
// Charts (Section 3)
// -------------------------------------------------------------------------
let chartJsLoaded = false;

function initCharts() {
  const canvas1 = document.getElementById('chart-passrate');
  if (!canvas1) return;  // No chart section in DOM

  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
  script.onload = function() {
    chartJsLoaded = true;
    buildCharts();
  };
  script.onerror = function() {
    ['chart-passrate', 'chart-duration', 'chart-healing'].forEach(id => {
      const c = document.getElementById(id);
      const off = document.getElementById(id + '-offline');
      if (c) c.style.display = 'none';
      if (off) off.style.display = 'flex';
    });
  };
  document.head.appendChild(script);
}

function chartLabels(arr) {
  return arr.map(r => {
    if (!r.started_at) return r.run_id ? r.run_id.slice(0,6) : '?';
    try {
      const d = new Date(r.started_at);
      return d.toLocaleDateString('en-US', {month:'short', day:'numeric'}) + ' ' + d.toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit', hour12:false});
    } catch(e) { return r.run_id ? r.run_id.slice(0,6) : '?'; }
  });
}

function getCssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function buildCharts() {
  const textColor = getCssVar('--text-2') || '#475569';
  const borderColor = getCssVar('--border') || '#e2e8f0';
  const passColor = getCssVar('--pass') || '#10b981';
  const healColor = getCssVar('--heal') || '#f59e0b';
  const failColor = getCssVar('--fail') || '#ef4444';
  const accentColor = getCssVar('--accent') || '#6366f1';

  const baseOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: textColor, font: { size: 11 } } },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: { ticks: { color: textColor, font: { size: 10 }, maxRotation: 45 }, grid: { color: borderColor } },
      y: { ticks: { color: textColor, font: { size: 11 } }, grid: { color: borderColor } },
    },
  };

  // -- Pass Rate Chart --
  const prData = DATA.trend_pass_rate || [];
  if (prData.length >= 2) {
    const ctx1 = document.getElementById('chart-passrate');
    if (ctx1) {
      new Chart(ctx1, {
        type: 'line',
        data: {
          labels: chartLabels(prData),
          datasets: [
            {
              label: 'Pass Rate %',
              data: prData.map(r => r.pass_rate),
              borderColor: accentColor,
              backgroundColor: accentColor + '22',
              fill: true,
              tension: 0.3,
              pointRadius: 4,
            },
            {
              label: '70% Target',
              data: prData.map(() => 70),
              borderColor: healColor,
              borderDash: [6, 4],
              borderWidth: 1.5,
              pointRadius: 0,
              fill: false,
            },
          ],
        },
        options: { ...baseOpts, scales: { ...baseOpts.scales, y: { ...baseOpts.scales.y, min: 0, max: 100 } } },
      });
    }
  }

  // -- Duration Chart --
  const durData = DATA.trend_duration || [];
  if (durData.length >= 2) {
    const ctx2 = document.getElementById('chart-duration');
    if (ctx2) {
      new Chart(ctx2, {
        type: 'line',
        data: {
          labels: chartLabels(durData),
          datasets: [{
            label: 'Duration (s)',
            data: durData.map(r => r.duration_seconds),
            borderColor: '#60a5fa',
            backgroundColor: '#60a5fa22',
            fill: true,
            tension: 0.3,
            pointRadius: 4,
          }],
        },
        options: baseOpts,
      });
    }
  }

  // -- Healing Activity Chart --
  const healData = DATA.trend_healing || [];
  if (healData.length >= 2) {
    const ctx3 = document.getElementById('chart-healing');
    if (ctx3) {
      new Chart(ctx3, {
        type: 'bar',
        data: {
          labels: chartLabels(healData),
          datasets: [
            { label: 'Passed (1st try)', data: healData.map(r => r.passed_first), backgroundColor: passColor + 'cc' },
            { label: 'Healed', data: healData.map(r => r.healed), backgroundColor: healColor + 'cc' },
            { label: 'Failed', data: healData.map(r => r.failed), backgroundColor: failColor + 'cc' },
          ],
        },
        options: { ...baseOpts, scales: { ...baseOpts.scales, x: { ...baseOpts.scales.x, stacked: true }, y: { ...baseOpts.scales.y, stacked: true } } },
      });
    }
  }
}

// -------------------------------------------------------------------------
// Filter pill wiring
// -------------------------------------------------------------------------
document.querySelectorAll('.pill').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    renderTable();
  });
});

const searchInput = document.getElementById('search-input');
if (searchInput) {
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchTerm = searchInput.value.trim();
      renderTable();
    }, 200);
  });
}

// -------------------------------------------------------------------------
// Init
// -------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function() {
  renderModuleBars(null);
  renderTable();
  renderHealingBars();
  renderFailureGroups();
  renderFlakiness();
  initCharts();
});
"""


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _fmt_dt(iso_str: str) -> str:
    """Format an ISO datetime string for display."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %-d, %Y · %H:%M")
    except Exception:
        try:
            # Fallback: strptime without timezone
            dt = datetime.strptime(iso_str[:19], "%Y-%m-%dT%H:%M:%S")
            return dt.strftime("%b %d, %Y · %H:%M")
        except Exception:
            return iso_str[:19].replace("T", " ")


def _fmt_dt_now() -> str:
    """Current datetime formatted for display."""
    return datetime.now().strftime("%b %d, %Y · %H:%M")


def _fmt_duration(seconds: float) -> str:
    """Format duration seconds as 'Xm Ys' or 'Xs'."""
    if seconds is None or seconds == 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}m {s:.0f}s"
