@echo off
setlocal

cd /d "%~dp0\.."
set "PATH=%CD%\bin;%PATH%"
set "START_LOG=%CD%\start_windows_last_run.log"
> "%START_LOG%" echo ASR Web Lite Windows 启动日志
>> "%START_LOG%" echo 启动时间：%DATE% %TIME%
>> "%START_LOG%" echo 项目目录：%CD%

echo ASR Web Lite Windows 开发启动器
echo.
echo 说明：这个脚本用于开发测试，需要本机已安装 Python 3.10-3.12。
echo 正式给普通用户使用时，请使用打包后的安装版，不需要用户安装 Python。
echo.

set "PYTHON_CMD="
py -3.12 -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 13) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD py -3.11 -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 13) else 1)" >nul 2>nul
if not errorlevel 1 if not defined PYTHON_CMD set "PYTHON_CMD=py -3.11"
if not defined PYTHON_CMD py -3.10 -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 13) else 1)" >nul 2>nul
if not errorlevel 1 if not defined PYTHON_CMD set "PYTHON_CMD=py -3.10"
if not defined PYTHON_CMD python -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 13) else 1)" >nul 2>nul
if not errorlevel 1 if not defined PYTHON_CMD set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  >> "%START_LOG%" echo 未检测到可用的 Python 3.10-3.12。
  echo 未检测到可用的 Python 3.10-3.12。
  echo 开发启动器无法在没有 Python 的电脑上直接运行；正式安装版会内置运行时。
  echo 诊断日志：%START_LOG%
  pause
  exit /b 1
)

echo 检测到 Python：%PYTHON_CMD%
>> "%START_LOG%" echo 检测到 Python：%PYTHON_CMD%
echo.

if not exist "bin\ffmpeg.exe" (
  >> "%START_LOG%" echo 缺少 bin\ffmpeg.exe。
  echo 未找到 bin\ffmpeg.exe。
  echo 请把 Windows 版 ffmpeg.exe 放到项目的 bin 文件夹后再启动。
  echo 诊断日志：%START_LOG%
  pause
  exit /b 1
)

if not exist "bin\ffprobe.exe" (
  >> "%START_LOG%" echo 缺少 bin\ffprobe.exe。
  echo 未找到 bin\ffprobe.exe。
  echo 请把 Windows 版 ffprobe.exe 放到项目的 bin 文件夹后再启动。
  echo 诊断日志：%START_LOG%
  pause
  exit /b 1
)

if not exist "models\medium.pt" (
  >> "%START_LOG%" echo 未找到 models\medium.pt，将允许 Whisper 首次运行时联网下载模型。
  echo 注意：未找到 models\medium.pt。
  echo 继续运行时，首次选择 medium 会联网下载约 1.4GB 模型；正式安装包建议内置该文件。
  echo.
)

>> "%START_LOG%" echo 正在运行 scripts\bootstrap.py。
call %PYTHON_CMD% scripts\bootstrap.py
set "BOOTSTRAP_EXIT=%ERRORLEVEL%"
>> "%START_LOG%" echo scripts\bootstrap.py 退出码：%BOOTSTRAP_EXIT%
if not "%BOOTSTRAP_EXIT%"=="0" goto fail

if not exist ".venv\Scripts\python.exe" (
  >> "%START_LOG%" echo 虚拟环境创建失败：未找到 .venv\Scripts\python.exe。
  echo.
  echo 虚拟环境创建失败：未找到 .venv\Scripts\python.exe。
  echo 请确认当前目录可以写入，并且 Python 安装时包含 venv/pip。
  echo 诊断日志：%START_LOG%
  pause
  exit /b 1
)

.venv\Scripts\python.exe -c "import socket; s=socket.socket(); code=s.connect_ex(('127.0.0.1', 8765)); s.close(); raise SystemExit(0 if code != 0 else 1)"
if errorlevel 1 (
  >> "%START_LOG%" echo 端口 8765 已被占用。
  echo.
  echo 端口 8765 已被占用，可能已有旧版 ASR Web Lite 正在运行。
  echo 请先关闭旧窗口或旧进程，再重新启动。
  echo 诊断日志：%START_LOG%
  pause
  exit /b 1
)

echo.
echo 正在启动本地网页：http://127.0.0.1:8765
>> "%START_LOG%" echo 正在启动本地网页：http://127.0.0.1:8765
start "" "http://127.0.0.1:8765"
.venv\Scripts\python.exe -m app.main
set "APP_EXIT=%ERRORLEVEL%"
>> "%START_LOG%" echo app.main 退出码：%APP_EXIT%
if not "%APP_EXIT%"=="0" (
  echo.
  echo 应用进程已退出，错误码：%APP_EXIT%
  echo 请把上方错误信息发给开发者排查。
  echo 诊断日志：%START_LOG%
  pause
)
exit /b %APP_EXIT%

:fail
echo.
echo 启动失败，请查看上方错误信息。
echo 诊断日志：%START_LOG%
pause
exit /b %BOOTSTRAP_EXIT%
