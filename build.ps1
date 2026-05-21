# Phoenix Build & Package Script
# Usage:
#   .\build.ps1 install     — install all packages in editable mode
#   .\build.ps1 package     — build the phoenix-intelligence standalone exe
#   .\build.ps1 clean       — remove build artifacts
#   .\build.ps1 all         — install + package exe only
#   .\build.ps1 dist        — clean + build all three artifacts into dist\ (exe + wheels)

param(
    [Parameter(Position=0)]
    [ValidateSet("install", "package", "clean", "all", "dist")]
    [string]$Command = "all"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Install-Deps {
    Write-Host "`n>>> Installing packages..." -ForegroundColor Cyan
    pip install -e "$Root\shared\" --quiet
    pip install -e "$Root\phoenix-core\" --quiet
    pip install -e "$Root\phoenix-intelligence\" --quiet
    pip install pyinstaller uvicorn[standard] --quiet
    Write-Host "    Done." -ForegroundColor Green
}

function Build-Exe {
    Write-Host "`n>>> Building phoenix-intelligence.exe..." -ForegroundColor Cyan

    # Create entry point if it doesn't exist
    $entryPoint = "$Root\phoenix-intelligence\main.py"
    if (-not (Test-Path $entryPoint)) {
        @'
import sys

if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)

from api.server import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
'@ | Set-Content $entryPoint
        Write-Host "    Created main.py entry point." -ForegroundColor Yellow
    }

    pyinstaller --onefile `
        --clean `
        --name phoenix-intelligence `
        --paths "$Root\phoenix-intelligence" `
        --paths "$Root\shared" `
        --paths "$Root\phoenix-core" `
        --collect-submodules api `
        --collect-submodules services `
        --collect-submodules phoenix_shared `
        --collect-submodules phoenix `
        --collect-submodules phoenix.reporting `
        --hidden-import uvicorn.logging `
        --hidden-import uvicorn.loops `
        --hidden-import uvicorn.loops.auto `
        --hidden-import uvicorn.protocols `
        --hidden-import uvicorn.protocols.http `
        --hidden-import uvicorn.protocols.http.auto `
        --hidden-import uvicorn.protocols.websockets `
        --hidden-import uvicorn.protocols.websockets.auto `
        --hidden-import uvicorn.lifespan `
        --hidden-import uvicorn.lifespan.on `
        --hidden-import fastapi `
        --hidden-import pydantic `
        --hidden-import anthropic `
        --hidden-import yaml `
        --add-data "$Root\phoenix-intelligence\prompts;prompts" `
        --add-data "$Root\phoenix-intelligence\services\knowledge;services\knowledge" `
        --distpath "$Root\dist" `
        --workpath "$Root\build" `
        --specpath "$Root" `
        --noconfirm `
        "$entryPoint"

    Write-Host "`n    Output: $Root\dist\phoenix-intelligence.exe" -ForegroundColor Green
}

function Clean-Artifacts {
    Write-Host "`n>>> Cleaning build artifacts..." -ForegroundColor Cyan
    @("$Root\dist", "$Root\build", "$Root\phoenix-intelligence.spec") | ForEach-Object {
        if (Test-Path $_) { Remove-Item $_ -Recurse -Force; Write-Host "    Removed $_" }
    }
    Write-Host "    Done." -ForegroundColor Green
}

function Build-Wheels {
    Write-Host "`n>>> Building wheels into dist\..." -ForegroundColor Cyan
    pip install build --quiet
    python -m build "$Root\shared\"       --outdir "$Root\dist\"
    python -m build "$Root\phoenix-core\" --outdir "$Root\dist\"
    Write-Host "    Done." -ForegroundColor Green
}

function Build-All-Dist {
    Clean-Artifacts
    Build-Wheels
    Build-Exe
    Write-Host "`n>>> dist\ contents:" -ForegroundColor Cyan
    Get-ChildItem "$Root\dist" | ForEach-Object {
        Write-Host ("    {0,-50} {1,8} KB" -f $_.Name, [math]::Round($_.Length/1KB))
    }
    Write-Host "`n    All artifacts ready in: $Root\dist\" -ForegroundColor Green
}

switch ($Command) {
    "install" { Install-Deps }
    "package" { Build-Exe }
    "clean"   { Clean-Artifacts }
    "all"     { Install-Deps; Build-Exe }
    "dist"    { Build-All-Dist }
}
