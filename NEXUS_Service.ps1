# ====================================================================
# NEXUS SERVICE - Inicialização Autônoma (sem VS Code)
# ====================================================================
# Este script pode ser executado por duplo-clique, Startup do Windows
# ou pelo Agendador de Tarefas. Ele inicia backend + frontend como
# processos independentes e valida que ambos estão no ar.
# ====================================================================

param(
    [switch]$NoBrowser,       # Não abrir navegador automaticamente
    [switch]$Silent,          # Sem output no console (para Task Scheduler)
    [switch]$ForceRestart     # Parar processos existentes e reiniciar
)

$ErrorActionPreference = "Continue"

# ---- Paths ----
$projectRoot = $PSScriptRoot
$backendDir  = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$logDir      = Join-Path $projectRoot "logs"
$pidFile     = Join-Path $projectRoot "logs\nexus_pids.json"
$logFile     = Join-Path $logDir "nexus_service.log"

# Criar diretório de logs se necessário
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Add-Content -Path $logFile -Value $logEntry -ErrorAction SilentlyContinue
    if (-not $Silent) {
        Write-Host $logEntry -ForegroundColor $Color
    }
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        return ($null -ne $conn -and $conn.Count -gt 0)
    } catch {
        return $false
    }
}

function Wait-ForService {
    param([string]$Url, [string]$Name, [int]$TimeoutSeconds = 30)
    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 3 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Log "✅ $Name: OK (porta respondendo)" "Green"
                return $true
            }
        } catch { }
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
    Write-Log "⚠️  $Name: Timeout após ${TimeoutSeconds}s (pode estar iniciando)" "Yellow"
    return $false
}

function Stop-ExistingProcesses {
    Write-Log "🔄 Parando processos existentes..." "Yellow"
    
    # Parar uvicorn
    Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%uvicorn%backend.main%'" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    
    # Parar node/vite na porta 5173
    Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%vite%'" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    
    # Limpar PIDs antigos do arquivo
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
    
    Start-Sleep -Seconds 2
    Write-Log "✅ Processos anteriores encerrados" "Green"
}

# ====================================================================
# INÍCIO
# ====================================================================

Write-Log "========================================" "Cyan"
Write-Log "NEXUS SERVICE - Inicialização Autônoma" "Cyan"
Write-Log "========================================" "Cyan"

# ---- Force Restart ----
if ($ForceRestart) {
    Stop-ExistingProcesses
}

# ---- Verificar se já está rodando ----
$backendRunning  = Test-PortInUse -Port 8000
$frontendRunning = Test-PortInUse -Port 5173

if ($backendRunning -and $frontendRunning -and -not $ForceRestart) {
    Write-Log "✅ NEXUS já está rodando (backend:8000, frontend:5173)" "Green"
    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:5173"
    }
    exit 0
}

# ---- Verificar pré-requisitos ----
Write-Log "📋 Verificando pré-requisitos..." "Yellow"

# Python
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
    Write-Log "⚠️  Usando Python global (venv não encontrado)" "Yellow"
} else {
    Write-Log "✅ Python venv encontrado" "Green"
}

# Node.js
try {
    $null = node --version 2>&1
    Write-Log "✅ Node.js encontrado" "Green"
} catch {
    Write-Log "❌ Node.js não encontrado! Instale Node.js 18+" "Red"
    if (-not $Silent) { Read-Host "Pressione Enter para fechar" }
    exit 1
}

# ---- Iniciar Backend ----
if (-not $backendRunning) {
    Write-Log "🚀 Iniciando Backend (porta 8000)..." "Cyan"
    
    $backendJob = Start-Process -FilePath $pythonExe `
        -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -PassThru
    
    Write-Log "   PID Backend: $($backendJob.Id)" "Gray"
} else {
    Write-Log "✅ Backend já rodando na porta 8000" "Green"
}

# ---- Iniciar Frontend ----
if (-not $frontendRunning) {
    Write-Log "🚀 Iniciando Frontend (porta 5173)..." "Cyan"
    
    # Verificar node_modules
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Log "📦 Instalando dependências do frontend..." "Yellow"
        Push-Location $frontendDir
        npm install --no-audit --no-fund 2>&1 | Out-Null
        Pop-Location
    }
    
    $frontendJob = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "cd /d `"$frontendDir`" && npx vite --host 127.0.0.1 --port 5173" `
        -WindowStyle Hidden `
        -PassThru
    
    Write-Log "   PID Frontend: $($frontendJob.Id)" "Gray"
} else {
    Write-Log "✅ Frontend já rodando na porta 5173" "Green"
}

# ---- Salvar PIDs ----
$pids = @{
    backend_pid  = if ($backendJob)  { $backendJob.Id }  else { $null }
    frontend_pid = if ($frontendJob) { $frontendJob.Id } else { $null }
    started_at   = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}
$pids | ConvertTo-Json | Set-Content -Path $pidFile -ErrorAction SilentlyContinue

# ---- Validar serviços ----
Write-Log "⏳ Aguardando serviços..." "Yellow"
Start-Sleep -Seconds 3

$backendOk  = Wait-ForService -Url "http://127.0.0.1:8000/health" -Name "Backend" -TimeoutSeconds 20
$frontendOk = Wait-ForService -Url "http://127.0.0.1:5173" -Name "Frontend" -TimeoutSeconds 25

Write-Log "========================================" "Cyan"
if ($backendOk -and $frontendOk) {
    Write-Log "🎉 NEXUS ONLINE - Todos os serviços ativos!" "Green"
} elseif ($backendOk) {
    Write-Log "⚠️  NEXUS parcialmente online (frontend pode levar mais tempo)" "Yellow"
} else {
    Write-Log "❌ Problemas na inicialização. Verifique logs\nexus_service.log" "Red"
}

Write-Log "   🌐 Interface: http://127.0.0.1:5173" "White"
Write-Log "   🔌 API:       http://127.0.0.1:8000" "White"
Write-Log "   📚 Docs:      http://127.0.0.1:8000/docs" "White"
Write-Log "========================================" "Cyan"

# ---- Abrir navegador ----
if (-not $NoBrowser -and ($backendOk -or $frontendOk)) {
    Start-Sleep -Seconds 1
    Start-Process "http://127.0.0.1:5173"
}

if (-not $Silent) {
    Write-Host ""
    Write-Host "💡 Os serviços estão rodando em segundo plano." -ForegroundColor Yellow
    Write-Host "   Para parar: .\NEXUS_Stop.ps1 ou feche pelo Gerenciador de Tarefas" -ForegroundColor Yellow
    Write-Host ""
}
