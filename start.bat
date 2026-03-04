@echo off
REM NEXUS STARTUP SCRIPT DEFINITIVO

echo 🔍 Validando ambiente...

if not exist .env if not exist .env.local (
    echo ❌ Arquivo .env ou .env.local não encontrado!
    echo 📄 Copie .env.example para .env.local
    exit /b 1
)

echo 📦 Instalando dependências backend...
pip install -r backend\requirements.txt

echo 📦 Instalando dependências frontend...
cd frontend && npm install && cd ..

echo 🏗️  Compilando frontend...
cd frontend && npm run build && cd ..

echo 🚀 Iniciando backend...
start /B python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

timeout /t 3

echo ❤️  Testando backend...
curl -f http://127.0.0.1:8000/health
if errorlevel 1 (
    echo ❌ Backend falhou!
    exit /b 1
)

echo ✅ Backend OK em http://127.0.0.1:8000

echo 🚀 Iniciando frontend...
cd frontend && npm run dev
