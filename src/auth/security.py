"""
src/auth/security.py

Primitivas de segurança usadas pela autenticação de usuários:
- Hash de senha com PBKDF2-HMAC-SHA256 (biblioteca padrão do Python, sem
  dependências nativas extras como bcrypt/argon2 — mantém o projeto
  "zero configuração" fácil de instalar em qualquer ambiente).
- Emissão/validação de tokens JWT (via PyJWT) para autenticar chamadas à
  API REST (`Authorization: Bearer <token>`).

Este módulo não depende do FastAPI nem do banco de dados: só lida com
criptografia e tokens, o que facilita testá-lo isoladamente.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from config.settings import settings

_PBKDF2_ITERATIONS = 260_000
_PBKDF2_ALGO = "sha256"


def hash_password(password: str) -> str:
    """Gera um hash de senha no formato `pbkdf2_sha256$iterações$salt$hash`.

    O salt é gerado aleatoriamente a cada chamada e guardado junto do hash
    (formato auto-contido, como o usado por Django), então não é preciso
    uma coluna extra no banco para o salt.
    """
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO, password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Confere uma senha em texto puro contra um hash gerado por `hash_password`."""
    try:
        algo, iterations_str, salt, hex_digest = stored_hash.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False

    derived = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO, password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return hmac.compare_digest(derived.hex(), hex_digest)


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """Cria um JWT assinado contendo `sub` (id do usuário) e expiração.

    `subject` deve ser algo estável e único (usamos o id do usuário como
    string) — nunca a senha ou outro dado sensível.
    """
    expires_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica e valida um JWT. Retorna o payload ou `None` se inválido/expirado."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
