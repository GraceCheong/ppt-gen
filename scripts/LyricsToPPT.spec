# -*- mode: python ; coding: utf-8 -*-
import sys as _sys

_is_win = _sys.platform == "win32"

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('assets/atempo.png', 'assets'),
        ('assets/background.png', 'assets'),
        ('assets/template.pptx', 'assets'),
        ('assets/songlist.pptx', 'assets'),
        ('assets/sequences_sample.txt', 'assets'),
    ],
    hiddenimports=['comtypes', 'comtypes.client'] if _is_win else [],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[] if _is_win else ['comtypes'],
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
    name='LyricsToPPT',
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
    icon='assets/atempo.png',
)

if not _is_win:
    app = BUNDLE(
        exe,
        name='LyricsToPPT.app',
        icon='assets/atempo.png',
        bundle_identifier='com.atempo.lyricstoppt',
    )
