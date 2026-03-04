# ============================================
# EXECUÇÃO SEGURA DO BACKEND NEXUS
# ============================================
# Script que carrega variáveis de ambiente e executa o servidor
# SEM EXPOR SECRETS NO TERMINAL OU HISTÓRICO

param(
    [switch]$NoReload = $false,
    [string]$Port = "8000",
    [string]$HostAddress = "127.0.0.1"
)

# Cores para output
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"
$Cyan = "Cyan"

Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host "🔐 NEXUS BACKEND - EXECUÇÃO SEGURA" -ForegroundColor $Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host ""

# ============================================
# 1. VALIDAR AMBIENTE
# ============================================

Write-Host "📋 Passo 1: Validando ambiente..." -ForegroundColor $Cyan

# Verificar se estamos na pasta NEXUS
if (-not (Test-Path ".\backend\main.py")) {
    Write-Host "❌ ERRO: Execute este script da raiz do NEXUS" -ForegroundColor $Red
    exit 1
}

# Verificar se .env.local existe
if (-not (Test-Path ".\.env.local")) {
    Write-Host "❌ ERRO: Arquivo .env.local não encontrado" -ForegroundColor $Red
    Write-Host "   Crie o arquivo conforme o guia CONFIGURACAO_SEGURA.md" -ForegroundColor $Yellow
    exit 1
}

Write-Host "✅ Estrutura validada" -ForegroundColor $Green

# ============================================
# 2. CARREGAR VARIÁVEIS DE AMBIENTE SEGURAMENTE
# ============================================

Write-Host "📋 Passo 2: Carregando variáveis de ambiente..." -ForegroundColor $Cyan

# Limpar variáveis anteriores
Get-ChildItem env:STRIPE_* -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue
Get-ChildItem env:CLERK_* -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue
Get-ChildItem env:OPENAI_* -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue
Get-ChildItem env:JWT_* -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue

# Carregar .env.local
$envContent = Get-Content ".\.env.local" -ErrorAction SilentlyContinue | Where-Object { 
    $_ -and -not $_.StartsWith("#") -and $_ -match "=" 
}

$secretsLoaded = 0
$secretsCount = 0

foreach ($line in $envContent) {
    if ($line -match "^([^=]+)=(.*)$") {
        $varName = $matches[1].Trim()
        $varValue = $matches[2].Trim()
        
        # Contar apenas secrets (não strings vazias ou placeholders)
        if ($varValue -and $varValue -notmatch "^COLE_|^OPCIONAL_") {
            $secretsCount++
        }
        
        # Carregar a variável de ambiente
        Set-Item -Path "env:$varName" -Value $varValue -ErrorAction SilentlyContinue
    }
}

Write-Host "✅ Variáveis carregadas ($secretsCount valores encontrados)" -ForegroundColor $Green
Write-Host ""

# ============================================
# 3. VALIDAR SECRETS CRÍTICAS
# ============================================

Write-Host "📋 Passo 3: Validando secrets críticas..." -ForegroundColor $Cyan

$requiredVars = @("STRIPE_SECRET_KEY", "CLERK_SECRET_KEY", "JWT_SECRET")
$missing = @()

foreach ($var in $requiredVars) {
    $value = Get-Item -Path "env:$var" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Value
    
    if ($value -and $value -notmatch "^(COLE_|sk_test_COLE|OPCIONAL)" ) {
        Write-Host "  ✅ $var (configurada)" -ForegroundColor $Green
    } else {
        Write-Host "  ❌ $var (faltando ou placeholder)" -ForegroundColor $Red
        $missing += $var
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️  AVISO: Variáveis não configuradas: $($missing -join ', ')" -ForegroundColor $Yellow
    Write-Host "   Edite .env.local e cole as chaves secretas reais" -ForegroundColor $Yellow
    Write-Host ""
    $continue = Read-Host "Continuar mesmo assim? (s/n)"
    if ($continue -ne "s") {
        exit 1
    }
}

Write-Host ""

# ============================================
# 4. ATIVAR VENV
# ============================================

Write-Host "📋 Passo 4: Ativando ambiente virtual..." -ForegroundColor $Cyan

$venvPath = ".\.venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvPath)) {
    Write-Host "❌ ERRO: Ambiente virtual não encontrado" -ForegroundColor $Red
    Write-Host "   Execute: python -m venv .venv" -ForegroundColor $Yellow
    exit 1
}

& $venvPath
Write-Host "✅ Venv ativado" -ForegroundColor $Green
Write-Host ""

# ============================================
# 5. INICIAR SERVIDOR
# ============================================

Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host "🚀 INICIANDO SERVIDOR NEXUS" -ForegroundColor $Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host ""
Write-Host "📍 Endereço: http://$HostAddress`:$Port" -ForegroundColor $Cyan
Write-Host "📚 Documentação: http://$HostAddress`:$Port/docs" -ForegroundColor $Cyan
Write-Host "🧪 Health Check: http://$HostAddress`:$Port/health" -ForegroundColor $Cyan
Write-Host ""
Write-Host "⏹️  Pressione CTRL+C para parar o servidor" -ForegroundColor $Yellow
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host ""

# Construir comando uvicorn
$reloadFlag = if ($NoReload) { "" } else { "--reload" }

# Executar com variáveis de ambiente já carregadas
python -m uvicorn backend.main:app $reloadFlag --host $HostAddress --port $Port

# Se chegou aqui, servidor foi interrompido
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host "⛔ Servidor interrompido" -ForegroundColor $Yellow
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
