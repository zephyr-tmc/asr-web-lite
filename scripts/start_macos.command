#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Finder/Terminal 启动 .command 时 PATH 可能很短，Homebrew 的 ffmpeg 会因此找不到。
# 这里显式补上常见 macOS 路径，同时允许项目内 bin/ 放置 ffmpeg/ffprobe。
export PATH="$ROOT/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

echo "ASR Web Lite macOS 原型启动器"
echo
echo "说明：当前脚本原型需要本机已经安装 Python 3.10-3.12。"
echo "正式面向没有 Python 的用户时，应提供内置 Python 运行时的打包版。"
echo

PYTHON_CMD=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 13) else 1)' >/dev/null 2>&1; then
      PYTHON_CMD="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  echo "未检测到可用的 Python 3.10-3.12。"
  echo "这个脚本原型无法在没有合适 Python 的电脑上直接运行。"
  echo "后续正式版需要改为 .app/.dmg 打包，并内置 Python。"
  read -n 1 -s -r -p "按任意键退出"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "未检测到 ffmpeg/ffprobe。"
  echo "当前 PATH：$PATH"
  echo "请先安装 ffmpeg，或等待后续内置 ffmpeg 的打包版。"
  echo "如果你正在测试正式版本，建议直接使用 dist/ASR-Web-Lite-macOS-arm64.dmg。"
  read -n 1 -s -r -p "按任意键退出"
  exit 1
fi

echo "ffmpeg: $(command -v ffmpeg)"
echo "ffprobe: $(command -v ffprobe)"

"$PYTHON_CMD" scripts/bootstrap.py

if ! "$PYTHON_CMD" -c 'import socket; s=socket.socket(); code=s.connect_ex(("127.0.0.1", 8765)); s.close(); raise SystemExit(0 if code != 0 else 1)'; then
  echo
  echo "端口 8765 已被占用，可能已有旧版 ASR Web Lite 正在运行。"
  echo "请先关闭旧窗口/旧终端进程，再重新双击 start_macos.command。"
  read -n 1 -s -r -p "按任意键退出"
  exit 1
fi

echo
echo "正在启动本地网页：http://127.0.0.1:8765"
open "http://127.0.0.1:8765" >/dev/null 2>&1 || true
exec .venv/bin/python -m app.main
