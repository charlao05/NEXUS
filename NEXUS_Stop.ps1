# ====================================================================
# NEXUS STOP - Parar todos os serviços
# ====================================================================

$ErrorActionPreference = "Continue"

Write-Host "🛑 Parando serviços NEXUS..." -ForegroundColor Yellow

# Parar uvicorn (backend)
$uvicorn = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%uvicorn%backend.main%'" -ErrorAction SilentlyContinue
if ($uvicorn) {
    $uvicorn | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "   ✅ Backend (PID $($_.ProcessId)) parado" -ForegroundColor Green
    }
} else {
    Write-Host "   ℹ️  Backend não estava rodando" -ForegroundColor Gray
}

# Parar vite/node (frontend)
$vite = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%vite%5173%'" -ErrorAction SilentlyContinue
if ($vite) {
    $vite | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "   ✅ Frontend (PID $($_.ProcessId)) parado" -ForegroundColor Green
    }
} else {
    # Tentar matcher mais amplo
    $node = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%vite%'" -ErrorAction SilentlyContinue
    if ($node) {
        $node | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "   ✅ Vite (PID $($_.ProcessId)) parado" -ForegroundColor Green
        }
    } else {
        Write-Host "   ℹ️  Frontend não estava rodando" -ForegroundColor Gray
    }
}

# Limpar PID file
$pidFile = Join-Path $PSScriptRoot "logs\nexus_pids.json"
if (Test-Path $pidFile) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "✅ Todos os serviços NEXUS foram parados." -ForegroundColor Green
