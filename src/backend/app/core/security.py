from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings


class TokenEncryptionError(RuntimeError):
    """Token 加密或解密失败时抛出的业务异常。"""


def generate_token_encryption_key() -> str:
    """生成用于本地加密 OAuth Token 的 Fernet key。

    阶段 1 只提供工具函数；阶段 2 接入 Google OAuth 时，会用这个 key
    对 access token 和 refresh token 做加密存储。
    """
    return Fernet.generate_key().decode("utf-8")


def get_token_cipher(settings: Settings | None = None) -> Fernet:
    """创建 OAuth Token 加密器。

    `TOKEN_ENCRYPTION_KEY` 必须只存在本地 `.env`。如果继续使用
    `replace-me`，说明本地密钥还没有配置好，此时宁可拒绝 OAuth
    写入，也不能把 Google access token 明文落库。
    """
    active_settings = settings or get_settings()
    if active_settings.token_encryption_key == "replace-me":
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY 尚未配置，不能保存 OAuth Token。")

    try:
        return Fernet(active_settings.token_encryption_key.encode("utf-8"))
    except ValueError as exc:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY 不是合法的 Fernet key。") from exc


def encrypt_secret(value: str, settings: Settings | None = None) -> str:
    """加密敏感字符串，当前主要用于 Google OAuth Token。"""
    return get_token_cipher(settings).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str, settings: Settings | None = None) -> str:
    """解密敏感字符串。

    如果密文无法解开，通常表示本地 `.env` 的 `TOKEN_ENCRYPTION_KEY`
    被替换过。此时不能继续调用 Google API，必须提示用户重新连接账号。
    """
    try:
        return get_token_cipher(settings).decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise TokenEncryptionError("OAuth Token 解密失败，请重新连接 Google 账号。") from exc
