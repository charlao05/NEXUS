"""
Configurações Centralizadas do NEXUS
====================================
Autor: Charles Rodrigues
Data: 25/01/2026
"""

import os
from typing import Optional
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class OpenAIConfig:
    """Configuração para OpenAI API"""
    api_key: str
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    model: str = "gpt-4o-mini"
    timeout: int = 30
    max_retries: int = 3
    base_url: Optional[str] = None
    
    def validate(self) -> None:
        """Valida configuração"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY não está configurada")
        if self.api_key == "sk-proj-test-development-mode":
            raise ValueError("OPENAI_API_KEY é um placeholder - configure com chave real")
        if len(self.api_key) < 20:
            raise ValueError("OPENAI_API_KEY parece inválida (muito curta)")


@dataclass
class RateLimitConfig:
    """Configuração de rate limiting"""
    rpm: int = 60  # Requests per minute
    tpm: int = 90000  # Tokens per minute
    request_timeout: int = 30
    
    def validate(self) -> None:
        """Valida configuração"""
        if self.rpm <= 0 or self.tpm <= 0:
            raise ValueError("Rate limits devem ser maiores que 0")


@dataclass
class LoggingConfig:
    """Configuração de logging"""
    level: str = "INFO"
    format: str = "json"  # json ou text
    file: Optional[str] = None
    sentry_dsn: Optional[str] = None
    
    def validate(self) -> None:
        """Valida configuração"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level not in valid_levels:
            raise ValueError(f"Log level deve ser um de {valid_levels}")


@dataclass
class AppConfig:
    """Configuração completa da aplicação"""
    environment: str = "development"
    debug: bool = False
    openai: Optional[OpenAIConfig] = None
    rate_limit: Optional[RateLimitConfig] = None
    logging: Optional[LoggingConfig] = None
    
    def __post_init__(self) -> None:
        """Inicializa configs se não foram fornecidas"""
        if self.openai is None:
            self.openai = OpenAIConfig(api_key=os.getenv("OPENAI_API_KEY", ""))
        if self.rate_limit is None:
            self.rate_limit = RateLimitConfig(
                rpm=int(os.getenv("RATE_LIMIT_RPM", "60")),
                tpm=int(os.getenv("RATE_LIMIT_TPM", "90000"))
            )
        if self.logging is None:
            self.logging = LoggingConfig(
                level=os.getenv("LOG_LEVEL", "INFO"),
                sentry_dsn=os.getenv("SENTRY_DSN")
            )
    
    def validate_all(self) -> None:
        """Valida todas as configs"""
        if self.openai is not None:
            self.openai.validate()
        if self.rate_limit is not None:
            self.rate_limit.validate()
        if self.logging is not None:
            self.logging.validate()


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Retorna config singleton"""
    config = AppConfig(
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=os.getenv("DEBUG", "False").lower() == "true",
        openai=OpenAIConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            org_id=os.getenv("OPENAI_ORG_ID"),
            project_id=os.getenv("OPENAI_PROJECT_ID"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            timeout=int(os.getenv("OPENAI_TIMEOUT", "30")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3"))
        )
    )
    config.validate_all()
    return config
