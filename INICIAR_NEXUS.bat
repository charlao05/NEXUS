@echo off
chcp 65001 >nul 2>&1
title NEXUS - Iniciando...
color 0A

echo.
echo ========================================
echo    NEXUS - Iniciando Servicos
echo ========================================
echo.

set "NEXUS_DIR=C:\Users\Charles\Desktop\NEXUS"
set "VENV=%NEXUS_DIR%\.venv\Scripts\Activate.ps1"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

REM ── Verificar Backend ──────────────────────────────────────────────
echo [..] Verificando Backend (porta %BACKEND_PORT%)...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
    echo [OK] Backend ja esta rodando
) else (
    echo [..] Iniciando Backend...
    start "NEXUS-Backend" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "cd '%NEXUS_DIR%'; & '%VENV%'; python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%"

    REM Aguardar backend ficar pronto (max 30s)
    echo [..] Aguardando backend ficar pronto...
    timeout /t 3 /nobreak >nul
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }"
    if not %errorlevel%==0 (
        timeout /t 4 /nobreak >nul
        powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 3 -ErrorAction Stop; exit 0 } catch { exit 1 }"
        if not %errorlevel%==0 (
            timeout /t 5 /nobreak >nul
        )
    )
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 3 -ErrorAction Stop; Write-Host '[OK] Backend pronto'; exit 0 } catch { Write-Host '[!!] Backend pode nao estar pronto - verifique manualmente'; exit 1 }"
)

echo.

REM ── Verificar Frontend ─────────────────────────────────────────────
echo [..] Verificando Frontend (porta %FRONTEND_PORT%)...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%FRONTEND_PORT%/' -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
    echo [OK] Frontend ja esta rodando
) else (
    echo [..] Iniciando Frontend...
    start "NEXUS-Frontend" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "cd '%NEXUS_DIR%\frontend'; npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"
    timeout /t 5 /nobreak >nul
    echo [OK] Frontend iniciado
)

echo.
echo ========================================
echo    NEXUS esta pronto!
echo.
echo    Acesse: http://127.0.0.1:%FRONTEND_PORT%
echo.
echo    Backend:  http://127.0.0.1:%BACKEND_PORT%/health
echo    Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo    Diagnostico: http://127.0.0.1:%FRONTEND_PORT%/diag
echo ========================================
echo.

REM ── Verificar Login (teste automatico) ─────────────────────────────
echo [..] Testando login automaticamente...
powershell -NoProfile -Command "try { $body = '{\"email\":\"charles.rsilva05@gmail.com\",\"password\":\"Admin@123\"}'; $r = Invoke-RestMethod -Uri 'http://127.0.0.1:%BACKEND_PORT%/api/auth/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 5 -ErrorAction Stop; Write-Host '[OK] Login funcional: plan=' $r.plan 'uid=' $r.user_id } catch { Write-Host '[!!] Login falhou:' $_.Exception.Message }"
echo.

REM Abrir navegador automaticamente
timeout /t 2 /nobreak >nul
start http://127.0.0.1:%FRONTEND_PORT%

echo Pressione qualquer tecla para fechar esta janela...
pause >nul
