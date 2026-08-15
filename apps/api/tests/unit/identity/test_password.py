import pytest

from citypulse.identity.password import (
    PasswordPolicyError,
    hash_password,
    needs_rehash,
    validate_password_policy,
    verify_password,
)


@pytest.mark.parametrize(
    "password",
    ["short1A", "password123", "1234567890", "abcdefghij", "admin-admin-1234"],
)
def test_policy_rejects_weak_passwords(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        validate_password_policy(password, username="admin")


def test_policy_accepts_strong_password() -> None:
    validate_password_policy("correct-horse-9", username="admin")


def test_hash_and_verify_roundtrip() -> None:
    password_hash = hash_password("correct-horse-9")

    assert verify_password(password_hash, "correct-horse-9")
    assert not verify_password(password_hash, "wrong-password-9")
    assert not verify_password("not-a-valid-hash", "correct-horse-9")


def test_hashes_are_salted_and_stable_for_rehash_check() -> None:
    first = hash_password("correct-horse-9")
    second = hash_password("correct-horse-9")

    assert first != second
    assert not needs_rehash(first)
