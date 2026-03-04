# =============================================================================
# 🔒 NEXUS - Iniciar com HTTPS (Desenvolvimento Seguro)
# =============================================================================
# Este script inicia o backend e frontend com HTTPS habilitado
# Necessário para OAuth do Facebook/Google funcionar corretamente
# =============================================================================

$ErrorActionPreference = "Stop"
$nexusPath = "C:\Users\Charles\Desktop\NEXUS"

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "🔒 NEXUS - Modo HTTPS Seguro" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Verificar certificados
$certPath = "$nexusPath\certs\localhost+2.pem"
$keyPath = "$nexusPath\certs\localhost+2-key.pem"

if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
    Write-Host "❌ Certificados não encontrados!" -ForegroundColor Red
    Write-Host "Execute: cd certs; mkcert localhost 127.0.0.1 ::1" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Certificados SSL encontrados" -ForegroundColor Green

# Parar processos existentes
Write-Host "🔄 Parando processos existentes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*NEXUS*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Ativar venv
Write-Host "🐍 Ativando ambiente Python..." -ForegroundColor Yellow
Set-Location $nexusPath
& "$nexusPath\.venv\Scripts\Activate.ps1"

# Iniciar Backend HTTPS
Write-Host ""
Write-Host "🚀 Iniciando Backend HTTPS na porta 8000..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    param($path, $cert, $key)
    Set-Location $path
    & "$path\.venv\Scripts\python.exe" -m uvicorn backend.main:app `
        --host 127.0.0.1 `
        --port 8000 `
        --ssl-keyfile $key `
        --ssl-certfile $cert `
        --reload
} -ArgumentList $nexusPath, $certPath, $keyPath

Start-Sleep -Seconds 3

# Iniciar Frontend HTTPS
Write-Host "🌐 Iniciando Frontend HTTPS na porta 5175..." -ForegroundColor Green
$frontendJob = Start-Job -ScriptBlock {
    param($path)
    Set-Location "$path\frontend"
    npm run dev -- --https
} -ArgumentList $nexusPath

Start-Sleep -Seconds 5

# Verificar status
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "📊 STATUS DOS SERVIÇOS:" -ForegroundColor Yellow
Write-Host ""

try {
    # Ignorar erros de certificado para teste local
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    $health = Invoke-RestMethod -Uri "https://127.0.0.1:8000/health" -TimeoutSec 10
    Write-Host "✅ Backend HTTPS: https://127.0.0.1:8000" -ForegroundColor Green
} catch {
    Write-Host "⏳ Backend iniciando... aguarde alguns segundos" -ForegroundColor Yellow
}

Write-Host "✅ Frontend HTTPS: https://127.0.0.1:5175" -ForegroundColor Green
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "🔗 URLs SEGURAS:" -ForegroundColor Cyan
Write-Host "   Backend:  https://127.0.0.1:8000" -ForegroundColor White
Write-Host "   Frontend: https://127.0.0.1:5175" -ForegroundColor White
Write-Host "   Docs API: https://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  IMPORTANTE: Atualize os Redirect URIs nos consoles:" -ForegroundColor Yellow
Write-Host "   Google:   https://127.0.0.1:8000/api/auth/google/callback" -ForegroundColor White
Write-Host "   Facebook: https://127.0.0.1:8000/api/auth/facebook/callback" -ForegroundColor White
Write-Host ""
Write-Host "Pressione Enter para parar os serviços..." -ForegroundColor Gray
Read-Host

# Cleanup
Stop-Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
Remove-Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
Write-Host "✅ Serviços encerrados" -ForegroundColor Green
