@echo off
REM Phoenix Intelligence Server Startup Script
REM Requires: GOOGLE_API_KEY environment variable (for the default Gemini provider)

set PHOENIX_INTELLIGENCE_PORT=8001

if "%GOOGLE_API_KEY%"=="" (
    echo WARNING: GOOGLE_API_KEY is not set.
    echo Automation test generation will fail without it.
    echo Set it with: set GOOGLE_API_KEY=your-gemini-api-key
    echo.
)

echo Starting Phoenix Intelligence Server on port 8001...
echo   LLM Provider: Gemini
echo   MCP Enabled:  true (default)
echo.
echo Press Ctrl+C to stop the server
echo.

python api/server.py
