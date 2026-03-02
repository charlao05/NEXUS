from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Carregar .env.local primeiro (dev), depois .env (prod)
load_dotenv(".env.local", override=False)
load_dotenv(".env", override=False)

class Settings(BaseSettings):
    # Banco de Dados
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    
    # Ambiente
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def validate_all(self):
        """Valida se todas variáveis críticas existem"""
        missing: List[str] = []
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            missing.append("SECRET_KEY (mínimo 32 caracteres)")
        
        if missing:
            raise ValueError(f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing)}")

# Instanciar e validar
settings = Settings()
settings.validate_all()
