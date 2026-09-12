"""
config/settings.py
Configuração central do projeto. Lê variáveis de ambiente (via .env) com
valores padrão sensatos, para que a aplicação funcione "out of the box"
mesmo sem nenhuma configuração adicional (usa SQLite local por padrão).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega variáveis do arquivo .env, se existir
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Configurações da aplicação, centralizadas em um único lugar."""

    # --- Diretórios ---
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    CACHE_DIR: Path = DATA_DIR / "cache"
    LOG_DIR: Path = BASE_DIR / "logs"

    # --- Banco de dados ---
    # Por padrão usa SQLite local (zero configuração). Para usar Postgres,
    # defina DATABASE_URL no .env, ex:
    # postgresql+psycopg2://user:password@localhost:5432/realestate_db
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'realestate.db').as_posix()}"
    )

    # --- Scraping ---
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    )
    SCRAPE_TIMEOUT: int = int(os.getenv("SCRAPE_TIMEOUT", "15"))
    SCRAPE_MAX_RETRIES: int = int(os.getenv("SCRAPE_MAX_RETRIES", "2"))

    # Fonte de dados padrão: "demo" (sintética, sempre funciona) ou "live"
    # (tenta raspar o site real; pode falhar por bloqueio/mudança de layout,
    # nesse caso o pipeline cai automaticamente para dados demo).
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "demo")

    # --- API keys (opcional) ---
    GOOGLE_PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")

    # --- Streamlit ---
    STREAMLIT_SERVER_PORT: int = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
    STREAMLIT_THEME: str = os.getenv("STREAMLIT_THEME", "dark")

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(LOG_DIR / "app.log"))

    # --- Cache (opcional, Redis). Sem Redis o app usa cache em memória. ---
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    USE_REDIS: bool = _as_bool(os.getenv("USE_REDIS"), default=bool(os.getenv("REDIS_URL")))

    # --- API (segurança) ---
    # Origens permitidas para CORS na API REST. Por padrão libera tudo ("*"),
    # o que é conveniente para desenvolvimento local, mas em produção defina
    # CORS_ORIGINS como uma lista separada por vírgula, ex:
    # CORS_ORIGINS=https://meuapp.com,https://admin.meuapp.com
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ] or ["*"]

    # Chave opcional para proteger endpoints que disparam trabalho pesado
    # (ex: POST /pipeline/run, que roda scraping + ML de forma síncrona).
    # Se definida, a API passa a exigir o header `X-API-Key` com esse valor
    # nesses endpoints. Deixe em branco para manter o comportamento aberto
    # (adequado para demo/estudo, não recomendado em produção pública).
    PIPELINE_API_KEY: str = os.getenv("PIPELINE_API_KEY", "")

    # --- Autenticação (usuários, favoritos, alertas pessoais) ---
    # Chave usada para assinar os tokens JWT emitidos em /auth/login.
    # IMPORTANTE: defina SECRET_KEY no .env em produção; o valor padrão
    # abaixo é adequado apenas para demo/estudo local.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-troque-em-producao")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    @classmethod
    def ensure_directories(cls) -> None:
        for directory in (cls.RAW_DATA_DIR, cls.PROCESSED_DATA_DIR, cls.CACHE_DIR, cls.LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
