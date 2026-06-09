from app.security import EncryptionManager


def test_encryption_round_trip() -> None:
    manager = EncryptionManager()
    token = manager.encrypt("secret-value")
    assert token != "secret-value"
    assert manager.decrypt(token) == "secret-value"
