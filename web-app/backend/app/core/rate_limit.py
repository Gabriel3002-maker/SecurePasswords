"""Límite de intentos compartido entre workers vía Redis (fallback en memoria)."""
import time
import logging

from config import get_settings

logger = logging.getLogger(__name__)

try:
    import redis as _redis_lib
except ImportError:  # pragma: no cover
    _redis_lib = None

_redis_client = None


def _get_redis():
    """Devuelve el cliente Redis si está configurado y responde; si no, None."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if _redis_lib is None:
        return None
    try:
        url = get_settings().redis_url
    except Exception:
        return None
    if not url:
        return None
    try:
        client = _redis_lib.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        _redis_client = client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis no disponible, rate limit en memoria: %s", exc)
        _redis_client = None
    return _redis_client


class RateLimiter:
    """Contador de intentos con ventana deslizante.

    Permite `max_attempts` fallos dentro de una ventana de `lockout_seconds`.
    Cada fallo renueva la ventana (mismo comportamiento que el dict en memoria
    original); un acierto borra el contador.
    """

    def __init__(self, key_prefix: str, max_attempts: int, lockout_seconds: int = 900):
        self.key_prefix = key_prefix
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._memory: dict[str, dict] = {}

    def _rkey(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def remaining_lockout(self, key: str) -> int:
        """Segundos de bloqueo restantes; 0 = se permite intentar."""
        client = _get_redis()
        if client is not None:
            try:
                return self._redis_remaining(client, key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error con Redis, usando memoria: %s", exc)
        return self._memory_remaining(key)

    def record(self, key: str, success: bool) -> None:
        client = _get_redis()
        if client is not None:
            try:
                if success:
                    client.delete(self._rkey(key))
                    return
                self._redis_incr(client, key)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error con Redis, usando memoria: %s", exc)
        if success:
            self._memory.pop(key, None)
            return
        data = self._memory.setdefault(key, {"attempts": 0, "last_attempt": 0.0})
        data["attempts"] += 1
        data["last_attempt"] = time.time()

    def _redis_incr(self, client, key: str) -> None:
        rkey = self._rkey(key)
        pipe = client.pipeline(transaction=True)
        pipe.incr(rkey)
        pipe.expire(rkey, self.lockout_seconds)
        pipe.execute()

    def _redis_remaining(self, client, key: str) -> int:
        rkey = self._rkey(key)
        value = client.get(rkey)
        if value is None or int(value) < self.max_attempts:
            return 0
        ttl = client.ttl(rkey)
        return max(int(ttl), 1) if ttl else 1

    def _memory_remaining(self, key: str) -> int:
        now = time.time()
        data = self._memory.get(key)
        if not data:
            return 0
        if data["last_attempt"] + self.lockout_seconds < now:
            self._memory.pop(key, None)
            return 0
        if data["attempts"] >= self.max_attempts:
            restante = int(data["last_attempt"] + self.lockout_seconds - now)
            return max(restante, 1)
        return 0
