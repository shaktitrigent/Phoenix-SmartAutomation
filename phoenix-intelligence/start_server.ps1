# Phoenix Intelligence Server Startup Script
# Supports Anthropic, Gemini, OpenAI, and Ollama.

$env:PHOENIX_INTELLIGENCE_PORT = "8001"

if (-not $env:PHOENIX_LLM_PROVIDER) {
    $env:PHOENIX_LLM_PROVIDER = "auto"
}

$providerSetting = $env:PHOENIX_LLM_PROVIDER
$availableProviders = @()

if ($env:ANTHROPIC_API_KEY) {
    $availableProviders += "anthropic"
}
if ($env:GOOGLE_API_KEY -or $env:GEMINI_API_KEY) {
    $availableProviders += "gemini"
}
if ($env:OPENAI_API_KEY) {
    $availableProviders += "openai"
}
if ($env:OLLAMA_BASE_URL) {
    $availableProviders += "ollama"
}

if ($availableProviders.Count -eq 0) {
    Write-Host "WARNING: No LLM API key detected." -ForegroundColor Red
    Write-Host "Set ANTHROPIC_API_KEY, GOOGLE_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY." -ForegroundColor Yellow
    Write-Host ""
}

if (-not $env:PHOENIX_LLM_MODEL) {
    if ($providerSetting -match "gemini") {
        $env:PHOENIX_LLM_MODEL = "gemini-1.5-pro"
    } elseif ($providerSetting -match "openai") {
        $env:PHOENIX_LLM_MODEL = "gpt-4o"
    } elseif ($providerSetting -match "ollama") {
        $env:PHOENIX_LLM_MODEL = "llama3"
    } elseif ($providerSetting -eq "auto" -and $availableProviders.Count -eq 1) {
        switch ($availableProviders[0]) {
            "gemini" { $env:PHOENIX_LLM_MODEL = "gemini-1.5-pro" }
            "openai" { $env:PHOENIX_LLM_MODEL = "gpt-4o" }
            "ollama" { $env:PHOENIX_LLM_MODEL = "llama3" }
            default { $env:PHOENIX_LLM_MODEL = "claude-sonnet-4-20250514" }
        }
    } else {
        $env:PHOENIX_LLM_MODEL = "claude-sonnet-4-20250514"
    }
}

Write-Host "Starting Phoenix Intelligence Server on port 8001..." -ForegroundColor Green
Write-Host "  LLM Provider: $providerSetting" -ForegroundColor Cyan
if ($availableProviders.Count -gt 0) {
    Write-Host "  Available:    $($availableProviders -join ', ')" -ForegroundColor Cyan
}
Write-Host "  LLM Model:    $($env:PHOENIX_LLM_MODEL)" -ForegroundColor Cyan
Write-Host "  MCP Enabled:  $($env:PHOENIX_MCP_ENABLED ?? 'true')" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python api/server.py
