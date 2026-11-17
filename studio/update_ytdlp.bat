@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
  echo Double-click install.bat first.
  pause
  exit /b 1
)
echo Updating the downloader...
".venv\Scripts\python.exe" -m pip install -U yt-dlp
if errorlevel 1 (
  echo The update failed. Check your internet and try again.
  pause
  exit /b 1
)
echo.
echo Done. If Clip Studio is open, close the black window.
echo Then double-click start.bat.
pause
exit /b 0
