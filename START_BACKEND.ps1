# ====================================
# START BACKEND - NEXUS API
# ====================================

$ErrorActionPreference = "Stop"

Write-Host "🚀 Iniciando NEXUS Backend..." -ForegroundColor Cyan

# Navegar para diretório do projeto
Push-Location $PSScriptRoot

# Configurar Python path
$env:PYTHONPATH = $PSScriptRoot

# Verificar venv
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "✅ Ambiente virtual encontrado" -ForegroundColor Green
    $pythonExe = ".venv\Scripts\python.exe"
} else {
    Write-Host "⚠️  Usando Python global" -ForegroundColor Yellow
    $pythonExe = "python"
}

# Iniciar servidor
Write-Host "🌐 Servidor rodando em: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "📚 Documentação: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "❤️  Health: http://127.0.0.1:8000/health" -ForegroundColor Green
Write-Host ""
Write-Host "Pressione CTRL+C para parar" -ForegroundColor Yellow
Write-Host ""

& $pythonExe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
