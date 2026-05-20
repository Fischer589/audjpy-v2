# AUDJPY V2 - Windows VPS Deployment Script
# Requires: Windows PowerShell 5.1+, Python 3.11+, Git
# ASCII-only: safe for all Windows code pages
#
# Usage:
#   .\deploy\windows\deploy.ps1 [-BotDir "C:\bots\audjpy-v2"] [-Branch "main"]

param(
    [string]$BotDir  = "C:\bots\audjpy-v2",
    [string]$Branch  = "main",
    [string]$RepoUrl = "https://github.com/Fischer589/audjpy-v2.git"
)

$ErrorActionPreference = "Stop"

function Write-Step { param([int]$N, [string]$Msg)
    Write-Host ""
    Write-Host "[$N/14] $Msg" -ForegroundColor Cyan
}

function Write-Ok   { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  WARN $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "  FAIL $Msg" -ForegroundColor Red; exit 1 }

# Step 1: Prerequisites
Write-Step 1 "Verifying prerequisites"

try {
    $pyVer = (python --version 2>&1)
    Write-Ok "Python: $pyVer"
} catch {
    Write-Fail "Python not found. Install Python 3.11+ and add to PATH."
}

try {
    $gitVer = (git --version 2>&1)
    Write-Ok "Git: $gitVer"
} catch {
    Write-Fail "Git not found. Install Git and add to PATH."
}

# Step 2: Bot directory
Write-Step 2 "Checking bot directory"

if (-not (Test-Path $BotDir)) {
    New-Item -ItemType Directory -Path $BotDir -Force | Out-Null
    Write-Ok "Created: $BotDir"
} else {
    Write-Ok "Exists:  $BotDir"
}

# Step 3: Clone or pull
Write-Step 3 "Syncing code from repository"

$gitDir = Join-Path $BotDir ".git"
if (-not (Test-Path $gitDir)) {
    Write-Host "  Cloning $RepoUrl ..." -ForegroundColor Gray
    git clone $RepoUrl $BotDir 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Fail "git clone failed." }
    Write-Ok "Cloned $RepoUrl -> $BotDir"
} else {
    Set-Location $BotDir
    git fetch origin 2>&1 | Out-Null
    git checkout $Branch 2>&1 | Out-Null
    git pull origin $Branch 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Fail "git pull failed." }
    Write-Ok "Pulled latest $Branch"
}

Set-Location $BotDir

# Step 4: Show active commit
Write-Step 4 "Active commit"

$commitSha  = (git rev-parse HEAD 2>&1).Trim()
$commitMsg  = (git log -1 --format="%s" 2>&1).Trim()
$commitDate = (git log -1 --format="%ci" 2>&1).Trim()

Write-Host ""
Write-Host "  SHA:  $commitSha" -ForegroundColor White
Write-Host "  Msg:  $commitMsg"
Write-Host "  Date: $commitDate"

# Step 5: Virtual environment
Write-Step 5 "Setting up virtual environment"

$venvPath = Join-Path $BotDir ".venv"
if (-not (Test-Path $venvPath)) {
    python -m venv .venv 2>&1 | Out-Null
    Write-Ok "Created .venv"
} else {
    Write-Ok ".venv already exists"
}

$pip    = Join-Path $venvPath "Scripts\pip.exe"
$python = Join-Path $venvPath "Scripts\python.exe"

# Step 6: Install dependencies
Write-Step 6 "Installing dependencies"

& $pip install --upgrade pip 2>&1 | Out-Null
& $pip install -r requirements.txt 2>&1
if ($LASTEXITCODE -ne 0) { Write-Fail "pip install failed." }
Write-Ok "Dependencies installed"

# Step 7: Verify config
Write-Step 7 "Checking configuration"

$mainConfig = Join-Path $BotDir "config\settings.yaml"
if (-not (Test-Path $mainConfig)) {
    Write-Fail "config\settings.yaml not found. Check repository."
}
Write-Ok "config\settings.yaml present"

# Step 8: Migrate local config
Write-Step 8 "Local config migration"

$localConfig   = Join-Path $BotDir "config\settings.local.yaml"
$exampleConfig = Join-Path $BotDir "config\settings.local.yaml.example"

if (-not (Test-Path $localConfig)) {
    if (Test-Path $exampleConfig) {
        Copy-Item $exampleConfig $localConfig
        Write-Warn "settings.local.yaml created from example. EDIT IT before starting live trading."
    } else {
        Write-Warn "No settings.local.yaml and no example found. Using tracked defaults only."
    }
} else {
    Write-Ok "settings.local.yaml exists (not modified)"
}

# Step 9: Runtime directories
Write-Step 9 "Creating runtime directories"

foreach ($dir in @("logs", "journals", "snapshots", "analytics", "config")) {
    $path = Join-Path $BotDir $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}
Write-Ok "Runtime directories ready"

# Step 10: Smoke test
Write-Step 10 "Smoke test (import check)"

$smokeScript = @"
import sys
sys.path.insert(0, r'$BotDir')
try:
    from src.config import load_settings
    from src.models.candle import Candle
    from src.strategy.trend_bias import analyze_htf_trend
    from src.strategy.corrective_structure import detect_correction
    from src.strategy.continuation_engine import detect_failure, evaluate_continuation
    from src.strategy.signal_quality import score_signal
    from src.risk.risk_manager import RiskManager
    s = load_settings(config_path=r'$BotDir\config\settings.yaml')
    print('SMOKE_OK mode=' + s.execution_mode)
except Exception as e:
    print('SMOKE_FAIL ' + str(e))
    sys.exit(1)
"@

$smokeResult = & $python -c $smokeScript 2>&1
Write-Host "  $smokeResult"
if ($smokeResult -notmatch "SMOKE_OK") {
    Write-Fail "Smoke test failed. Check Python environment and config."
}
Write-Ok "Smoke test passed"

# Step 11: Test suite
Write-Step 11 "Running test suite"

$pytest = Join-Path $venvPath "Scripts\pytest.exe"
if (Test-Path $pytest) {
    & $pytest tests/ -q --tb=short 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Some tests failed. Review output above before starting the bot."
    } else {
        Write-Ok "All tests passed"
    }
} else {
    Write-Warn "pytest not found in venv -- skipping test run"
}

# Step 12: Stop existing bot process
Write-Step 12 "Stopping existing bot (if running)"

$botProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -match "audjpy"
}

if ($botProcs) {
    $botProcs | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Ok "Stopped $($botProcs.Count) existing process(es)"
} else {
    Write-Ok "No existing bot process found"
}

# Step 13: Start bot
Write-Step 13 "Starting bot"

$startCmd = "& '$python' main.py --config config\settings.yaml"
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$BotDir'; $startCmd`"" -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Ok "Bot started in new window"

# Step 14: Summary
Write-Step 14 "Deployment summary"

Write-Host ""
Write-Host "  AUDJPY V2 deployed successfully" -ForegroundColor Green
Write-Host ""
Write-Host "  Bot directory : $BotDir"
Write-Host "  Active commit : $commitSha"
Write-Host "  Branch        : $Branch"
Write-Host "  Log file      : $BotDir\logs\live.log"
Write-Host ""
Write-Host "  To tail logs:"
Write-Host "    Get-Content '$BotDir\logs\live.log' -Wait -Tail 50"
Write-Host ""
Write-Host "  To stop the bot:"
Write-Host "    Get-Process python | Stop-Process"
Write-Host ""
