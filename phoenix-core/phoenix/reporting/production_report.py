"""Production Report Generator - HTML reports with comprehensive metrics.

Generates detailed HTML reports containing all Phoenix subsystem metrics,
healing statistics, browser pool utilization, circuit breaker status,
and execution results.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ProductionReportGenerator:
    """Generate comprehensive HTML production reports."""
    
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Production Report Generator initialized: %s", self.output_dir)
    
    def generate_report(
        self,
        metrics: Any,
        test_results: Optional[Dict[str, Any]] = None,
        execution_log: Optional[str] = None,
    ) -> str:
        """Generate comprehensive HTML production report.
        
        Args:
            metrics: ProductionMetrics object
            test_results: Optional test execution results
            execution_log: Optional execution log text
            
        Returns:
            Path to generated HTML report
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.output_dir / f"production_report_{timestamp}.html"
        
        html_content = self._generate_html(metrics, test_results, execution_log)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info("Production report generated: %s", report_path)
        return str(report_path)
    
    def _generate_html(
        self,
        metrics: Any,
        test_results: Optional[Dict[str, Any]] = None,
        execution_log: Optional[str] = None,
    ) -> str:
        """Generate HTML content for the report."""
        
        # Summary calculations
        healing_success_rate = (
            metrics.healing_successful / metrics.healing_total_attempts * 100
            if metrics.healing_total_attempts > 0 else 0
        )
        browser_reuse_rate = (
            metrics.browser_reuse_count / metrics.browser_total_created * 100
            if metrics.browser_total_created > 0 else 0
        )
        test_pass_rate = (
            metrics.passed_tests / metrics.total_tests * 100
            if metrics.total_tests > 0 else 0
        )
        mcp_success_rate = (
            metrics.mcp_success_count / metrics.mcp_call_count * 100
            if metrics.mcp_call_count > 0 else 0
        )
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phoenix Production Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-card.success {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .metric-card.warning {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .metric-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .metric-card .value {{
            font-size: 32px;
            font-weight: bold;
        }}
        .metric-card .unit {{
            font-size: 14px;
            opacity: 0.8;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .status-pass {{
            color: #27ae60;
            font-weight: bold;
        }}
        .status-fail {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .status-warning {{
            color: #f39c12;
            font-weight: bold;
        }}
        .log-section {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #7f8c8d;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Phoenix Production Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>📊 Executive Summary</h2>
        <div class="summary">
            <div class="metric-card success">
                <h3>Test Pass Rate</h3>
                <div class="value">{test_pass_rate:.1f}</div>
                <div class="unit">%</div>
            </div>
            <div class="metric-card">
                <h3>Healing Success Rate</h3>
                <div class="value">{healing_success_rate:.1f}</div>
                <div class="unit">%</div>
            </div>
            <div class="metric-card">
                <h3>Browser Reuse Rate</h3>
                <div class="value">{browser_reuse_rate:.1f}</div>
                <div class="unit">%</div>
            </div>
            <div class="metric-card">
                <h3>DOM Cache Hit Ratio</h3>
                <div class="value">{metrics.dom_cache_hit_ratio:.2f}</div>
                <div class="unit">%</div>
            </div>
            <div class="metric-card">
                <h3>MCP Success Rate</h3>
                <div class="value">{mcp_success_rate:.1f}</div>
                <div class="unit">%</div>
            </div>
            <div class="metric-card warning">
                <h3>Circuit State</h3>
                <div class="value">{metrics.circuit_state.upper()}</div>
                <div class="unit">Status</div>
            </div>
        </div>
        
        <h2>🧪 Test Execution</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>Total Tests</td>
                <td>{metrics.total_tests}</td>
                <td>-</td>
            </tr>
            <tr>
                <td>Passed</td>
                <td>{metrics.passed_tests}</td>
                <td class="status-pass">✓ PASS</td>
            </tr>
            <tr>
                <td>Failed</td>
                <td>{metrics.failed_tests}</td>
                <td class="status-fail">✗ FAIL</td>
            </tr>
            <tr>
                <td>Skipped</td>
                <td>{metrics.skipped_tests}</td>
                <td class="status-warning">⊘ SKIP</td>
            </tr>
            <tr>
                <td>Total Execution Time</td>
                <td>{metrics.total_execution_time_ms / 1000:.2f}s</td>
                <td>-</td>
            </tr>
            <tr>
                <td>Average Test Time</td>
                <td>{metrics.average_test_time_ms / 1000:.2f}s</td>
                <td>-</td>
            </tr>
        </table>
        
        <h2>🔧 Healing Engine</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Healing Attempts</td>
                <td>{metrics.healing_total_attempts}</td>
            </tr>
            <tr>
                <td>Successful Healings</td>
                <td>{metrics.healing_successful}</td>
            </tr>
            <tr>
                <td>Failed Healings</td>
                <td>{metrics.healing_failed}</td>
            </tr>
            <tr>
                <td>Cache Hits</td>
                <td>{metrics.healing_cache_hits}</td>
            </tr>
            <tr>
                <td>Cache Misses</td>
                <td>{metrics.healing_cache_misses}</td>
            </tr>
            <tr>
                <td>Total Healing Time</td>
                <td>{metrics.healing_total_time_ms:.0f}ms</td>
            </tr>
        </table>
        
        <h2>🌐 Browser Pool</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Browsers Created</td>
                <td>{metrics.browser_total_created}</td>
            </tr>
            <tr>
                <td>Total Browsers Closed</td>
                <td>{metrics.browser_total_closed}</td>
            </tr>
            <tr>
                <td>Active Browsers</td>
                <td>{metrics.browser_active}</td>
            </tr>
            <tr>
                <td>Browser Reuse Count</td>
                <td>{metrics.browser_reuse_count}</td>
            </tr>
            <tr>
                <td>Total Contexts Created</td>
                <td>{metrics.context_total_created}</td>
            </tr>
            <tr>
                <td>Active Contexts</td>
                <td>{metrics.context_active}</td>
            </tr>
            <tr>
                <td>Context Reuse Count</td>
                <td>{metrics.context_reuse_count}</td>
            </tr>
            <tr>
                <td>Total Pages Created</td>
                <td>{metrics.page_total_created}</td>
            </tr>
            <tr>
                <td>Active Pages</td>
                <td>{metrics.page_active}</td>
            </tr>
            <tr>
                <td>Page Reuse Count</td>
                <td>{metrics.page_reuse_count}</td>
            </tr>
        </table>
        
        <h2>⚡ Circuit Breaker</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Current State</td>
                <td class="status-{'pass' if metrics.circuit_state == 'closed' else 'fail'}">{metrics.circuit_state.upper()}</td>
            </tr>
            <tr>
                <td>Total Failures</td>
                <td>{metrics.circuit_failures}</td>
            </tr>
            <tr>
                <td>Total Successes</td>
                <td>{metrics.circuit_successes}</td>
            </tr>
            <tr>
                <td>Total Events</td>
                <td>{metrics.circuit_total_events}</td>
            </tr>
        </table>
        
        <h2>🔄 Session Recovery</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Recovery Attempts</td>
                <td>{metrics.session_recovery_attempts}</td>
            </tr>
            <tr>
                <td>Successful Recoveries</td>
                <td>{metrics.session_successful}</td>
            </tr>
            <tr>
                <td>Failed Recoveries</td>
                <td>{metrics.session_failed}</td>
            </tr>
            <tr>
                <td>Sessions Saved</td>
                <td>{metrics.session_saved}</td>
            </tr>
            <tr>
                <td>Sessions Restored</td>
                <td>{metrics.session_restored}</td>
            </tr>
            <tr>
                <td>Total Recovery Time</td>
                <td>{metrics.session_recovery_time_ms:.0f}ms</td>
            </tr>
        </table>
        
        <h2>💾 DOM Cache</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Cache Hits</td>
                <td>{metrics.dom_cache_hits}</td>
            </tr>
            <tr>
                <td>Cache Misses</td>
                <td>{metrics.dom_cache_misses}</td>
            </tr>
            <tr>
                <td>Total Entries</td>
                <td>{metrics.dom_cache_entries}</td>
            </tr>
            <tr>
                <td>Total Evictions</td>
                <td>{metrics.dom_cache_evictions}</td>
            </tr>
            <tr>
                <td>Hit Ratio</td>
                <td>{metrics.dom_cache_hit_ratio:.2%}</td>
            </tr>
        </table>
        
        <h2>🤖 MCP Integration</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Calls</td>
                <td>{metrics.mcp_call_count}</td>
            </tr>
            <tr>
                <td>Successful Calls</td>
                <td>{metrics.mcp_success_count}</td>
            </tr>
            <tr>
                <td>Failed Calls</td>
                <td>{metrics.mcp_failure_count}</td>
            </tr>
            <tr>
                <td>Total Time</td>
                <td>{metrics.mcp_total_time_ms:.0f}ms</td>
            </tr>
            <tr>
                <td>Average Time</td>
                <td>{metrics.mcp_average_time_ms:.0f}ms</td>
            </tr>
        </table>
        
        <h2>🧠 LLM Generation</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Calls</td>
                <td>{metrics.llm_call_count}</td>
            </tr>
            <tr>
                <td>Total Time</td>
                <td>{metrics.llm_total_time_ms:.0f}ms</td>
            </tr>
            <tr>
                <td>Average Time</td>
                <td>{metrics.llm_average_time_ms:.0f}ms</td>
            </tr>
        </table>
"""
        
        if execution_log:
            html += f"""
        <h2>📋 Execution Log</h2>
        <div class="log-section">{execution_log}</div>
"""
        
        html += f"""
        <div class="footer">
            <p>Generated by Phoenix Automation Framework - Production Report</p>
            <p>Report ID: {timestamp}</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html