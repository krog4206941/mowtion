@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%~dp0;"
set "PATH=%~dp0tools\ffmpeg\bin;%PATH%"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

if exist ".venv\Scripts\python.exe" goto run
echo.
echo Clip Studio is not set up yet.
echo Double-click install.bat first.
echo Leave that window open until it says Done.
echo.
pause
exit /b 1

:run
echo.
echo Opening Clip Studio...
echo Leave this window open while you use the app.
echo Close this window when you are finished.
echo.
".venv\Scripts\python.exe" -m mowstudio
echo.
echo Clip Studio stopped.
pause
exit /b 0
