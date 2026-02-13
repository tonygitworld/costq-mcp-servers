"""加密解密模块

自包含模块，替代 backend.services.credential_manager。
使用 Fernet 对称加密算法解密 AKSK 凭证。
"""

import json
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from .exceptions import CredentialDecryptionError

logger = logging.getLogger(__name__)


def _get_encryption_key() -> str:
    """获取加密密钥

    从环境变量 ENCRYPTION_KEY 读取 Fernet 密钥（Base64 编码）。

    Returns:
        加密密钥字符串

    Raises:
        CredentialDecryptionError: 未设置加密密钥
    """
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        raise CredentialDecryptionError(
            "未设置加密密钥，请配置 ENCRYPTION_KEY 环境变量"
        )
    return encryption_key


def decrypt_secret_key(
    encrypted_secret_key: str,
    encryption_key: Optional[str] = None,
) -> str:
    """解密 Secret Access Key（兼容项目原有实现）

    注意：项目中只加密 Secret Access Key，Access Key ID 存储为明文。

    Args:
        encrypted_secret_key: 加密的 Secret Access Key（Fernet 加密后的密文）
        encryption_key: Fernet 加密密钥（Base64 编码），
                       为 None 时从环境变量读取

    Returns:
        解密后的 Secret Access Key 明文

    Raises:
        CredentialDecryptionError: 解密失败
    """
    if encryption_key is None:
        encryption_key = _get_encryption_key()

    try:
        # 初始化 Fernet
        fernet = Fernet(encryption_key.encode())

        # 解密
        decrypted_bytes = fernet.decrypt(encrypted_secret_key.encode())
        secret_key = decrypted_bytes.decode("utf-8")

        logger.debug("Secret Access Key 解密成功")
        return secret_key

    except InvalidToken:
        raise CredentialDecryptionError("解密失败：密钥无效或密文已损坏")
    except Exception as e:
        if isinstance(e, CredentialDecryptionError):
            raise
        raise CredentialDecryptionError(f"Secret Access Key 解密失败: {e}")


def decrypt_aksk(
    encrypted_credential: str,
    encryption_key: Optional[str] = None,
) -> dict[str, str]:
    """解密 AKSK 凭证（向后兼容接口）

    实际上只解密 Secret Access Key。

    Args:
        encrypted_credential: 加密的 Secret Access Key
        encryption_key: Fernet 加密密钥

    Returns:
        包含解密后 secret_key 的字典
        {
            "secret_key": "..."
        }

    Raises:
        CredentialDecryptionError: 解密失败
    """
    secret_key = decrypt_secret_key(encrypted_credential, encryption_key)
    return {"secret_key": secret_key}


def encrypt_aksk(
    access_key: str,
    secret_key: str,
    encryption_key: Optional[str] = None,
) -> str:
    """加密 AKSK 凭证（可选，用于测试）

    Args:
        access_key: AWS Access Key ID
        secret_key: AWS Secret Access Key
        encryption_key: Fernet 加密密钥（Base64 编码）

    Returns:
        加密后的密文字符串
    """
    if encryption_key is None:
        encryption_key = _get_encryption_key()

    credentials = {
        "access_key": access_key,
        "secret_key": secret_key,
    }

    fernet = Fernet(encryption_key.encode())
    encrypted = fernet.encrypt(json.dumps(credentials).encode())
    return encrypted.decode("utf-8")
