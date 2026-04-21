@echo off
REM Phoenix Intelligence Server Startup Script
REM Supports Anthropic, Gemini, OpenAI, and Ollama.

set PHOENIX_INTELLIGENCE_PORT=8001

if "%PHOENIX_LLM_PROVIDER%"=="" set PHOENIX_LLM_PROVIDER=auto

set AVAILABLE_PROVIDERS=
if not "%ANTHROPIC_API_KEY%"=="" set AVAILABLE_PROVIDERS=anthropic
if not "%GOOGLE_API_KEY%"=="" (
    if "%AVAILABLE_PROVIDERS%"=="" (
        set AVAILABLE_PROVIDERS=gemini
    ) else (
        set AVAILABLE_PROVIDERS=%AVAILABLE_PROVIDERS%, gemini
    )
)
if not "%GEMINI_API_KEY%"=="" (
    echo %AVAILABLE_PROVIDERS% | findstr /C:"gemini" >nul
    if errorlevel 1 (
        if "%AVAILABLE_PROVIDERS%"=="" (
            set AVAILABLE_PROVIDERS=gemini
        ) else (
            set AVAILABLE_PROVIDERS=%AVAILABLE_PROVIDERS%, gemini
        )
    )
)
if not "%OPENAI_API_KEY%"=="" (
    if "%AVAILABLE_PROVIDERS%"=="" (
        set AVAILABLE_PROVIDERS=openai
    ) else (
        set AVAILABLE_PROVIDERS=%AVAILABLE_PROVIDERS%, openai
    )
)
if not "%OLLAMA_BASE_URL%"=="" (
    if "%AVAILABLE_PROVIDERS%"=="" (
        set AVAILABLE_PROVIDERS=ollama
    ) else (
        set AVAILABLE_PROVIDERS=%AVAILABLE_PROVIDERS%, ollama
    )
)

if "%AVAILABLE_PROVIDERS%"=="" (
    echo WARNING: No LLM API key detected.
    echo Set ANTHROPIC_API_KEY, GOOGLE_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY.
    echo.
)

if "%PHOENIX_LLM_MODEL%"=="" (
    echo %PHOENIX_LLM_PROVIDER% | findstr /I /C:"gemini" >nul
    if not errorlevel 1 set PHOENIX_LLM_MODEL=gemini-1.5-pro

    if "%PHOENIX_LLM_MODEL%"=="" (
        echo %PHOENIX_LLM_PROVIDER% | findstr /I /C:"openai" >nul
        if not errorlevel 1 set PHOENIX_LLM_MODEL=gpt-4o
    )

    if "%PHOENIX_LLM_MODEL%"=="" (
        echo %PHOENIX_LLM_PROVIDER% | findstr /I /C:"ollama" >nul
        if not errorlevel 1 set PHOENIX_LLM_MODEL=llama3
    )

    if "%PHOENIX_LLM_MODEL%"=="" if /I "%PHOENIX_LLM_PROVIDER%"=="auto" if /I "%AVAILABLE_PROVIDERS%"=="gemini" set PHOENIX_LLM_MODEL=gemini-1.5-pro
    if "%PHOENIX_LLM_MODEL%"=="" if /I "%PHOENIX_LLM_PROVIDER%"=="auto" if /I "%AVAILABLE_PROVIDERS%"=="openai" set PHOENIX_LLM_MODEL=gpt-4o
    if "%PHOENIX_LLM_MODEL%"=="" if /I "%PHOENIX_LLM_PROVIDER%"=="auto" if /I "%AVAILABLE_PROVIDERS%"=="ollama" set PHOENIX_LLM_MODEL=llama3

    if "%PHOENIX_LLM_MODEL%"=="" set PHOENIX_LLM_MODEL=claude-sonnet-4-20250514
)

echo Starting Phoenix Intelligence Server on port 8001...
echo   LLM Provider: %PHOENIX_LLM_PROVIDER%
if not "%AVAILABLE_PROVIDERS%"=="" echo   Available:    %AVAILABLE_PROVIDERS%
echo   LLM Model:    %PHOENIX_LLM_MODEL%
if "%PHOENIX_MCP_ENABLED%"=="" (
    echo   MCP Enabled:  true
) else (
    echo   MCP Enabled:  %PHOENIX_MCP_ENABLED%
)
echo.
echo Press Ctrl+C to stop the server
echo.

python api/server.py
