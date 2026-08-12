@echo off
setlocal
cd /d "%~dp0"
echo ======================================================
echo   Agentic 835 Assistant - Setup
echo ======================================================

echo.
echo [1/4] Checking Python...
where py >nul 2>nul
if errorlevel 1 (
  echo   ERROR: Python launcher "py" was not found.
  echo   Install Python 3.12 from https://www.python.org/downloads/
  echo   and make sure "Add python.exe to PATH" is checked.
  pause
  exit /b 1
)
py -3.12 --version 2>nul || py --version

echo.
echo [2/4] Setting up Python virtual environment...
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo   Could not create the virtual environment.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo   Could not install Python dependencies.
  pause
  exit /b 1
)
echo   Python dependencies installed.

echo.
echo [3/4] Checking Node.js and frontend...
where node >nul 2>nul
if errorlevel 1 (
  echo   ERROR: Node.js was not found.
  echo   Install Node.js LTS from https://nodejs.org/
  pause
  exit /b 1
)
node --version
where npm >nul 2>nul
if errorlevel 1 (
  echo   ERROR: npm was not found.
  echo   npm normally comes with Node.js. Reinstall Node.js LTS from https://nodejs.org/
  pause
  exit /b 1
)
call npm --version

if not exist "frontend\node_modules" goto install_frontend
echo   Frontend dependencies already installed.
goto frontend_build

:install_frontend
echo   Installing frontend dependencies (this can take a minute)...
pushd frontend
call npm install
set "NPM_EXIT=%errorlevel%"
popd
if not "%NPM_EXIT%"=="0" (
  echo.
  echo   npm install FAILED. Exit code: %NPM_EXIT%
  echo   This is usually a network or npm-registry problem.
  echo   Check your internet connection, then retry:
  echo       cd frontend
  echo       npm install
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo.
  echo   npm install finished but "frontend\node_modules" was not created.
  echo   Please run it manually and confirm it works:
  echo       cd frontend
  echo       npm install
  echo       dir node_modules
  pause
  exit /b 1
)

:frontend_build
pushd frontend
call npm run build
popd
echo   Frontend ready.

echo.
echo [4/4] Checking Ollama / Llama 3.2...
where ollama >nul 2>nul
if errorlevel 1 (
  echo   ERROR: Ollama was not found.
  echo   Install Ollama from https://ollama.com  then run:
  echo     ollama pull llama3.2
  echo   and run setup.bat again.
  pause
  exit /b 1
)
ollama list | findstr /C:"llama3.2" >nul
if errorlevel 1 (
  echo   Pulling the llama3.2 model...
  echo   The first download can take several minutes.
  ollama pull llama3.2
  if errorlevel 1 (
    echo   Could not pull llama3.2. Run it manually:  ollama pull llama3.2
    pause
    exit /b 1
  )
)
echo   Ollama and llama3.2 are ready.

echo.
echo Setup complete. Run start.bat to launch the assistant.
pause
endlocal
