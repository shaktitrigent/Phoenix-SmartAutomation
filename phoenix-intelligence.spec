# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'fastapi', 'pydantic', 'anthropic', 'yaml']
hiddenimports += collect_submodules('api')
hiddenimports += collect_submodules('services')
hiddenimports += collect_submodules('phoenix_shared')
hiddenimports += collect_submodules('phoenix')
hiddenimports += collect_submodules('phoenix.reporting')


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
