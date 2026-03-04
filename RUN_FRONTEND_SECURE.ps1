# ============================================
# EXECUÇÃO SEGURA DO FRONTEND NEXUS
# ============================================
# Script que carrega variáveis de ambiente e executa o frontend
# SEM EXPOR SECRETS NO TERMINAL OU HISTÓRICO

param(
    [string]$Port = "5175",
    [string]$HostAddress = "127.0.0.1"
)

# Cores para output
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"
$Cyan = "Cyan"

Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host "🔐 NEXUS FRONTEND - EXECUÇÃO SEGURA" -ForegroundColor $Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host ""

# ============================================
# 1. VALIDAR AMBIENTE
# ============================================

Write-Host "📋 Passo 1: Validando ambiente..." -ForegroundColor $Cyan

# Verificar se estamos na pasta frontend
if (-not (Test-Path ".\package.json")) {
    Write-Host "❌ ERRO: Execute este script da raiz do NEXUS ou do frontend" -ForegroundColor $Red
    exit 1
}

if (-not (Test-Path ".\.env.local") -and -not (Test-Path "..\NEXUS\.env.local")) {
    Write-Host "⚠️  AVISO: Arquivo .env.local não encontrado" -ForegroundColor $Yellow
    Write-Host "   Verifique se está na pasta correta ou se .env.local existe" -ForegroundColor $Yellow
}

Write-Host "✅ Estrutura validada" -ForegroundColor $Green
Write-Host ""

# ============================================
# 2. CARREGAR VARIÁVEIS DE AMBIENTE
# ============================================

Write-Host "📋 Passo 2: Carregando variáveis de ambiente..." -ForegroundColor $Cyan

# Procurar por .env.local na pasta raiz ou uma pasta acima
$envFile = if (Test-Path ".\.env.local") { ".\.env.local" } 
           elseif (Test-Path "..\\.env.local") { "..\\.env.local" }
           else { $null }

if ($envFile) {
    $envContent = Get-Content $envFile -ErrorAction SilentlyContinue | Where-Object { 
        $_ -and -not $_.StartsWith("#") -and $_ -match "=" 
    }
    
    $secretsLoaded = 0
    foreach ($line in $envContent) {
        if ($line -match "^([^=]+)=(.*)$") {
            $varName = $matches[1].Trim()
            $varValue = $matches[2].Trim()
            
            # Carregar variáveis públicas (NEXT_PUBLIC_*)
            if ($varName -match "^NEXT_PUBLIC_") {
                Set-Item -Path "env:$varName" -Value $varValue -ErrorAction SilentlyContinue
                $secretsLoaded++
            }
        }
    }
    
    Write-Host "✅ Variáveis carregadas ($secretsLoaded variáveis públicas)" -ForegroundColor $Green
} else {
    Write-Host "⚠️  Nenhum arquivo .env.local encontrado (usar defaults)" -ForegroundColor $Yellow
}

Write-Host ""

# ============================================
# 3. VERIFICAR DEPENDÊNCIAS
# ============================================

Write-Host "📋 Passo 3: Verificando dependências..." -ForegroundColor $Cyan

if (-not (Test-Path ".\node_modules")) {
    Write-Host "⚠️  node_modules não encontrado" -ForegroundColor $Yellow
    Write-Host "   Instalando dependências com npm..." -ForegroundColor $Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Erro ao instalar dependências" -ForegroundColor $Red
        exit 1
    }
}

Write-Host "✅ Dependências verificadas" -ForegroundColor $Green
Write-Host ""

# ============================================
# 4. INICIAR SERVIDOR FRONTEND
# ============================================

Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host "🚀 INICIANDO SERVIDOR FRONTEND" -ForegroundColor $Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host ""
Write-Host "📍 Endereço: http://$HostAddress`:$Port" -ForegroundColor $Cyan
Write-Host "📍 Backend (proxy): http://$HostAddress`:$Port/api" -ForegroundColor $Cyan
Write-Host ""
Write-Host "⏹️  Pressione CTRL+C para parar o servidor" -ForegroundColor $Yellow
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host ""

# Executar Vite com variáveis de ambiente já carregadas
npm run dev -- --host $HostAddress --port $Port

# Se chegou aqui, servidor foi interrompido
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host "⛔ Servidor interrompido" -ForegroundColor $Yellow
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
