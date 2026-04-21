@echo off
REM Phoenix Intelligence Server Startup Script
REM Requires: ANTHROPIC_API_KEY environment variable

set PHOENIX_INTELLIGENCE_PORT=8001

if "%ANTHROPIC_API_KEY%"=="" (
    echo WARNING: ANTHROPIC_API_KEY is not set.
    echo Automation test generation will fail without it.
    echo Set it with: set ANTHROPIC_API_KEY=sk-ant-your-key-here
    echo.
)

echo Starting Phoenix Intelligence Server on port 8001...
echo   LLM Provider: Anthropic Claude
echo   MCP Enabled:  true (default)
echo.
echo Press Ctrl+C to stop the server
echo.

python api/server.py
