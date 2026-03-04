# 🚀 START_NEXUS_FULL.ps1 — Script robusto e autossuficiente para inicialização do NEXUS
# Características: Validação rigorosa, tratamento de erros detalhado, auto-correção, desempenho máximo e logging abrangente

$logFile = "C:\Users\Charles\Desktop\NEXUS\logs\nexus_startup.log"
if (!(Test-Path (Split-Path $logFile))) { New-Item -ItemType Directory -Path (Split-Path $logFile) -Force | Out-Null }

function Log {
    param([string]$msg, [string]$level = "INFO")
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $line = "$timestamp [$Level] $Message"
        Write-Host $line
        Add-Content -Path $logFile -Value $line
}

## Substituição de funções customizadas por cmdlets aprovados

# Validação de arquivo
if (-not (Test-Path $venvPath)) {
    Write-NexusLog "❌ Ambiente virtual Python não encontrado em $venvPath" "ERROR"
    exit 1
}

# Validação de variável de ambiente
$env_var = [System.Environment]::GetEnvironmentVariable("STRIPE_SECRET_KEY")
if ($null -eq $env_var -or !$env_var) {
    Write-NexusLog "❌ Variável STRIPE_SECRET_KEY não definida" "ERROR"
    exit 1
}

Log "==============================================================="
Write-NexusLog "==============================================================="
Write-NexusLog "INICIANDO NEXUS (BACKEND + FRONTEND)"
Write-NexusLog "==============================================================="
    Write-NexusLog "Tentando criar ambiente virtual Python automaticamente..." "INFO"
    Write-NexusLog "Backend FastAPI será logado em $backendLog (porta $port)"
    Write-NexusLog "✅ Porta 8000 liberada" "INFO"
    Write-NexusLog "⚠️  Nenhuma regra de firewall configurada para porta 8000" "WARN"
            Write-NexusLog "[Monitor] Testando porta $port..."
                    Write-NexusLog "Porta $port já está em uso por $($proc.ProcessName) (PID: $($proc.Id))" "WARN"
                            Write-NexusLog "Porta $port liberada. Tentando iniciar backend..." "INFO"
                        Write-NexusLog "Migrando para próxima porta alternativa..." "INFO"
                    Write-NexusLog "Porta $port ocupada, mas processo não identificado." "ERROR"
                Write-NexusLog "Porta $port está livre. Iniciando backend..." "INFO"
                Write-NexusLog "Aguardando backend subir na porta $chosenPort... tentativa $i de $maxTries (espera $waitStep s)"
                    Write-NexusLog "Backend FastAPI está saudável na porta $chosenPort" "INFO"
                    Write-NexusLog "Backend ainda não respondeu na porta $chosenPort (tentativa $i)" "WARN"
                Write-NexusLog "Backend não respondeu após $($maxTries*$waitStep) segundos na porta $chosenPort. Diagnóstico automático..." "ERROR"
                    Write-NexusLog "Tentando reiniciar backend na mesma porta (Nível 1)..." "WARN"
                    Write-NexusLog "Nível 2: Tentando próxima porta alternativa..." "WARN"
            Write-NexusLog "Nível 1 falhou. Escalando para Nível 2 (portas alternativas)..." "WARN"
            Write-NexusLog "Nível 2 falhou. Escalando para Nível 3 (diagnóstico avançado)..." "ERROR"
            Write-NexusLog "Se persistir, tente reiniciar a máquina ou reconfigurar firewall/rede." "FATAL"
    Write-NexusLog "[Relatório de incidente] Timeline: $($incidentTimeline -join ' | ')" "INFO"
    Write-NexusLog "ATENÇÃO: Backend foi iniciado em porta alternativa $chosenPort. Atualize configurações do frontend/API se necessário." "WARN"

# 1. Ativar ambiente virtual Python
Try-Start {
    $venvPath = "C:\Users\Charles\Desktop\NEXUS\.venv\Scripts\Activate.ps1"
    Validate-File $venvPath "Ambiente virtual Python"
    . $venvPath
} "Ativação do ambiente virtual Python" {
    # Auto-correção: tentar criar o venv se não existir
    Log "Tentando criar ambiente virtual Python automaticamente..." "INFO"
    $pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (!$pyExe) { throw "Python não encontrado no PATH. Instale Python 3.10+ e tente novamente." }
    & $pyExe -m venv "C:\Users\Charles\Desktop\NEXUS\.venv"
}

