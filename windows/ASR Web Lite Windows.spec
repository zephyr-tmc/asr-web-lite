# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


root = Path.cwd()
datas = [
    (str(root.parent / "app" / "static"), "app/static"),
    (str(root / "models" / "medium.pt"), "models"),
]
datas += collect_data_files("whisper")
datas += collect_data_files("tiktoken")

binaries = [
    (str(root / "bin" / "ffmpeg.exe"), "bin"),
    (str(root / "bin" / "ffprobe.exe"), "bin"),
]


a = Analysis(
    ["launcher.py"],
    pathex=[str(root), str(root.parent)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["tiktoken_ext", "tiktoken_ext.openai_public"],
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
    [],
    exclude_binaries=True,
    name="ASR Web Lite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ASR Web Lite",
)
