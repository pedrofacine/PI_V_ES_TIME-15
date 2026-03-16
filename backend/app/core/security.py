"""
Segurança: hash de senha (bcrypt) e geração/validação de JWT.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import JWT_ALGORITHM, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES

# bcrypt tem limite de 72 bytes
BCRYPT_MAX_BYTES = 72


def _to_b72(password: str) -> bytes:
    """Garante que a senha em bytes não ultrapasse 72 bytes (limite do bcrypt)."""
    raw = password.encode("utf-8")
    return raw[:BCRYPT_MAX_BYTES] if len(raw) > BCRYPT_MAX_BYTES else raw


def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha."""
    pwd_bytes = _to_b72(password)
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano confere com o hash."""
    pwd_bytes = _to_b72(plain_password)
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))


def create_access_token(subject: str | Any) -> str:
    """Cria um JWT com o subject (ex.: user_id) e expiração."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(subject), "exp": expire}
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Decodifica o JWT e retorna o subject (user_id) ou None se inválido."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
