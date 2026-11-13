@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%~dp0;"

echo.
echo ============================================
echo   Clip Studio setup
echo   You only do this one time.
echo   It can take a long time. Leave this window open.
echo   You do not need an admin password.
echo ============================================
echo.

set "UV=%USERPROFILE%\.local\bin\uv.exe"

if exist "%UV%" goto have_uv
where uv >nul 2>&1
if errorlevel 1 goto download_uv
for /f "delims=" %%I in ('where uv') do (
  set "UV=%%I"
  goto have_uv
)

:download_uv
echo [1/7] Downloading a small helper...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if exist "%UV%" goto have_uv
echo.
echo Could not download the helper. Check your internet.
echo Then double-click install.bat again.
pause
exit /b 1

:have_uv
echo [2/7] Installing Python...
"%UV%" python install 3.11
if errorlevel 1 goto failed

echo [3/7] Creating a private folder for the app...
if exist ".venv\Scripts\python.exe" goto have_venv
"%UV%" venv --python 3.11 --seed .venv
if errorlevel 1 goto failed

:have_venv
".venv\Scripts\python.exe" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo The private folder is broken.
  echo Delete the studio\.venv folder, then double-click install.bat again.
  goto failed
)
echo [4/7] Installing the app pieces. This is the long step...
".venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto failed

echo [5/7] Getting the video tool...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\get-ffmpeg.ps1"
if errorlevel 1 goto failed

echo [6/7] Extra voice: Grandfather Joe.
echo       This download is big. If it fails, the fast voice still works.
".venv\Scripts\python.exe" -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto joe_failed
".venv\Scripts\python.exe" -m pip install -r "%~dp0requirements-joe.txt"
if errorlevel 1 goto joe_failed
echo Joe's voice package is installed.
echo The voice model downloads the first time you use Joe.
goto joe_done

:joe_failed
echo.
echo Joe's voice did not install. That is OK.
echo The app will use the fast voice instead.
echo.

:joe_done
echo [7/7] Checking the app...
set "PATH=%~dp0tools\ffmpeg\bin;%PATH%"
".venv\Scripts\python.exe" -m mowstudio doctor
if errorlevel 1 goto failed

echo.
echo ============================================
echo   Done.
echo   Double-click start.bat to open Clip Studio.
echo ============================================
echo.
pause
exit /b 0

:failed
echo.
echo Setup stopped. Scroll up and read the last lines.
echo Then double-click install.bat again.
echo You do not need an admin password for this app.
echo.
pause
exit /b 1
