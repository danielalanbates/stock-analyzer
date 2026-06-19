# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['engine_cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['recommendation_engine', 'data_cli', 'fundamentals',
                   'portfolio_manager', 'yfinance', 'pandas', 'numpy'],
    excludes=['matplotlib', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
              'sklearn', 'scipy', 'torch', 'tensorflow', 'opentelemetry',
              'numba', 'llvmlite', 'sympy', 'IPython', 'jupyter', 'notebook',
              'PIL', 'wx', 'zmq', 'tornado'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='engine_cli',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='engine')
