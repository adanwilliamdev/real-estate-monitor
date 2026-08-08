"""
src/data_storage/cache_manager.py

Cache simples para respostas de API / dados processados. Usa Redis se
`USE_REDIS=true` e o pacote `redis` estiver instalado e acessível; caso
contrário, cai automaticamente para um cache em memória do processo, para
que o restante da aplicação nunca dependa de um serviço externo rodando.
"""
import json
import time
from typing import Any, Dict, Optional

from config.settings import settings
from src.logging_setup import logger


class CacheManager:
    """Gerencia cache de dados, com Redis opcional e fallback em memória."""

    def __init__(self):
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self.redis_client = None

        if settings.USE_REDIS and settings.REDIS_URL:
            try:
                import redis  # import tardio, dependência opcional

                self.redis_client = redis.from_url(settings.REDIS_URL, socket_timeout=2)
                self.redis_client.ping()
                logger.info("CacheManager conectado ao Redis")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Redis indisponível ({exc}); usando cache em memória")
                self.redis_client = None

    def get_cached_data(self, key: str, max_age_hours: int = 24) -> Optional[Any]:
        if self.redis_client:
            try:
                raw = self.redis_client.get(key)
                if raw:
                    entry = json.loads(raw)
                    if time.time() - entry["timestamp"] < max_age_hours * 3600:
                        return entry["data"]
                    self.redis_client.delete(key)
                return None
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Erro lendo do Redis: {exc}")
                return None

        entry = self._memory_store.get(key)
        if entry and time.time() - entry["timestamp"] < max_age_hours * 3600:
            return entry["data"]
        if entry:
            del self._memory_store[key]
        return None

    def cache_data(self, key: str, data: Any, ttl_hours: int = 24) -> bool:
        entry = {"data": data, "timestamp": time.time()}

        if self.redis_client:
            try:
                self.redis_client.setex(key, int(ttl_hours * 3600), json.dumps(entry))
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Erro gravando no Redis: {exc}")
                return False

        self._memory_store[key] = entry
        return True

    def clear_cache(self, pattern: str = "*") -> None:
        if self.redis_client:
            try:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Erro limpando cache Redis: {exc}")
            return

        self._memory_store.clear()
