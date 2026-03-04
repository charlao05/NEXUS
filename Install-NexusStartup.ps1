# ====================================================================
# INSTALAR NEXUS NO STARTUP DO WINDOWS
# ====================================================================
# Executa uma vez para registrar o NEXUS na inicialização automática
# do Windows. Após executar, o NEXUS inicia automaticamente quando
# o computador ligar / o usuário fizer login.
# ====================================================================

param(
    [switch]$Uninstall    # Remover do Startup
)

$ErrorActionPreference = "Stop"

$startupFolder = [System.IO.Path]::Combine(
    [Environment]::GetFolderPath("Startup"),
    ""
)
$shortcutPath = Join-Path $startupFolder "NEXUS.lnk"
$batFile = Join-Path $PSScriptRoot "NEXUS_Start.bat"

if ($Uninstall) {
    if (Test-Path $shortcutPath) {
        Remove-Item $shortcutPath -Force
        Write-Host "✅ NEXUS removido da inicialização automática do Windows." -ForegroundColor Green
    } else {
        Write-Host "ℹ️  NEXUS não estava configurado no Startup." -ForegroundColor Yellow
    }
    exit 0
}

# Criar atalho no Startup
Write-Host "🔧 Configurando NEXUS na inicialização do Windows..." -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $batFile)) {
    Write-Host "❌ Arquivo NEXUS_Start.bat não encontrado em: $PSScriptRoot" -ForegroundColor Red
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $batFile
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = "NEXUS - Sistema Unificado de IA e Automação"
$shortcut.WindowStyle = 7  # 7 = Minimized
$shortcut.Save()

Write-Host "✅ NEXUS adicionado à inicialização automática!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Atalho criado em:" -ForegroundColor White
Write-Host "   $shortcutPath" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 O que acontece agora:" -ForegroundColor Yellow
Write-Host "   • Ao fazer login no Windows, o NEXUS inicia automaticamente" -ForegroundColor White
Write-Host "   • Backend (API) + Frontend (Interface) sobem em segundo plano" -ForegroundColor White
Write-Host "   • O navegador abre em http://127.0.0.1:5173" -ForegroundColor White
Write-Host ""
Write-Host "🛑 Para remover da inicialização:" -ForegroundColor Yellow
Write-Host "   .\Install-NexusStartup.ps1 -Uninstall" -ForegroundColor White
Write-Host ""
