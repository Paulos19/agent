import os
from pathlib import Path
from typing import List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Segurança & Acesso
    ALLOWED_USERS: str = ""
    WORKER_SECRET: str = Field(default="devops_secret_token_123", validation_alias=AliasChoices("WORKER_SECRET", "NODE_TOKEN"))

    # Diretório de trabalho padrão
    WORKSPACE_DIR: str = "./workspace"

    # Evolution API
    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_INSTANCE_NAME: str = "assistente"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""

    # SMTP / E-mail (Suporta tanto prefixo SMTP_ quanto EMAIL_SERVER_)
    SMTP_HOST: str = Field(default="smtp.gmail.com", validation_alias=AliasChoices("SMTP_HOST", "EMAIL_SERVER_HOST"))
    SMTP_PORT: int = Field(default=465, validation_alias=AliasChoices("SMTP_PORT", "EMAIL_SERVER_PORT"))
    SMTP_USER: str = Field(default="", validation_alias=AliasChoices("SMTP_USER", "EMAIL_SERVER_USER"))
    SMTP_PASS: str = Field(default="", validation_alias=AliasChoices("SMTP_PASS", "EMAIL_SERVER_PASSWORD", "SMTP_PASSWORD"))
    SMTP_FROM: str = Field(default="", validation_alias=AliasChoices("SMTP_FROM", "EMAIL_FROM"))
    EMAIL_SERVER_SECURE: bool = Field(default=True, validation_alias=AliasChoices("EMAIL_SERVER_SECURE", "SMTP_SECURE"))

    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def allowed_users_set(self) -> Set[str]:
        """Retorna uma lista limpa dos IDs e números autorizados com normalização de 9º dígito BR."""
        if not self.ALLOWED_USERS:
            return set()
        items = [u.strip() for u in self.ALLOWED_USERS.split(",") if u.strip()]
        result = set(items)
        
        # Normalização inteligente para números do Brasil (com e sem o 9º dígito)
        for item in items:
            clean = "".join(filter(str.isdigit, item))
            if clean.startswith("55") and len(clean) == 13:
                # 55 + DDD (2) + 9 + 8 dígitos -> Gera versão sem o 9
                sem_9 = clean[:4] + clean[5:]
                result.add(sem_9)
            elif clean.startswith("55") and len(clean) == 12:
                # 55 + DDD (2) + 8 dígitos -> Gera versão com o 9
                com_9 = clean[:4] + "9" + clean[4:]
                result.add(com_9)

        return result

    @property
    def workspace_path(self) -> Path:
        """Garante que o diretório de trabalho exista e retorne o Path absoluto."""
        path = Path(self.WORKSPACE_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

settings = Settings()
