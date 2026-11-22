from __future__ import annotations

"""
Secure Password Hashing & Strength Validation Module
Khmer Government Document Intelligence Platform

Security Features:
- Argon2id with memory-hard Scrypt fallback (RFC 7914 standard).
- Cryptographically secure random salts (os.urandom).
- Constant-time verification to prevent timing attacks.
- Strict password policy enforcement for government security compliance.
"""

import os
import re
import hmac
import hashlib
from typing import Tuple, Optional

# Attempt to load argon2-cffi if available in the environment
_HAS_ARGON2 = False
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    _ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32)
    _HAS_ARGON2 = True
except ImportError:
    _ph = None


COMMON_WEAK_PASSWORDS = {
    "password", "password123", "admin123", "administrator", "12345678",
    "cambodia", "khmer123", "gov12345", "root1234", "qwerty123"
}


class PasswordPolicyError(Exception):
    """Raised when a password does not satisfy security requirements."""
    pass


def validate_password_strength(password: str, min_length: int = 8) -> Tuple[bool, Optional[str]]:
    """
    Validates password complexity against government security baseline:
    - Minimum length (default 8, recommended 12 for admins).
    - At least one uppercase letter.
    - At least one lowercase letter.
    - At least one numerical digit.
    - At least one special/symbol character.
    - Not in known common weak passwords list.
    """
    if not password:
        return False, "Password cannot be empty."

    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long."

    if password.lower() in COMMON_WEAK_PASSWORDS:
        return False, "Password is too common and easily guessable."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."

    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit (0-9)."

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+~`\[\]/\\]", password):
        return False, "Password must contain at least one special character (!@#$%^&* etc.)."

    return True, None


def hash_password(password: str) -> str:
    """
    Hashes a password using Argon2id if available, or cryptographically secure Scrypt.
    Format:
    - Argon2id: $argon2id$...
    - Scrypt fallback: scrypt$n=16384,r=8,p=1$<salt_hex>$<hash_hex>
    """
    if _HAS_ARGON2 and _ph is not None:
        return _ph.hash(password)

    # Standard library Scrypt (memory-hard, resistant to GPU/ASIC brute forcing)
    salt = os.urandom(16)
    n, r, p = 16384, 8, 1
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=0)
    return f"scrypt$n={n},r={r},p={p}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored hash using constant-time comparison.
    Supports both Argon2id and Scrypt hash formats.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        # Check Argon2 format
        if hashed_password.startswith("$argon2"):
            if _HAS_ARGON2 and _ph is not None:
                try:
                    return _ph.verify(hashed_password, plain_password)
                except VerifyMismatchError:
                    return False
            # If argon2-cffi is not installed, cannot verify an argon2 hash
            return False

        # Check Scrypt format
        if hashed_password.startswith("scrypt$"):
            parts = hashed_password.split("$")
            if len(parts) != 4:
                return False
            params_str, salt_hex, key_hex = parts[1], parts[2], parts[3]

            # Parse parameters
            params = dict(item.split("=") for item in params_str.split(","))
            n = int(params.get("n", 16384))
            r = int(params.get("r", 8))
            p = int(params.get("p", 1))

            salt = bytes.fromhex(salt_hex)
            expected_key = bytes.fromhex(key_hex)

            computed_key = hashlib.scrypt(
                plain_password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                maxmem=0
            )
            return hmac.compare_digest(computed_key, expected_key)

        # Legacy PBKDF2 fallback if present
        if hashed_password.startswith("pbkdf2$"):
            parts = hashed_password.split("$")
            if len(parts) == 4:
                iterations = int(parts[1])
                salt = bytes.fromhex(parts[2])
                expected_key = bytes.fromhex(parts[3])
                computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
                return hmac.compare_digest(computed, expected_key)

    except Exception:
        return False

    return False
