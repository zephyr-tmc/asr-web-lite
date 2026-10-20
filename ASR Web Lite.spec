# -*- mode: python ; coding: utf-8 -*-
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

model_path = Path.home() / '.cache' / 'whisper' / 'medium.pt'
ffmpeg_path = shutil.which('ffmpeg')
ffprobe_path = shutil.which('ffprobe')
if not model_path.is_file():
    raise FileNotFoundError('Download the Whisper medium model before packaging.')
if not ffmpeg_path or not ffprobe_path:
    raise FileNotFoundError('Install ffmpeg and ffprobe and add them to PATH before packaging.')

datas = [('app/static', 'app/static'), (str(model_path), 'models')]
datas += collect_data_files('whisper')
datas += collect_data_files('tiktoken')


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[(ffmpeg_path, 'bin'), (ffprobe_path, 'bin')],
    datas=datas,
    hiddenimports=['tiktoken_ext', 'tiktoken_ext.openai_public'],
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
    name='ASR Web Lite',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ASR Web Lite',
)
app = BUNDLE(
    coll,
    name='ASR Web Lite.app',
    icon=None,
    bundle_identifier=None,
)
