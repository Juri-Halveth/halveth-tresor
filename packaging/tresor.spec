# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Tresor. Build with:  python -m PyInstaller packaging/tresor.spec --clean --noconfirm
# Paths are resolved relative to this spec file (SPECPATH) so the build works from any CWD.
import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas = [(os.path.join(ROOT, 'src', 'tresor', 'ui', 'index.html'), 'ui')]
binaries = []
hiddenimports = ['clr']

# Bundle the pywebview + pythonnet stack completely (WebView2 host interop).
for pkg in ('webview', 'clr_loader', 'pythonnet'):
    collected_datas, collected_binaries, collected_hidden = collect_all(pkg)
    datas += collected_datas
    binaries += collected_binaries
    hiddenimports += collected_hidden

a = Analysis(
    [os.path.join(ROOT, 'src', 'tresor', '__main__.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=binaries,
    datas=datas,
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
    name='Tresor',
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
    icon=[os.path.join(ROOT, 'assets', 'icon.ico')],
)
