# ============================================================
#  NEXUS - Corrige SKILL.md + Upload para OpenAI
#  Salvar como: fix_and_upload_skills.ps1
#  Rodar de dentro de: C:\Users\Charles\Downloads\nexus_skills
# ============================================================

param(
    [string]$ApiKey = $env:OPENAI_API_KEY
)

if (-not $ApiKey) {
    Write-Host ""
    Write-Host "  OPENAI_API_KEY nao encontrada no ambiente." -ForegroundColor Yellow
    Write-Host "  Cole sua chave abaixo (comeca com sk-proj-...):" -ForegroundColor Yellow
    Write-Host ""
    $ApiKey = Read-Host "  API Key"
}

if (-not $ApiKey -or $ApiKey.Length -lt 20) {
    Write-Host "Chave invalida. Abortando." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  NEXUS - Fix SKILL.md + Upload v3   " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Add-Type -AssemblyName System.IO.Compression.FileSystem

$pasta        = $PSScriptRoot
if (-not $pasta) { $pasta = Get-Location }
$tempBase     = Join-Path $pasta "_temp_skills"
$fixedBase    = Join-Path $pasta "_fixed_zips"
$resultLog    = Join-Path $pasta "skill_ids.txt"

# Limpar pastas temporarias anteriores
if (Test-Path $tempBase)  { Remove-Item $tempBase  -Recurse -Force }
if (Test-Path $fixedBase) { Remove-Item $fixedBase -Recurse -Force }
New-Item -ItemType Directory -Path $tempBase  | Out-Null
New-Item -ItemType Directory -Path $fixedBase | Out-Null

# Mapeamento: nome do zip -> nome correto da skill (kebab-case)
$skillMap = @{
    "verificar_limite_plano"  = "verificar-limite-plano"
    "verificar_assinatura"    = "verificar-assinatura"
    "resolver_agente"         = "resolver-agente"
    "consultar_clientes"      = "consultar-clientes"
    "consultar_agendamentos"  = "consultar-agendamentos"
    "consultar_financeiro"    = "consultar-financeiro"
    "consultar_cobrancas"     = "consultar-cobrancas"
    "consultar_notas_fiscais" = "consultar-notas-fiscais"
    "consultar_fornecedores"  = "consultar-fornecedores"
    "registrar_log"           = "registrar-log"
}

$enviadas = 0
$erros    = 0
$logLines = @()

foreach ($entry in $skillMap.GetEnumerator()) {
    $skillKey  = $entry.Key    # ex: consultar_clientes
    $skillName = $entry.Value  # ex: consultar-clientes
    $zipPath   = Join-Path $pasta "nexus_skill_${skillKey}.zip"

    Write-Host "─────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host "Skill: $skillName" -ForegroundColor White

    if (-not (Test-Path $zipPath)) {
        Write-Host "   ZIP nao encontrado: $zipPath" -ForegroundColor Yellow
        $erros++
        continue
    }

    # 1. Extrair zip original
    $extractDir = Join-Path $tempBase $skillKey
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $extractDir)

    # 2. Localizar SKILL.md (em qualquer subpasta)
    $skillMdFiles = Get-ChildItem -Path $extractDir -Recurse -Filter "SKILL.md"
    if ($skillMdFiles.Count -eq 0) {
        Write-Host "   SKILL.md nao encontrado dentro do ZIP." -ForegroundColor Red
        $erros++
        continue
    }
    $skillMdPath = $skillMdFiles[0].FullName

    # 3. Ler e corrigir frontmatter
    $content = Get-Content $skillMdPath -Raw -Encoding UTF8

    # Substitui o valor do campo 'name' no frontmatter YAML pelo nome kebab-case correto
    $corrected = $content -replace '(?m)^(name:\s*)(.+)$', "name: $skillName"

    # Gravar de volta UTF-8 sem BOM
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($skillMdPath, $corrected, $utf8NoBom)

    Write-Host "   SKILL.md corrigido -> name: $skillName" -ForegroundColor Green

    # 4. Reempacotar em novo ZIP
    $newZipPath = Join-Path $fixedBase "nexus_skill_${skillKey}_fixed.zip"
    if (Test-Path $newZipPath) { Remove-Item $newZipPath -Force }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($extractDir, $newZipPath)

    Write-Host "   ZIP recriado: nexus_skill_${skillKey}_fixed.zip" -ForegroundColor DarkCyan

    # 5. Upload via curl.exe
    Write-Host "   Enviando para OpenAI..." -NoNewline

    $curlOutput = & curl.exe -s -X POST "https://api.openai.com/v1/skills" `
        -H "Authorization: Bearer $ApiKey" `
        -F "files=@${newZipPath};type=application/zip"

    try {
        $json = $curlOutput | ConvertFrom-Json
    } catch {
        Write-Host " ERRO - resposta invalida: $curlOutput" -ForegroundColor Red
        $erros++
        continue
    }

    if ($json.id) {
        Write-Host " OK - ID: $($json.id)" -ForegroundColor Green
        $enviadas++
        $logLines += "$skillName = $($json.id)"
    }
    elseif ($json.error) {
        Write-Host " ERRO: $($json.error.message)" -ForegroundColor Red
        $erros++
    }
    else {
        Write-Host " ERRO inesperado: $curlOutput" -ForegroundColor Red
        $erros++
    }
}

# 6. Salvar IDs em arquivo
if ($logLines.Count -gt 0) {
    $header = @"
# NEXUS - IDs das Skills OpenAI
# Gerado em: $(Get-Date -Format 'dd/MM/yyyy HH:mm')
# Cole estes IDs no .env do backend NEXUS como:
#   SKILL_ID_CONSULTAR_CLIENTES=skill_xxx
#   SKILL_ID_CONSULTAR_AGENDAMENTOS=skill_xxx
#   etc.

"@
    $header + ($logLines -join "`n") | Out-File $resultLog -Encoding UTF8
    Write-Host ""
    Write-Host "IDs salvos em: $resultLog" -ForegroundColor Cyan
}

# 7. Limpar temporarios
Remove-Item $tempBase -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
if ($erros -eq 0) {
    Write-Host "  Resultado: $enviadas enviadas | 0 erros" -ForegroundColor Green
} else {
    Write-Host "  Resultado: $enviadas enviadas | $erros erros" -ForegroundColor Yellow
}
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Verifique em: https://platform.openai.com/storage/skills" -ForegroundColor DarkGray
Write-Host ""