# 2. Carregar variáveis do .env do NEXUS
Try-Start {
    $envFile = "C:\Users\Charles\Desktop\NEXUS\.env"
    Validate-File $envFile ".env do NEXUS"
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^(\w+)=(.*)$') {
            $name = $matches[1]
            $value = $matches[2]
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    # Validação de variáveis críticas
    $criticalVars = @("STRIPE_SECRET_KEY", "OPENAI_API_KEY", "JWT_SECRET", "DATABASE_URL")
    foreach ($var in $criticalVars) { Validate-EnvVar $var $var }
} "Carregamento do .env e validação de variáveis"


# 3. Iniciar backend FastAPI (NEXUS) com monitoramento e correção inteligente de porta
function Test-Port {
    param([int]$port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect('127.0.0.1', $port)
        $tcp.Close()
        return $true
    } catch { return $false }
}

function Get-PortProcess {
    param([int]$port)
    $netstat = netstat -ano | Select-String ":$port "
    if ($netstat) {
        $procId = ($netstat -split '\s+')[-1]
        try { return Get-Process -Id $procId -ErrorAction Stop } catch { return $null }
    }
    return $null
}

## Liberação de porta usando Stop-Process
$process = Get-Process | Where-Object { $_.Handles -gt 0 } | Where-Object { (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -eq $_.Id }
if ($process) {
    Stop-Process -Id $process.Id -Force
    Log "✅ Porta 8000 liberada" "INFO"
}

function Find-AvailablePort {
    param([int[]]$candidates)
    foreach ($p in $candidates) { if (-not (Test-Port $p)) { return $p } }
    return $null
}

## Checagem de firewall usando Get-NetFirewallRule
$rule = Get-NetFirewallRule -DisplayName "*8000*" -ErrorAction SilentlyContinue
if (-not $rule) {
    Log "⚠️  Nenhuma regra de firewall configurada para porta 8000" "WARN"
}

function Start-Backend {
    param([int]$port)
    $backendPath = "C:\Users\Charles\Desktop\NEXUS\backend"
    Validate-File (Join-Path $backendPath "main.py") "Backend FastAPI main.py"
    $backendLog = "C:\Users\Charles\Desktop\NEXUS\logs\backend_uvicorn.log"
    if (Test-Path $backendLog) { Remove-Item $backendLog -Force }
    $backendCmd = "python -m uvicorn main:app --reload --host 127.0.0.1 --port $port"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $backendPath; $backendCmd 2>&1 | Tee-Object -FilePath '$backendLog'" -WindowStyle Minimized
    Log "Backend FastAPI será logado em $backendLog (porta $port)"
}

function Health-Check {
    param([int]$port)
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 5
        if ($health.status -eq "ok") { return $true } else { return $false }
    } catch { return $false }
}


