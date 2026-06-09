from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from cryptography.fernet import Fernet

from .config import get_settings

bearer = HTTPBearer(auto_error=False)


class EncryptionManager:
    def __init__(self) -> None:
        settings = get_settings()
        key = settings.encryption_key
        if key is None:
            key = Fernet.generate_key().decode()
        self.fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self.fernet.decrypt(value.encode()).decode()


def require_role(required_roles: set[str]):
    def _require_role(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
        settings = get_settings()
        if not credentials:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
        token = credentials.credentials
        role = None
        if token == settings.admin_token:
            role = "admin"
        elif token == settings.viewer_token:
            role = "viewer"
        if role not in required_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return role

    return _require_role
