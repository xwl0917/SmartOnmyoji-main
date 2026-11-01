# -*- mode: python ; coding: utf-8 -*-
# Compatible with PyInstaller 5.13 and 6.x.
# PyInstaller 6 removed the bytecode-encryption `cipher` option and the
# deprecated `win_no_prefer_redirects` / `win_private_assemblies` arguments,
# so they are intentionally not used here.
#
# Qt: do NOT collect_all('PyQt5') here. The app only imports QtCore/QtGui/
# QtWidgets; PyInstaller's PyQt5 hook collects the required DLLs and plugins
# (qwindows, qico, styles). Keeping collect_all pulled in QML/translations and
# every optional Qt module, bloating the package. Build with --self-check to
# verify the trimmed bundle.
from PyInstaller.utils.hooks import collect_all

datas = [('.\\img', 'img'), ('.\\modules', 'modules')]
binaries = []
hiddenimports = ['PyQt5.sip', 'win32api', 'win32con', 'win32gui', 'win32process', 'pywintypes']
tmp_ret = collect_all('pynput')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['smart_onmyoji_start.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='smart_onmyoji_start',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='smart_onmyoji_start',
)
