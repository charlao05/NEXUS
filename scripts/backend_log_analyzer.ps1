# backend_log_analyzer.ps1
# Sistema inteligente de análise automática de logs de backend com diagnóstico e correção proativa
# Uso: powershell -ExecutionPolicy Bypass -File scripts/backend_log_analyzer.ps1

param(
    [string]$LogPath = "C:\Users\Charles\Desktop\NEXUS\logs\backend_uvicorn.log",
    [string]$BackupDir = "C:\Users\Charles\Desktop\NEXUS\logs\log_backups",
    [int]$TailLines = 200
)

function Log {
    param([string]$msg, [string]$level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$timestamp [$level] $msg"
    Write-Host $line
    Add-Content -Path "C:\Users\Charles\Desktop\NEXUS\logs\log_analyzer.log" -Value $line
}

function Backup-Log {
    param([string]$logFile)
    if (!(Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }
    $backupFile = Join-Path $BackupDir ("backend_uvicorn_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
    Copy-Item $logFile $backupFile -Force
    Log "Backup do log criado em $backupFile" "INFO"
    return $backupFile
}

function Parse-Log {
    param([string[]]$lines)
    $errors = @()
    $warnings = @()
    $criticals = @()
    $traces = @()
    $currentTrace = @()
    $inTrace = $false
    foreach ($line in $lines) {
        if ($line -match "CRITICAL|FATAL|Traceback") {
            $criticals += $line
            $inTrace = $true
            $currentTrace = @($line)
        } elseif ($line -match "ERROR|Exception") {
            $errors += $line
            $inTrace = $true
            $currentTrace = @($line)
        } elseif ($line -match "WARN") {
            $warnings += $line
        } elseif ($inTrace -and ($line -match "^\s+" -or $line -match "File|line|in")) {
            $currentTrace += $line
        } else {
            if ($inTrace) {
                $traces += ,@($currentTrace)
                $inTrace = $false
                $currentTrace = @()
            }
        }
    }
    return @{ "criticals" = $criticals; "errors" = $errors; "warnings" = $warnings; "traces" = $traces }
}

function Diagnose-Log {
    param($parsed)
    $diagnosis = @()
    $severity = "INFO"
    $rootCause = ""
    $category = ""
    $location = ""
    $stack = ""
    $impact = ""
    $problem = ""
    $solutions = @()
    $alternatives = @()
    $actions = @()
    $prevention = @()
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    # 1. CRITICAL
    if ($parsed.criticals.Count -gt 0) {
        $severity = "P0 - CRÍTICO"
        $problem = $parsed.criticals[0]
        $category = "CRITICAL"
        $impact = "Serviço indisponível"
        $rootCause = $parsed.criticals[0]
        $solutions += "Reiniciar backend imediatamente"
        $alternatives += "Tentar porta alternativa"
        $alternatives += "Verificar dependências e permissões"
        $prevention += "Adicionar monitoramento de disponibilidade"
    } elseif ($parsed.errors.Count -gt 0) {
        $severity = "P1 - ALTO"
        $problem = $parsed.errors[0]
        $category = "ERROR"
        $impact = "Funcionalidade principal degradada"
        $rootCause = $parsed.errors[0]
        $solutions += "Corrigir erro de aplicação: $($parsed.errors[0])"
        $alternatives += "Reinstalar dependências"
        $alternatives += "Reiniciar serviço"
        $prevention += "Adicionar testes automatizados para este fluxo"
    } elseif ($parsed.warnings.Count -gt 0) {
        $severity = "P2 - MÉDIO"
        $problem = $parsed.warnings[0]
        $category = "WARNING"
        $impact = "Funcionalidade secundária afetada"
        $rootCause = $parsed.warnings[0]
        $solutions += "Monitorar e analisar warning: $($parsed.warnings[0])"
        $alternatives += "Ajustar configuração"
        $prevention += "Revisar logs periodicamente"
    } else {
        $severity = "P3 - BAIXO"
        $problem = "Nenhum erro crítico detectado"
        $category = "INFO"
        $impact = "Sem impacto imediato"
        $solutions += "Nenhuma ação necessária"
    }
    return @{ 
        "Resumo" = $problem; "Severidade" = $severity; "Impacto" = $impact; "Categoria" = $category;
        "CausaRaiz" = $rootCause; "Solucoes" = $solutions; "Alternativas" = $alternatives; "Prevenção" = $prevention;
        "Timestamp" = $now; "Traces" = $parsed.traces
    }
}

function Report-LogAnalysis {
    param($diagnosis)
    $report = @()
    $report += "## Resumo Executivo"
    $report += "- Problema detectado: $($diagnosis.Resumo)"
    $report += "- Severidade: $($diagnosis.Severidade)"
    $report += "- Impacto: $($diagnosis.Impacto)"
    $report += "- Status: analisado"
    $report += ""
    $report += "## Diagnóstico Técnico"
    $report += "- Tipo de erro: $($diagnosis.Categoria)"
    $report += "- Causa raiz: $($diagnosis.CausaRaiz)"
    $report += "- Stack trace:"
    foreach ($trace in $diagnosis.Traces) {
        $report += ("    " + ($trace -join "`n    "))
    }
    $report += ""
    $report += "## Soluções Propostas"
    $report += "### Solução Primária"
    $report += "- $($diagnosis.Solucoes[0])"
    $report += "### Alternativas"
    foreach ($alt in $diagnosis.Alternativas) { $report += "- $alt" }
    $report += ""
    $report += "## Prevenção Futura"
    foreach ($prev in $diagnosis.Prevenção) { $report += "- $prev" }
    $report += ""
    $report += "---"
    $report += "Análise gerada em $($diagnosis.Timestamp)"
    $reportStr = $report -join "`n"
    $reportFile = "C:\Users\Charles\Desktop\NEXUS\logs\backend_log_report.md"
    Set-Content -Path $reportFile -Value $reportStr -Encoding UTF8
    Log "Relatório de diagnóstico salvo em $reportFile" "INFO"
    Write-Host $reportStr
}

# Execução principal
if (!(Test-Path $LogPath)) { Log "Arquivo de log não encontrado: $LogPath" "ERROR"; exit 1 }
$backup = Backup-Log $LogPath
$lines = Get-Content $LogPath -Tail $TailLines
$parsed = Parse-Log $lines
$diagnosis = Diagnose-Log $parsed
Report-LogAnalysis $diagnosis

# Correção automatizada (exemplo: reiniciar backend se crítico)
if ($diagnosis.Severidade -like "P0*") {
    Log "Correção automática: Reiniciando backend..." "WARN"
    # Aqui pode-se chamar o script de inicialização inteligente
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "& 'C:\Users\Charles\Desktop\NEXUS\START_NEXUS_FULL.ps1'" -WindowStyle Minimized
    Log "Backend reiniciado automaticamente." "INFO"
}
