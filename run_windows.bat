@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Dependency installation failed. Check your Python installation and internet access.
  pause
  exit /b 1
)
python server.py
pause
