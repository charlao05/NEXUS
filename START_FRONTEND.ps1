# ====================================
# START FRONTEND - NEXUS UI
# ====================================

$ErrorActionPreference = "Stop"

Write-Host "🎨 Iniciando NEXUS Frontend..." -ForegroundColor Cyan

# Navegar para frontend
Push-Location "$PSScriptRoot\frontend"

# Verificar node_modules
if (-not (Test-Path "node_modules")) {
    Write-Host "📦 Instalando dependências..." -ForegroundColor Yellow
    npm install --no-audit --no-fund
}

# Iniciar servidor Vite
    $port = 5173
    Write-Host "🌐 Interface disponível em: http://127.0.0.1:$port" -ForegroundColor Green
    Write-Host ""
    Write-Host "Pressione CTRL+C para parar" -ForegroundColor Yellow
    Write-Host ""
    npm run dev -- --host 127.0.0.1 --port $port