function Monitor-Port8000 {
    $candidates = @(8000,8001,8080,3000)
    $level = 1
    $maxTries = 8
    $waitStep = 2
    $incidentTimeline = @()
    $success = $false
    $chosenPort = $null
    $tryPorts = $candidates
    while ($level -le 2 -and -not $success) {
        foreach ($port in $tryPorts) {
            Log "[Monitor] Testando porta $port..."
            $incidentTimeline += "Testando porta $port"
            if (Test-Port $port) {
                $proc = Get-PortProcess $port
                if ($proc) {
                    Log "Porta $port já está em uso por $($proc.ProcessName) (PID: $($proc.Id))" "WARN"
                    $incidentTimeline += "Porta $port ocupada por $($proc.ProcessName) (PID: $($proc.Id))"
                    if ($level -eq 1) {
                        if (Free-Port $port) {
                            Log "Porta $port liberada. Tentando iniciar backend..." "INFO"
                            Start-Backend $port
                            $chosenPort = $port
                        } else {
                            continue
                        }
                    } elseif ($level -eq 2) {
                        Log "Migrando para próxima porta alternativa..." "INFO"
                        continue
                    }
                } else {
                    Log "Porta $port ocupada, mas processo não identificado." "ERROR"
                    $incidentTimeline += "Porta $port ocupada, processo não identificado"
                    continue
                }
            } else {
                Log "Porta $port está livre. Iniciando backend..." "INFO"
                Start-Backend $port
                $chosenPort = $port
            }
            # Health check para a porta escolhida
            for ($i=1; $i -le $maxTries; $i++) {
                Log "Aguardando backend subir na porta $chosenPort... tentativa $i de $maxTries (espera $waitStep s)"
                Start-Sleep -Seconds $waitStep
                if (Health-Check $chosenPort) {
                    Log "Backend FastAPI está saudável na porta $chosenPort" "INFO"
                    $incidentTimeline += "Backend saudável na porta $chosenPort"
                    $success = $true
                    break
                } else {
                    Log "Backend ainda não respondeu na porta $chosenPort (tentativa $i)" "WARN"
                    $incidentTimeline += "Backend não respondeu tentativa $i na porta $chosenPort"
                }
            }
            if ($success) { break }
            else {
                Log "Backend não respondeu após $($maxTries*$waitStep) segundos na porta $chosenPort. Diagnóstico automático..." "ERROR"
                $incidentTimeline += "Backend não respondeu após $($maxTries*$waitStep) segundos na porta $chosenPort"
                if ($level -eq 1) {
                    Log "Tentando reiniciar backend na mesma porta (Nível 1)..." "WARN"
                    Start-Backend $chosenPort
                    # repete health check
                } elseif ($level -eq 2) {
                    Log "Nível 2: Tentando próxima porta alternativa..." "WARN"
                    # repete laço para próxima porta
                }
            }
        }
        if (-not $success -and $level -eq 1) {
            Log "Nível 1 falhou. Escalando para Nível 2 (portas alternativas)..." "WARN"
            $level = 2
            $tryPorts = $candidates | Where-Object { $_ -ne $chosenPort }
        } elseif (-not $success -and $level -eq 2) {
            Log "Nível 2 falhou. Escalando para Nível 3 (diagnóstico avançado)..." "ERROR"
            foreach ($port in $candidates) { Check-Firewall $port }
            Log "Se persistir, tente reiniciar a máquina ou reconfigurar firewall/rede." "FATAL"
            throw "Falha crítica: Nenhuma porta disponível para backend. Veja logs para diagnóstico."
        }
    }
    Log "[Relatório de incidente] Timeline: $($incidentTimeline -join ' | ')" "INFO"
    if ($chosenPort -ne $null -and $chosenPort -ne 8000) {
        Log "ATENÇÃO: Backend foi iniciado em porta alternativa $chosenPort. Atualize configurações do frontend/API se necessário." "WARN"
    }
}

Try-Start {

# Execução protegida do backend
Try-Start {
    Monitor-Port8000
} "Inicialização inteligente do backend FastAPI"
    Write-NexusLog "Executando npm install automaticamente para corrigir dependências do frontend..." "INFO"
    Write-NexusLog "Frontend Vite/React está saudável (HTTP 200)"
    Write-NexusLog "Falha no health check do frontend: $_" "ERROR"

# 4. Iniciar frontend Vite/React (NEXUS)
Try-Start {
    $frontendPath = "C:\Users\Charles\Desktop\NEXUS\frontend"
    Validate-File (Join-Path $frontendPath "package.json") "Frontend package.json"
    $frontendCmd = "npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $frontendPath; $frontendCmd" -WindowStyle Minimized
    Start-Sleep -Seconds 2
    # Health check
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 5 -UseBasicParsing
        if ($resp.StatusCode -ne 200) { throw "Frontend não respondeu HTTP 200" }
        Log "Frontend Vite/React está saudável (HTTP 200)"
    } catch {
        Log "Falha no health check do frontend: $_" "ERROR"
        throw $_
    }
} "Inicialização do frontend Vite/React" {
    # Auto-correção: tentar rodar npm install
    Log "Executando npm install automaticamente para corrigir dependências do frontend..." "INFO"
    $frontendPath = "C:\Users\Charles\Desktop\NEXUS\frontend"
    Push-Location $frontendPath
    npm install
    Pop-Location
}

# Linhas removidas para evitar erro de encoding/sintaxe
# Linha removida para evitar erro de sintaxe/encoding
