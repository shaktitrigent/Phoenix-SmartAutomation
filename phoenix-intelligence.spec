# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['services', 'services.agents', 'services.agents.base', 'services.agents.failure_analyzer', 'services.agents.locator_expert', 'services.agents.registry', 'services.agents.script_fixer', 'services.agents.test_generator', 'services.cache', 'services.config', 'services.llm', 'services.llm.client', 'services.llm.prompt_loader', 'services.llm.router', 'services.logger', 'services.locator', 'services.mcp', 'services.mcp.client', 'services.mcp.handlers', 'services.mcp.server', 'services.knowledge', 'services.knowledge.base', 'phoenix.reporting', 'phoenix.reporting.aggregator', 'phoenix.reporting.data_loader', 'phoenix.reporting.generator', 'phoenix.reporting.html_reporter', 'phoenix.reporting.render', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'fastapi', 'pydantic', 'anthropic', 'yaml']
hiddenimports += collect_submodules('api')
hiddenimports += collect_submodules('phoenix_shared')
hiddenimports += collect_submodules('phoenix')


a = Analysis(
    ['D:\\SmartAutomation\\Phoenix-SmartAutomation\\phoenix-intelligence\\main.py'],
    pathex=['D:\\SmartAutomation\\Phoenix-SmartAutomation\\phoenix-intelligence', 'D:\\SmartAutomation\\Phoenix-SmartAutomation\\shared', 'D:\\SmartAutomation\\Phoenix-SmartAutomation\\phoenix-core'],
    binaries=[],
    datas=[('D:\\SmartAutomation\\Phoenix-SmartAutomation\\phoenix-intelligence\\prompts', 'prompts'), ('D:\\SmartAutomation\\Phoenix-SmartAutomation\\phoenix-intelligence\\services\\knowledge', 'services\\knowledge')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='phoenix-intelligence',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
