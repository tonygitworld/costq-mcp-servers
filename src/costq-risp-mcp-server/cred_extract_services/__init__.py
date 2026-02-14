"""凭证提取服务公共接口

导出所有公共类和函数，便于外部调用。
"""

import logging

from .aws_client import assume_role, assume_role_sync
from .context_manager import (
    is_credentials_set,
    set_aws_credentials,
)
from .credential_extractor import extract_aws_credentials
from .crypto import decrypt_aksk, encrypt_aksk
from .database import close_connection, query_account
from .exceptions import (
    AccountNotFoundError,
    AssumeRoleError,
    CredentialDecryptionError,
    CredentialExtractionError,
    DatabaseConnectionError,
)

logger = logging.getLogger(__name__)


async def setup_account_context(target_account_id: str) -> dict[str, str]:
    """设置 AWS 凭证上下文

    从数据库提取指定账号的 AWS 凭证，并设置到环境变量中。
    boto3 会自动使用这些环境变量进行 API 调用。

    Args:
        target_account_id: AWS 账号 ID

    Returns:
        脱敏的凭证信息字典
        {
            "account_id": str,
            "account_alias": str,
            "auth_type": str,
            "region": str
        }

    Raises:
        AccountNotFoundError: 账号不存在
        CredentialDecryptionError: 凭证解密失败
        AssumeRoleError: AssumeRole 失败
        DatabaseConnectionError: 数据库连接失败
    """
    logger.info(f"设置账号上下文: {target_account_id}")

    # 提取凭证
    credentials = await extract_aws_credentials(target_account_id)

    # 设置环境变量
    set_aws_credentials(
        access_key_id=credentials["access_key_id"],
        secret_access_key=credentials["secret_access_key"],
        session_token=credentials.get("session_token"),
        region=credentials.get("region", "us-east-1"),
    )

    # 返回脱敏信息
    return {
        "account_id": credentials["account_id"],
        "account_alias": credentials.get("alias", "Unknown"),
        "auth_type": credentials["auth_type"],
        "region": credentials.get("region", "us-east-1"),
    }


__all__ = [
    # 凭证提取
    "extract_aws_credentials",
    "setup_account_context",
    # 环境变量管理
    "set_aws_credentials",
    "is_credentials_set",
    # 数据库
    "query_account",
    "close_connection",
    # 加密解密
    "decrypt_aksk",
    "encrypt_aksk",
    # AWS 客户端
    "assume_role",
    "assume_role_sync",
    # 异常
    "CredentialExtractionError",
    "AccountNotFoundError",
    "CredentialDecryptionError",
    "AssumeRoleError",
    "DatabaseConnectionError",
]
