import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 10

WEAK_PASSWORDS = frozenset(
    {
        "password123",
        "1234567890",
        "qwertyuiop",
        "letmein123",
        "admin12345",
        "citypulse123",
        "welcome123",
        "iloveyou123",
    }
)

_hasher = PasswordHasher()


class PasswordPolicyError(ValueError):
    pass


def validate_password_policy(password: str, *, username: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError("The password must contain at least 10 characters.")
    if password.lower() in WEAK_PASSWORDS:
        raise PasswordPolicyError("The password is too common, choose a stronger one.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise PasswordPolicyError("The password must combine letters and digits.")
    if username.lower() in password.lower():
        raise PasswordPolicyError("The password must not contain the username.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
