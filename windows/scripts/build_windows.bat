@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "BUILD_SCRIPT=%SCRIPT_DIR%build_windows.ps1"

pushd "%PROJECT_ROOT%" >nul 2>nul
if errorlevel 1 (
  echo 无法进入项目目录：%PROJECT_ROOT%
  echo 请确认项目已经完整解压，不要在 ZIP 压缩包预览窗口里运行。
  pause
  exit /b 1
)

if not exist "%BUILD_SCRIPT%" (
  echo 未找到打包脚本：%BUILD_SCRIPT%
  echo 请确认 scripts\build_windows.ps1 存在，并且项目文件夹结构完整。
  popd
  pause
  exit /b 1
)

echo ASR Web Lite Windows 打包启动器
echo.
echo 这个脚本会调用 scripts\build_windows.ps1。
echo 打包过程会创建 .venv、安装依赖，并生成 dist 目录。
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BUILD_SCRIPT%"
set "BUILD_EXIT=%ERRORLEVEL%"
if not "%BUILD_EXIT%"=="0" (
  echo.
  echo 打包失败，请查看上方错误信息。
  popd
  pause
  exit /b %BUILD_EXIT%
)

echo.
echo 打包完成。
echo 便携版位置：dist\ASR Web Lite\ASR Web Lite.exe
echo 如果安装了 Inno Setup，安装包位置：dist\installer\ASR-Web-Lite-Setup.exe
popd
pause
