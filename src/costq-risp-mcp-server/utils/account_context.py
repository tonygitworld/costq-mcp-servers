"""账号上下文管理模块

提供 AWS 账号凭证上下文设置功能。
独立模块，避免 server.py 与 handlers 之间的循环导入。
"""

import logging

from cred_extract_services import (
    extract_aws_credentials,
    set_aws_credentials,
)

logger = logging.getLogger(__name__)


async def _setup_account_context(
    target_account_id: str,
) -> dict[str, str]:
    """设置 AWS 凭证上下文

    统一入口函数，完成以下操作：
    1. 查询账号信息（自包含数据库查询）
    2. 提取凭证（AKSK 解密 / IAM Role AssumeRole）
    3. 设置环境变量

    Args:
        target_account_id: AWS 账号 ID

    Returns:
        凭证信息字典（用于日志记录，已脱敏）

    Raises:
        AccountNotFoundError: 账号不存在
        CredentialDecryptionError: 凭证解密失败
        AssumeRoleError: AssumeRole 失败
        DatabaseConnectionError: 数据库连接失败
    """
    logger.info("开始设置 AWS 凭证上下文")

    credentials = await extract_aws_credentials(target_account_id)

    set_aws_credentials(
        access_key_id=credentials["access_key_id"],
        secret_access_key=credentials["secret_access_key"],
        session_token=credentials.get("session_token"),
        region=credentials.get("region", "us-east-1"),
    )

    return {
        "account_id": credentials["account_id"],
        "account_alias": credentials.get("alias", "Unknown"),
        "auth_type": credentials["auth_type"],
        "region": credentials.get("region", "us-east-1"),
    }
