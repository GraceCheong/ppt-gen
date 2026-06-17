# -*- mode: python ; coding: utf-8 -*-
import os as _os
import sys as _sys

_is_win = _sys.platform == "win32"
_root = _os.path.abspath(_os.path.join(SPECPATH, '..'))
_icon_file = _os.path.join(_root, 'assets', 'atempo.ico' if _is_win else 'atempo.png')
_hiddenimports = ['gdown']
if _is_win:
    _hiddenimports.extend(['comtypes', 'comtypes.client'])

_excludes = [
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
    'IPython',
    'astroid',
    'black',
    'dask',
    'jedi',
    'matplotlib',
    'nbformat',
    'pandas',
    'pytest',
    'scipy',
    'sphinx',
    'zmq',
]
if not _is_win:
    _excludes.append('comtypes')

a = Analysis(
    [_os.path.join(_root, 'src', 'main.py')],
    pathex=[_os.path.join(_root, 'src')],
    binaries=[],
    datas=[
        (_os.path.join(_root, 'assets', 'atempo.ico'), 'assets'),
        (_os.path.join(_root, 'assets', 'atempo.png'), 'assets'),
        (_os.path.join(_root, 'assets', 'logo.png'), 'assets'),
        (_os.path.join(_root, 'assets', 'background.png'), 'assets'),
(_os.path.join(_root, 'assets', 'sequences_sample.txt'), 'assets'),
    ],
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes,
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
    name='PORR_atempo',
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
    icon=_icon_file,
)

if not _is_win:
    app = BUNDLE(
        exe,
        name='PORR_atempo.app',
        icon=_icon_file,
        bundle_identifier='com.atempo.lyricstoppt',
    )
