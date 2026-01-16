# ===========================================
# DSU IQC Backend Starter (with external venv)
# ===========================================

Write-Host "🚀 Starting Flask Backend for IQC Portal..." -ForegroundColor Cyan

# Path to your virtual environment (one folder up from backend)
$venvPath = "..\venv\Scripts\Activate.ps1"

if (Test-Path $venvPath) {
    Write-Host "✅ Activating virtual environment..." -ForegroundColor Yellow
    & $venvPath
} else {
    Write-Host "❌ Could not find virtual environment at $venvPath" -ForegroundColor Red
    exit
}

# Set Flask environment variables
$env:FLASK_APP = "main.py"
$env:FLASK_ENV = "development"

# Run Flask server
Write-Host "💻 Running Flask on http://localhost:5000 ..." -ForegroundColor Green
flask run --port=5000

Pause
