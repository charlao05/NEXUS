# NEXUS - Script de Inicialização Automática
# ============================================
# Este script inicia o backend e frontend do NEXUS automaticamente
# Execute como administrador para criar tarefa agendada

param(
    [switch]$Install,      # Instalar como tarefa agendada
    [switch]$Uninstall,    # Remover tarefa agendada
    [switch]$Start         # Apenas iniciar agora
)

$NexusPath = "C:\Users\Charles\Desktop\NEXUS"
$VenvActivate = "$NexusPath\.venv\Scripts\Activate.ps1"

function Start-NexusServices {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  NEXUS - Iniciando Serviços" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    # Verificar se já está rodando
    $backendRunning = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    $frontendRunning = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    
    if ($backendRunning) {
        Write-Host "[OK] Backend já está rodando na porta 8000" -ForegroundColor Green
    } else {
        Write-Host "[...] Iniciando Backend..." -ForegroundColor Yellow
        Start-Process powershell -ArgumentList "-WindowStyle Hidden", "-Command", @"
cd '$NexusPath'
& '$VenvActivate'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
"@ -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "[OK] Backend iniciado na porta 8000" -ForegroundColor Green
    }
    
    if ($frontendRunning) {
        Write-Host "[OK] Frontend já está rodando na porta 5173" -ForegroundColor Green
    } else {
        Write-Host "[...] Iniciando Frontend..." -ForegroundColor Yellow
        Start-Process powershell -ArgumentList "-WindowStyle Hidden", "-Command", @"
cd '$NexusPath\frontend'
npx vite --port 5173 --host
"@ -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "[OK] Frontend iniciado na porta 5173" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  NEXUS está pronto!" -ForegroundColor Green
    Write-Host "  Acesse: http://localhost:5173" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}

function Install-StartupTask {
    Write-Host "Instalando NEXUS para iniciar automaticamente..." -ForegroundColor Yellow
    
    $taskName = "NEXUS_AutoStart"
    $scriptPath = $MyInvocation.MyCommand.Path
    
    # Remover tarefa existente
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Criar ação
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`" -Start"
    
    # Trigger: ao fazer logon
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    
    # Configurações
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    
    # Registrar tarefa
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Inicia o NEXUS automaticamente"
    
    Write-Host "[OK] NEXUS configurado para iniciar automaticamente no login!" -ForegroundColor Green
    Write-Host "Para remover, execute: .\START_NEXUS.ps1 -Uninstall" -ForegroundColor Cyan
}

function Uninstall-StartupTask {
    $taskName = "NEXUS_AutoStart"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Inicialização automática removida" -ForegroundColor Green
}

# Executar baseado nos parâmetros
if ($Install) {
    Install-StartupTask
    Start-NexusServices
} elseif ($Uninstall) {
    Uninstall-StartupTask
} else {
    Start-NexusServices
}
