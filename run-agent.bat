@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found. Install Python 3.12 and try again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python 3.12 virtual environment...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Could not create a Python 3.12 environment.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt

where ollama >nul 2>nul
if errorlevel 1 (
  echo Ollama was not found. Install it from https://ollama.com and run: ollama pull llama3.2
  pause
  exit /b 1
)

echo.
echo Starting the Agentic 835 Processing Assistant (local Ollama / Llama 3.2)...
echo Press CTRL+C to exit.
echo.
python main.py
endlocal
