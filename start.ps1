# Starts the local Agentic 835 Assistant (backend + frontend + browser).
# Launched by start.bat.  Everything runs on 127.0.0.1 - nothing leaves this PC.
# If a required dependency is missing, this installs it automatically instead
# of just failing, so a fresh machine "just works".

Set-Location $PSScriptRoot

# ---- Python backend ----
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found - creating it..." -ForegroundColor Yellow
    & py -3.12 -m venv .venv
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Could not create .venv. Install Python 3.12 and run setup.bat." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    & ".venv\Scripts\python.exe" -m pip install --upgrade pip
    & ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not install Python dependencies. Run setup.bat." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "  Virtual environment created."
}

# ---- Frontend ----
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js was not found. Install Node.js LTS from https://nodejs.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Frontend dependencies not found - installing them now (may take a minute)..." -ForegroundColor Yellow
    Push-Location frontend
    & npm install
    $npmExit = $LASTEXITCODE
    Pop-Location
    if ($npmExit -ne 0) {
        Write-Host "npm install FAILED (exit code $npmExit). This is usually a network or npm-registry problem." -ForegroundColor Red
        Write-Host "Check your internet connection and retry, or run:" -ForegroundColor Red
        Write-Host "    cd frontend" -ForegroundColor Red
        Write-Host "    npm install" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    if (-not (Test-Path "frontend\node_modules")) {
        Write-Host "npm install did not create 'frontend\node_modules'. Run it manually: cd frontend; npm install" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "  Frontend dependencies installed."
}

# ---- Ollama ----
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "Ollama was not found. Install it from https://ollama.com and run: ollama pull llama3.2" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Checking Ollama runtime..."
try {
    $null = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    Write-Host "  Ollama is running."
} catch {
    Write-Host "  Starting Ollama in the background..."
    Start-Process "ollama" -ArgumentList "serve"
    Start-Sleep -Seconds 3
}

Write-Host "Starting backend  -> http://127.0.0.1:8000"
Start-Process powershell -ArgumentList "-NoProfile", "-Command", "Set-Location '$PSScriptRoot'; & '.venv\Scripts\Activate.ps1'; python -m uvicorn webapp:app --host 127.0.0.1 --port 8000"

Write-Host "Starting frontend -> http://127.0.0.1:5173"
Start-Process powershell -ArgumentList "-NoProfile", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm run dev"

Start-Sleep -Seconds 7
Start-Process "http://127.0.0.1:5173"
Write-Host ""
Write-Host "Browser opened at http://127.0.0.1:5173"
Write-Host "Keep the two new windows open while you use the app."
Read-Host "Press Enter to close this window (servers keep running in their windows)"
