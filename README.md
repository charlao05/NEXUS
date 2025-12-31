# 🚀 NEXUS - Sistema de IA para Diagnóstico de Problemas

![NEXUS](https://img.shields.io/badge/NEXUS-AI%20Powered-blue)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![Version](https://img.shields.io/badge/Version-1.0.0-blue)

## 📌 Descrição

**NEXUS** é uma plataforma inteligente de diagnóstico empresarial que utiliza **OpenAI GPT** para analisar desafios de negócio e fornecer soluções estruturadas baseadas em IA.

- ✅ Análise profunda de desafios empresariais
- ✅ Identificação automática de causas raiz
- ✅ Recomendação de soluções priorizadas
- ✅ Próximos passos actionáveis
- ✅ Dashboard intuitivo
- ✅ Autenticação segura com JWT

## 🎯 Características

- 📊 **Diagnosis** - Análise com IA
- 💡 **Solutions** - Soluções recomendadas
- 🤖 **AI Automation** - Controle de automações
- 📈 **Results** - Dashboard de métricas
- 📚 **Actions** - Biblioteca de ações

## �� Tech Stack

**Backend:** FastAPI, SQLAlchemy, OpenAI API, SQLite, Python 3.11+
**Frontend:** React 18+, Vite, Axios, TypeScript

## 🚀 Setup Rápido

### Backend
\\\ash
cd NEXUS/backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-proj-[YOUR_KEY]" > .env
echo "OPENAI_MODEL=gpt-3.5-turbo" >> .env
uvicorn app.main:app --reload --port 8000
\\\

### Frontend
\\\ash
cd NEXUS/frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
\\\

**Backend:** http://localhost:8000
**Frontend:** http://localhost:5173

## 💻 Como Usar

1. Cadastre-se/Faça login
2. Vá para aba "Diagnóstico"
3. Descreva seu desafio
4. Clique "Analisar Diagnóstico"
5. Receba análise com causas-raiz e soluções

## 📊 API Endpoints

\\\
POST   /api/auth/register     # Criar conta
POST   /api/auth/login        # Fazer login
POST   /api/diagnosis/analyze # Analisar desafio
GET    /api/diagnosis/health  # Health check
\\\

## 🔐 Variáveis de Ambiente

**Backend (.env):**
\\\
OPENAI_API_KEY=sk-proj-[YOUR_KEY]
OPENAI_MODEL=gpt-3.5-turbo
DATABASE_URL=sqlite:///./nexus.db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
\\\

**Frontend (.env.local):**
\\\
VITE_API_URL=http://localhost:8000
\\\

## 📈 Deployment

**Frontend (GitHub Pages):**
\\\ash
npm run build
\\\

**Backend:** Render, Railway, Heroku, AWS EC2

## 🧪 Testes

\\\ash
curl http://localhost:8000/api/diagnosis/health
npm run build && npm run preview
\\\

## 🐛 Troubleshooting

**"No module named 'openai'"**
\\\ash
pip install openai python-dotenv
\\\

**"Chave OpenAI não configurada"**
Verifique .env: OPENAI_API_KEY=sk-proj-... (sem espaços!)

**Frontend não conecta**
Verifique CORS no backend e URL em .env.local

## 📝 License

MIT License

## 👨‍💼 Autor

Charles (charlao05) - GitHub: @charlao05

## 🗺️ Roadmap

**v1.1.0 (Q1 2026):** Histórico, PDF export, Analytics, Stripe
**v2.0.0 (Q2 2026):** Mobile, Mais modelos IA, Colaboração, API pública

Feito com ❤️ por Charles
