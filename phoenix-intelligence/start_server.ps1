# Phoenix Intelligence Server Startup Script
# Requires a provider-specific API key environment variable

$env:PHOENIX_INTELLIGENCE_PORT = "8001"

$provider = if ($env:PHOENIX_LLM_PROVIDER) { $env:PHOENIX_LLM_PROVIDER } else { "anthropic" }

switch ($provider.ToLower()) {
    "gemini" {
        if (-not $env:GOOGLE_API_KEY) {
            Write-Host "WARNING: GOOGLE_API_KEY is not set." -ForegroundColor Red
            Write-Host "Automation test generation will fail without it." -ForegroundColor Red
            Write-Host 'Set it with: $env:GOOGLE_API_KEY = "your-google-api-key"' -ForegroundColor Yellow
            Write-Host ""
        }
        if (-not $env:PHOENIX_LLM_MODEL) { $env:PHOENIX_LLM_MODEL = "gemini-1.5-pro" }
    }
    "openai" {
        if (-not $env:OPENAI_API_KEY) {
            Write-Host "WARNING: OPENAI_API_KEY is not set." -ForegroundColor Red
            Write-Host "Automation test generation will fail without it." -ForegroundColor Red
            Write-Host 'Set it with: $env:OPENAI_API_KEY = "your-openai-api-key"' -ForegroundColor Yellow
            Write-Host ""
        }
        if (-not $env:PHOENIX_LLM_MODEL) { $env:PHOENIX_LLM_MODEL = "gpt-4o" }
    }
    "ollama" {
        if (-not $env:PHOENIX_LLM_MODEL) { $env:PHOENIX_LLM_MODEL = "llama3" }
    }
    default {
        if (-not $env:ANTHROPIC_API_KEY) {
            Write-Host "WARNING: ANTHROPIC_API_KEY is not set." -ForegroundColor Red
            Write-Host "Automation test generation will fail without it." -ForegroundColor Red
            Write-Host 'Set it with: $env:ANTHROPIC_API_KEY = "your-anthropic-api-key"' -ForegroundColor Yellow
            Write-Host ""
        }
        if (-not $env:PHOENIX_LLM_MODEL) { $env:PHOENIX_LLM_MODEL = "claude-sonnet-4-20250514" }
    }
}

Write-Host "Starting Phoenix Intelligence Server on port 8001..." -ForegroundColor Green
Write-Host "  LLM Provider: $provider" -ForegroundColor Cyan
Write-Host "  LLM Model:    $($env:PHOENIX_LLM_MODEL)" -ForegroundColor Cyan
$mcpEnabled = if ($env:PHOENIX_MCP_ENABLED) { $env:PHOENIX_MCP_ENABLED } else { "true" }
Write-Host "  MCP Enabled:  $mcpEnabled" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python api/server.py
