from cryptography.fernet import Fernet, InvalidToken

from acwa.errors import ApiError


class TokenCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("ACWA_TOKEN_ENCRYPTION_KEY must be a urlsafe base64-encoded 32-byte Fernet key") from exc

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode("utf-8"))

    def decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(value).decode("utf-8")
        except InvalidToken as exc:
            raise ApiError(
                500,
                "token_unreadable",
                "Не удалось расшифровать токен. Проверьте ключ шифрования.",
            ) from exc
