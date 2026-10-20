# ビルド / 构建 / Build

[日本語](../README.md) · [简体中文](../README.zh-CN.md) · [English](../README.en.md)

以下はソースから配布物を作るための手順です。以下说明如何从源码构建。The following steps describe building from source; they are not a claim that a release has been validated.

## macOS

From the repository root, create and activate a Python 3.10–3.12 virtual environment, then:

```bash
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -c "import whisper; whisper.load_model('medium', device='cpu')"
pyinstaller "ASR Web Lite.spec"
```

- `ffmpeg` and `ffprobe` must be available on PATH before building.
- The spec expects `medium.pt` in `~/.cache/whisper/` and includes it in the bundle.
- Output: `dist/ASR Web Lite.app`.
- Build on the target platform. Signing and notarization are separate release tasks.

## Windows

On Windows, place the following assets under `windows/`:

```text
bin/ffmpeg.exe
bin/ffprobe.exe
models/medium.pt
```

Obtain FFmpeg from a distribution linked by the [FFmpeg project](https://ffmpeg.org/download.html). Obtain model weights using [OpenAI Whisper](https://github.com/openai/whisper). A model downloaded through Whisper is normally cached under `~/.cache/whisper/`.

From `windows/`, run:

```powershell
scripts\build_windows.bat
```

- Requires Python 3.10–3.12.
- Portable application: `dist/ASR Web Lite/ASR Web Lite.exe`.
- With Inno Setup 6 and `ISCC.exe` on PATH: `dist/installer/ASR-Web-Lite-Setup.exe`.

## Distribution contents

Model weights, bundled interpreters and FFmpeg binaries can make release packages large. They are not Git source files. Before distributing a binary package, review the notices and redistribution terms for the actual dependency builds included in it.
