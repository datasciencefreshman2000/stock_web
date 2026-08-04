import jwt
import pytest

from services.auth import hash_password, verify_password

# 測試用低迭代數，避免拖慢測試
FAST = 1000


def test_hash_and_verify_roundtrip():
    encoded = hash_password("correct horse battery", iterations=FAST)
    assert verify_password("correct horse battery", encoded) is True


def test_wrong_password_is_rejected():
    encoded = hash_password("secret-password", iterations=FAST)
    assert verify_password("secret-passwore", encoded) is False
    assert verify_password("", encoded) is False


def test_same_password_produces_different_hashes():
    """每次都要有新的 salt，否則相同密碼會產生相同雜湊。"""
    a = hash_password("same", iterations=FAST)
    b = hash_password("same", iterations=FAST)
    assert a != b
    assert verify_password("same", a) and verify_password("same", b)


@pytest.mark.parametrize("bad", ["", "not-a-hash", "pbkdf2_sha256$abc", "md5$1$aa$bb"])
def test_malformed_hash_is_rejected_not_crashed(bad):
    assert verify_password("anything", bad) is False


def test_token_signed_with_other_secret_is_rejected():
    token = jwt.encode({"sub": "owner"}, "attacker-secret", algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "real-secret", algorithms=["HS256"])


def test_unsigned_token_is_rejected():
    """防 alg=none 攻擊。"""
    token = jwt.encode({"sub": "owner"}, "", algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "real-secret", algorithms=["HS256"])
