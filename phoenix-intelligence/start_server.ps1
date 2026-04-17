# Phoenix Intelligence Server Startup Script
# Requires: GOOGLE_API_KEY environment variable (for the default Gemini provider)

$env:PHOENIX_INTELLIGENCE_PORT = "8001"

if ([string]::IsNullOrWhiteSpace($env:PHOENIX_LLM_PROVIDER)) {
    $provider = "gemini"
} else {
    $provider = $env:PHOENIX_LLM_PROVIDER
}

if ([string]::IsNullOrWhiteSpace($env:PHOENIX_LLM_MODEL)) {
    $model = "gemini-2.5-flash"
} else {
    $model = $env:PHOENIX_LLM_MODEL
}

if ([string]::IsNullOrWhiteSpace($env:PHOENIX_MCP_ENABLED)) {
    $mcpEnabled = "true"
} else {
    $mcpEnabled = $env:PHOENIX_MCP_ENABLED
}

if (-not $env:GOOGLE_API_KEY) {
    Write-Host "WARNING: GOOGLE_API_KEY is not set." -ForegroundColor Red
    Write-Host "Automation test generation will fail without it." -ForegroundColor Red
    Write-Host 'Set it with: $env:GOOGLE_API_KEY = "your-gemini-api-key"' -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Starting Phoenix Intelligence Server on port 8001..." -ForegroundColor Green
Write-Host "  LLM Provider: $provider" -ForegroundColor Cyan
Write-Host "  LLM Model:    $model" -ForegroundColor Cyan
Write-Host "  MCP Enabled:  $mcpEnabled" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python api/server.py
