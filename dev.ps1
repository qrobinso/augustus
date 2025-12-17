# Augustus Development Script
# Runs both backend and frontend with easy shutdown (Ctrl+C)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  =======================================" -ForegroundColor Cyan
Write-Host "         AUGUSTUS - Development Mode     " -ForegroundColor Cyan
Write-Host "         Audio Intelligence Platform     " -ForegroundColor Cyan
Write-Host "  =======================================" -ForegroundColor Cyan
Write-Host ""

# Store the root directory
$ROOT_DIR = $PSScriptRoot
if (-not $ROOT_DIR) {
    $ROOT_DIR = (Get-Location).Path
}

# Check for Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python not found. Please install Python 3.11+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Python found: $($pythonCmd.Source)" -ForegroundColor Green

# Check for Node.js
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "[ERROR] Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Node.js found: $($nodeCmd.Source)" -ForegroundColor Green

# Check for npm
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    Write-Host "[ERROR] npm not found. Please install Node.js 18+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check for .env file
$envFile = Join-Path $ROOT_DIR ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[WARN] No .env file found. Creating template..." -ForegroundColor Yellow
    $envContent = "# Augustus Configuration`n`n# OpenRouter API key (required for LLM)`nOPENROUTER_API_KEY=your-openrouter-api-key`n`n# OpenRouter model (optional)`nOPENROUTER_MODEL=anthropic/claude-3.5-sonnet`n`n# TTS Provider: piper (local) or elevenlabs (cloud)`nTTS_PROVIDER=piper`n`n# ElevenLabs API key (only if using elevenlabs)`nELEVENLABS_API_KEY=`n`n# Debug mode`nDEBUG=true"
    $envContent | Out-File -FilePath $envFile -Encoding UTF8
    Write-Host "[INFO] Created .env file. Add your OPENROUTER_API_KEY to use LLM features." -ForegroundColor Yellow
}

# Load .env file
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Create necessary directories
$dirs = @("audio", "models", "data")
foreach ($dirName in $dirs) {
    $dir = Join-Path $ROOT_DIR $dirName
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# Setup backend virtual environment if needed
$VENV_PATH = Join-Path $ROOT_DIR "backend\venv"
$venvPython = Join-Path $VENV_PATH "Scripts\python.exe"
$venvPip = Join-Path $VENV_PATH "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[INFO] Creating Python virtual environment..." -ForegroundColor Yellow
    $backendDir = Join-Path $ROOT_DIR "backend"
    Push-Location $backendDir
    & python -m venv venv
    Pop-Location
    
    if (-not (Test-Path $venvPython)) {
        Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Host "[OK] Virtual environment ready" -ForegroundColor Green

# Install/update backend dependencies
$REQUIREMENTS_FILE = Join-Path $ROOT_DIR "backend\requirements.txt"
Write-Host "[INFO] Installing backend dependencies..." -ForegroundColor Yellow
& $venvPip install --upgrade pip -q
& $venvPip install -r $REQUIREMENTS_FILE
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install backend dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Backend dependencies installed" -ForegroundColor Green

# Install frontend dependencies if needed
$NODE_MODULES = Join-Path $ROOT_DIR "frontend\node_modules"
if (-not (Test-Path $NODE_MODULES)) {
    Write-Host "[INFO] Installing frontend dependencies..." -ForegroundColor Yellow
    $frontendDir = Join-Path $ROOT_DIR "frontend"
    Push-Location $frontendDir
    & npm install
    Pop-Location
}
Write-Host "[OK] Frontend dependencies ready" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Starting Augustus Services..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "   Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host ""

# Start backend process
$backendDir = Join-Path $ROOT_DIR "backend"

$backendProcess = Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" `
    -WorkingDirectory $backendDir `
    -PassThru

Write-Host "[OK] Backend started (PID: $($backendProcess.Id))" -ForegroundColor Green

# Start frontend
$frontendDir = Join-Path $ROOT_DIR "frontend"
Push-Location $frontendDir
$frontendProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory $frontendDir `
    -PassThru
Pop-Location

Write-Host "[OK] Frontend started (PID: $($frontendProcess.Id))" -ForegroundColor Green

# Function to cleanup processes
function Stop-AllProcesses {
    Write-Host ""
    Write-Host "[INFO] Shutting down Augustus..." -ForegroundColor Yellow
    
    # Stop backend
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Write-Host "[INFO] Stopping backend..." -ForegroundColor Gray
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Stop frontend
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Write-Host "[INFO] Stopping frontend..." -ForegroundColor Gray
        Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Kill any remaining node/python processes on our ports
    $portsToCheck = @(8000, 3000)
    foreach ($port in $portsToCheck) {
        try {
            $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
            foreach ($conn in $connections) {
                if ($conn.OwningProcess -gt 0) {
                    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {}
    }
    
    Write-Host "[OK] Augustus stopped." -ForegroundColor Green
}

# Handle Ctrl+C
try {
    Write-Host ""
    Write-Host "[OK] Services running! Open http://localhost:3000 in your browser." -ForegroundColor Green
    Write-Host "[INFO] Press Ctrl+C to stop..." -ForegroundColor Gray
    Write-Host ""
    
    # Wait for either process to exit
    while ($true) {
        if ($backendProcess.HasExited -and $frontendProcess.HasExited) {
            Write-Host "[INFO] All processes exited" -ForegroundColor Yellow
            break
        }
        Start-Sleep -Seconds 2
    }
}
catch {
    # Ctrl+C pressed
}
finally {
    Stop-AllProcesses
}
