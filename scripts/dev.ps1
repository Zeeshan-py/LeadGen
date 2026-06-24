$ErrorActionPreference = "Stop"

Write-Host "Starting LeadForge AI Postgres with Docker Compose..."
docker compose up -d postgres

Write-Host "Backend: http://localhost:8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\backend'; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

Write-Host "Frontend: http://localhost:3000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\frontend'; npm run dev"
