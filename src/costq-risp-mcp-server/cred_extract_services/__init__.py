"""凭证提取服务公共接口

导出所有公共类和函数，便于外部调用。
"""

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

__all__ = [
    # 凭证提取
    "extract_aws_credentials",
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
