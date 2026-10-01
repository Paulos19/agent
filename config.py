import os
from pathlib import Path
from typing import List, Set, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Provider (Google Gemini, 9Router, LiteLLM, OpenAI)
    LLM_API_KEY: str = Field(default="", validation_alias=AliasChoices("LLM_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"))
    LLM_MODEL: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("LLM_MODEL", "GEMINI_MODEL", "OPENAI_MODEL"))
    LLM_BASE_URL: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai/", validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL", "GEMINI_BASE_URL"))

    # Segurança & Acesso
    ALLOWED_USERS: str = ""
    WORKER_SECRET: str = Field(default="devops_secret_token_123", validation_alias=AliasChoices("WORKER_SECRET", "NODE_TOKEN"))
    VPS_WS_URL: Optional[str] = Field(default="wss://agent.phdev.top/ws/worker", validation_alias=AliasChoices("VPS_WS_URL", "NODE_WS_URL"))

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

    # DevOps: SSH na VPS Host
    VPS_SSH_HOST: Optional[str] = None
    VPS_SSH_PORT: int = 22
    VPS_SSH_USER: str = "root"
    VPS_SSH_PASS: Optional[str] = None
    VPS_SSH_KEY: Optional[str] = None

    # DevOps: Easypanel API & Deploy
    EASYPANEL_URL: str = "https://khdya3.easypanel.host"
    EASYPANEL_DOMAIN: str = "khdya3.easypanel.host"
    EASYPANEL_API_KEY: Optional[str] = None
    EASYPANEL_EMAIL: Optional[str] = None
    EASYPANEL_PASSWORD: Optional[str] = None
    EASYPANEL_DEPLOY_WEBHOOK: Optional[str] = None
    EASYPANEL_DEPLOY_WEBHOOKS: str = "{}"

    # DevOps: GitHub Automation
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_USERNAME: str = "Paulos19"

    # UI/UX & Design Intelligence: Mobbin
    MOBBIN_API_KEY: Optional[str] = Field(default=None, validation_alias=AliasChoices("MOBBIN_API_KEY", "MOBBIN_TOKEN"))

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

    @property
    def GEMINI_MODEL(self) -> str:
        return self.LLM_MODEL

    @property
    def GEMINI_API_KEY(self) -> str:
        return self.LLM_API_KEY

settings = Settings()
