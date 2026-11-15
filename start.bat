@echo off
echo ==========================================
echo        Starting DiffGuard Systems         
echo ==========================================

echo [1/2] Launching Backend API on port 8000...
start "DiffGuard Backend" cmd /k "cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Launching Next.js Frontend on port 3000...
cd frontend
npm run dev

