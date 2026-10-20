from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> int:
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        print("需要 Python 3.10 - 3.12。")
        print("开发启动器依赖本机已有 Python；正式 Windows 安装包会内置 Python 运行时。")
        return 1

    print(f"项目目录：{ROOT}")
    print(f"当前 Python：{sys.executable}")
    print(f"当前版本：{sys.version.split()[0]}")

    if VENV.exists() and not PYTHON.exists():
        print("检测到不完整的 .venv，正在删除后重新创建 ...")
        shutil.rmtree(VENV, ignore_errors=True)

    if not PYTHON.exists():
        print("正在创建项目虚拟环境 .venv ...")
        run([sys.executable, "-m", "venv", str(VENV)])

    if not PYTHON.exists():
        print(f"虚拟环境创建失败：未找到 {PYTHON}")
        return 1

    print("正在安装/检查依赖，首次运行可能较慢 ...")
    run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    if os.name == "nt":
        print("正在安装 Windows CPU 版 PyTorch ...")
        run([str(PYTHON), "-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cpu"])
    requirements = ROOT / ("requirements-windows.txt" if os.name == "nt" else "requirements.txt")
    run([str(PYTHON), "-m", "pip", "install", "-r", str(requirements)])
    return 0


def run(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
