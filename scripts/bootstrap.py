from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
PYTHON = VENV / "bin" / "python"


def main() -> int:
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        print("需要 Python 3.10 - 3.12。")
        print("当前脚本原型依赖本机已有 Python；正式小白版应内置 Python 运行时。")
        return 1

    if not VENV.exists():
        print("正在创建项目虚拟环境 .venv ...")
        run([sys.executable, "-m", "venv", str(VENV)])

    print("正在安装/检查依赖，首次运行可能较慢 ...")
    run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(PYTHON), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    return 0


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
