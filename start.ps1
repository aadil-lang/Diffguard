# DiffGuard Quick Start Script for Windows PowerShell
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       Starting DiffGuard Systems         " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Start Backend in new window
Write-Host "[1/2] Launching Backend API (FastAPI) on port 8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

# Start Frontend
Write-Host "[2/2] Launching Frontend (Next.js) on port 3000..." -ForegroundColor Green
cd frontend
npm run dev
