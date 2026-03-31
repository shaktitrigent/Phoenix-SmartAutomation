# Phoenix Intelligence Server Startup Script
# Requires: ANTHROPIC_API_KEY environment variable

$env:PHOENIX_INTELLIGENCE_PORT = "8001"

if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "WARNING: ANTHROPIC_API_KEY is not set." -ForegroundColor Red
    Write-Host "Automation test generation will fail without it." -ForegroundColor Red
    Write-Host 'Set it with: $env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"' -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Starting Phoenix Intelligence Server on port 8001..." -ForegroundColor Green
Write-Host "  LLM Provider: Anthropic Claude" -ForegroundColor Cyan
Write-Host "  LLM Model:    $($env:PHOENIX_LLM_MODEL ?? 'claude-sonnet-4-20250514')" -ForegroundColor Cyan
Write-Host "  MCP Enabled:  $($env:PHOENIX_MCP_ENABLED ?? 'true')" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python api/server.py
