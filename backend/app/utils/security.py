from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import logging
import bcrypt
import jwt
from app.config import settings

logger = logging.getLogger("one-click-attendance.security")

# Maximum bytes supported by bcrypt algorithm
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """
    Hash plain-text password using bcrypt. Never stores plain text.
    Safely handles password length bounds and empty inputs.
    """
    if not password or not isinstance(password, str):
        raise ValueError("Password must be a non-empty string.")

    # Bcrypt strictly enforces a 72-byte ceiling on UTF-8 encoded bytes.
    # Safely pre-truncate to 72 bytes to avoid unhandled ValueError exceptions.
    password_bytes = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against stored bcrypt hash using constant-time check.
    Returns False gracefully on malformed hashes or empty inputs.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        pw_bytes = plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception as exc:
        logger.warning(f"Password verification failure: {exc}")
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token with standard expiration and claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token against the configured algorithm and signature."""
    if not token or not isinstance(token, str):
        return None
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
        return payload
    except (jwt.PyJWTError, Exception):
        return None
