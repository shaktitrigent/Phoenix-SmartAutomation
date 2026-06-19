@echo off
REM Phoenix Intelligence Server Startup Script
REM Requires a provider-specific API key environment variable

set PHOENIX_INTELLIGENCE_PORT=8001

if "%PHOENIX_LLM_PROVIDER%"=="" set PHOENIX_LLM_PROVIDER=anthropic

if /I "%PHOENIX_LLM_PROVIDER%"=="gemini" (
    if "%GOOGLE_API_KEY%"=="" (
        echo WARNING: GOOGLE_API_KEY is not set.
        echo Automation test generation will fail without it.
        echo Set it with: set GOOGLE_API_KEY=your-google-api-key
        echo.
    )
    if "%PHOENIX_LLM_MODEL%"=="" set PHOENIX_LLM_MODEL=gemini-1.5-pro
) else if /I "%PHOENIX_LLM_PROVIDER%"=="openai" (
    if "%OPENAI_API_KEY%"=="" (
        echo WARNING: OPENAI_API_KEY is not set.
        echo Automation test generation will fail without it.
        echo Set it with: set OPENAI_API_KEY=your-openai-api-key
        echo.
    )
    if "%PHOENIX_LLM_MODEL%"=="" set PHOENIX_LLM_MODEL=gpt-4o
) else if /I "%PHOENIX_LLM_PROVIDER%"=="ollama" (
    if "%PHOENIX_LLM_MODEL%"=="" set PHOENIX_LLM_MODEL=llama3
) else (
    if "%ANTHROPIC_API_KEY%"=="" (
        echo WARNING: ANTHROPIC_API_KEY is not set.
        echo Automation test generation will fail without it.
        echo Set it with: set ANTHROPIC_API_KEY=your-anthropic-api-key
        echo.
    )
    if "%PHOENIX_LLM_MODEL%"=="" set PHOENIX_LLM_MODEL=claude-sonnet-4-6
)

echo Starting Phoenix Intelligence Server on port 8001...
echo   LLM Provider: %PHOENIX_LLM_PROVIDER%
echo   LLM Model:    %PHOENIX_LLM_MODEL%
echo   MCP Enabled:  %PHOENIX_MCP_ENABLED%
echo.
echo Press Ctrl+C to stop the server
echo.

python api/server.py
