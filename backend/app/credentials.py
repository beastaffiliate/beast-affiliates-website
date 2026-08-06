"""Recoverable copies of the passwords the admin hands out.

Login itself is unchanged and still verifies against the PBKDF2 hash in
`portal_accounts.password_hash` — nothing here weakens authentication. This
module exists only so the admin panel can re-show a password it issued, because
a hash cannot be reversed and admins kept losing the one-time reveal.

The copy is encrypted with a key that lives in the environment, not the
database, so a leaked database dump on its own does not expose anyone's
password. With no key configured the feature simply switches off: nothing is
written, and the admin panel falls back to issuing a fresh password.
"""

import os

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    Fernet = None
    InvalidToken = Exception

# Generate one with:  python -c "from cryptography.fernet import Fernet;
#                                print(Fernet.generate_key().decode())"
CREDENTIAL_KEY = os.getenv("CREDENTIAL_KEY", "").strip()

_fernet = None
if Fernet is not None and CREDENTIAL_KEY:
    try:
        _fernet = Fernet(CREDENTIAL_KEY.encode())
    except Exception:  # malformed key — treat exactly like an absent one
        _fernet = None


def enabled() -> bool:
    """True when passwords issued from now on can be shown again later."""
    return _fernet is not None


def encrypt(password: str) -> str:
    """Ciphertext to store, or "" when the feature is off or there is nothing
    to store. Never raises — failing to keep a convenience copy must not stop
    an account from being created."""
    if _fernet is None or not password:
        return ""
    try:
        return _fernet.encrypt(password.encode()).decode()
    except Exception:
        return ""


def decrypt(token: str) -> str:
    """The stored password, or "" if absent, unreadable, or written under a
    different key (which is what a rotated CREDENTIAL_KEY looks like)."""
    if _fernet is None or not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return ""
