@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo  SmartOnmyoji - Windows build
echo ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
    echo [FAILED] Build failed with exit code %EXITCODE%. See the messages above.
) else (
    echo [DONE] Output: Release\smart_onmyoji_start\smart_onmyoji_start.exe
)
echo.
pause
exit /b %EXITCODE%
