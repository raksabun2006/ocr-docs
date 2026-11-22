from __future__ import annotations

"""
JWT Token Management Module (RFC 7519 Compliant)
Khmer Government Document Intelligence Platform

Features:
- HS256 JWT creation and validation.
- Token expiration enforcement.
- Cryptographic signature verification.
- Token ID (jti) generation for revocation tracking.
"""

import hmac
import hashlib
import base64
import json
import time
import uuid
from typing import Dict, Any, Optional

from app.config import settings

# In-memory revocation cache for active process (persisted via database model when db is passed)
_REVOKED_TOKENS: set[str] = set()


def _b64url_encode(data: bytes) -> str:
    """Base64-URL encode without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(encoded_str: str) -> bytes:
    """Base64-URL decode with padding restored."""
    padding = "=" * (4 - (len(encoded_str) % 4)) if len(encoded_str) % 4 != 0 else ""
    return base64.urlsafe_b64decode((encoded_str + padding).encode("utf-8"))


def create_access_token(
    data: Dict[str, Any],
    expires_delta_seconds: Optional[int] = None,
    secret_key: Optional[str] = None
) -> str:
    """
    Creates a signed JWT access token.
    Default expiry: 8 hours (28800 seconds) for administrative working sessions.
    """
    secret = secret_key or settings.SECRET_KEY
    expiry = expires_delta_seconds or 28800

    now = int(time.time())
    payload = data.copy()
    payload["iat"] = now
    payload["exp"] = now + expiry
    if "jti" not in payload:
        payload["jti"] = str(uuid.uuid4())

    header = {"alg": "HS256", "typ": "JWT"}

    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    header_b64 = _b64url_encode(header_bytes)
    payload_b64 = _b64url_encode(payload_bytes)

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(
    token: str,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Decodes and cryptographically verifies a JWT token.
    Raises ValueError on invalid format, bad signature, or expired token.
    """
    secret = secret_key or settings.SECRET_KEY
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token format.")

    header_b64, payload_b64, signature_b64 = parts[0], parts[1], parts[2]

    # Verify signature
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(signature_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature.")

    # Decode payload
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Malformed token payload: {exc}")

    # Check expiration
    exp = payload.get("exp")
    if exp is not None and int(time.time()) > int(exp):
        raise ValueError("Token has expired.")

    # Check revocation
    jti = payload.get("jti")
    if jti and jti in _REVOKED_TOKENS:
        raise ValueError("Token has been revoked.")

    return payload


def revoke_token(jti: str) -> None:
    """Adds a token ID to the in-memory revocation list."""
    if jti:
        _REVOKED_TOKENS.add(jti)


def is_token_revoked(jti: str) -> bool:
    """Checks if a token ID has been revoked."""
    return jti in _REVOKED_TOKENS
