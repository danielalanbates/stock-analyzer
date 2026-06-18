# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['stock_manager_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('portfolio.json', '.'), ('portfolio_manager.py', '.')],
    hiddenimports=['yfinance', 'pandas', 'matplotlib', 'PIL'],
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
    name='Stock Analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.png'],
)
app = BUNDLE(
    exe,
    name='Stock Analyzer.app',
    icon='app_icon.png',
    bundle_identifier=None,
)
