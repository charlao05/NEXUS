# ====================================
# NEXUS - INICIALIZAÇÃO COMPLETA
# ====================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         NEXUS - Sistema Unificado de IA e Automação          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Navegar para raiz do projeto
$projectRoot = $PSScriptRoot
Push-Location $projectRoot

# ============================================================================
# VERIFICAR PRÉ-REQUISITOS
# ============================================================================

Write-Host "📋 Verificando pré-requisitos..." -ForegroundColor Yellow

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python não encontrado! Instale Python 3.9+" -ForegroundColor Red
    exit 1
}

# Verificar Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "✅ Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js não encontrado! Instale Node.js 18+" -ForegroundColor Red
    exit 1
}

# Verificar npm
try {
    $npmVersion = npm --version 2>&1
    Write-Host "✅ npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ npm não encontrado!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ====================================
# INICIAR SERVIÇOS
# ====================================

Write-Host "🚀 Iniciando serviços..." -ForegroundColor Cyan
Write-Host ""

# Iniciar Backend em nova janela
Write-Host "🔹 Backend (API)..." -ForegroundColor White
Start-Process powershell -ArgumentList "-NoExit", "-File", "$projectRoot\START_BACKEND.ps1" -WindowStyle Normal
Start-Sleep -Seconds 3

# Iniciar Frontend em nova janela
Write-Host "🔹 Frontend (UI)..." -ForegroundColor White
Start-Process powershell -ArgumentList "-NoExit", "-File", "$projectRoot\START_FRONTEND.ps1" -WindowStyle Normal
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    ✅ NEXUS INICIADO!                         ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "📍 URLs de Acesso:" -ForegroundColor Cyan
Write-Host "   🌐 Interface: http://127.0.0.1:5173" -ForegroundColor White
Write-Host "   🔌 API:       http://127.0.0.1:8000" -ForegroundColor White
Write-Host "   📚 Docs:      http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""

Write-Host "💡 Dica: As janelas do Backend e Frontend foram abertas separadamente" -ForegroundColor Yellow
Write-Host "   Para parar os serviços, feche as janelas ou pressione CTRL+C nelas" -ForegroundColor Yellow
Write-Host ""

# Validar serviços (aguardar 5 segundos)
Write-Host "⏳ Aguardando serviços iniciarem..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "🔍 Validando serviços..." -ForegroundColor Yellow

# Testar Backend
try {
    $healthResponse = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -Method GET -TimeoutSec 5
    if ($healthResponse.StatusCode -eq 200) {
        Write-Host "   ✅ Backend: OK" -ForegroundColor Green
    }
} catch {
    Write-Host "   ⚠️  Backend: Ainda iniciando (aguarde mais alguns segundos)" -ForegroundColor Yellow
}

# Testar Frontend
try {
    $frontendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -Method GET -TimeoutSec 5
    if ($frontendResponse.StatusCode -eq 200) {
        Write-Host "   ✅ Frontend: OK" -ForegroundColor Green
    }
} catch {
    Write-Host "   ⚠️  Frontend: Ainda iniciando (aguarde mais alguns segundos)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Sistema pronto para uso!" -ForegroundColor Green
Write-Host ""

# Abrir navegador automaticamente
Start-Process "http://127.0.0.1:5173"

Write-Host "Pressione qualquer tecla para fechar esta janela..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
