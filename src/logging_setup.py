"""
src/logging_setup.py
Configuração única do Loguru para toda a aplicação. Importar este módulo
(via `from src.logging_setup import logger`) garante que os logs sejam
formatados de forma consistente e gravados em arquivo + console.
"""
import sys

from loguru import logger

from config.settings import settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add(
        settings.LOG_FILE,
        level=settings.LOG_LEVEL,
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
    )
    _CONFIGURED = True


configure_logging()

__all__ = ["logger"]
