"""Password hashing, session tokens and invite codes (standard library only)."""

import hashlib
import hmac
import os
import secrets
from typing import Optional, Tuple

from app.core.config import settings

# No look-alike characters (0/O, 1/I) so invite codes are easy to read aloud.
_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """PBKDF2-HMAC-SHA256 with a per-user random 16-byte salt. Returns (hash, salt)."""
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, settings.PBKDF2_ITERATIONS
    )
    return digest, salt


def verify_password(password: str, pw_hash: bytes, salt: bytes) -> bool:
    """Re-derive the hash and compare in constant time."""
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, pw_hash)


def new_session_token() -> str:
    """256-bit random bearer token."""
    return secrets.token_urlsafe(32)


def new_invite_code() -> str:
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(6))
