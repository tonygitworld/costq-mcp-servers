"""凭证提取核心逻辑

自包含模块，根据账号类型提取 AWS 凭证。
支持 AKSK 和 IAM Role 两种认证方式。
"""

import logging
import uuid

from .aws_client import assume_role
from .crypto import decrypt_aksk
from .database import query_account
from .exceptions import (
    AccountNotFoundError,
    AssumeRoleError,
    CredentialDecryptionError,
)

logger = logging.getLogger(__name__)


async def extract_aws_credentials(account_id: str) -> dict[str, str]:
    """提取 AWS 账号凭证

    前置条件：
        - account_id 已通过权限验证
        - 调用方有权访问该账号

    Args:
        account_id: AWS 账号 ID（数据库主键）

    Returns:
        凭证字典
        {
            "access_key_id": "AKIA...",
            "secret_access_key": "...",
            "session_token": "...",  # 可选
            "region": "us-east-1",
            "account_id": "123456789012",
            "alias": "production",
            "auth_type": "iam_role"  # 或 "aksk"
        }

    Raises:
        AccountNotFoundError: 账号不存在
        CredentialDecryptionError: 凭证解密失败
        AssumeRoleError: AssumeRole 失败
    """
    # 1. 查询账号信息
    account = await query_account(account_id)

    if not account:
        raise AccountNotFoundError(f"账号不存在: {account_id}")

    auth_type = account.get("auth_type")
    # ✅ 只记录非敏感的元数据
    logger.info(
        f"开始提取凭证: Alias={account.get('alias')}, "
        f"AuthType={auth_type}"
    )

    # 2. 根据类型提取凭证
    if auth_type == "aksk":
        credentials = await _extract_aksk_credentials(account)
    elif auth_type == "iam_role":
        credentials = await _extract_iam_role_credentials(account)
    else:
        raise ValueError(f"不支持的账号类型: {auth_type}")

    # 3. 添加元数据
    credentials["alias"] = account.get("alias", "Unknown")
    credentials["auth_type"] = auth_type

    # ✅ 只记录成功状态，不记录凭证内容
    logger.info(f"✅ 凭证提取成功: AuthType={auth_type}")
    return credentials


async def _extract_aksk_credentials(account: dict) -> dict[str, str]:
    """解密 AKSK 凭证

    注意：Access Key ID 存储为明文，只需解密 Secret Access Key。

    Args:
        account: 账号信息字典

    Returns:
        凭证字典

    Raises:
        CredentialDecryptionError: 解密失败
    """
    access_key_id = account.get("access_key_id")
    encrypted_secret_key = account.get("encrypted_secret_key")

    if not access_key_id:
        raise CredentialDecryptionError(
            f"账号 {account.get('id')} 未配置 Access Key ID"
        )

    if not encrypted_secret_key:
        raise CredentialDecryptionError(
            f"账号 {account.get('id')} 未配置加密的 Secret Access Key"
        )

    try:
        # 解密 Secret Access Key
        decrypted = decrypt_aksk(encrypted_secret_key)

        return {
            "access_key_id": access_key_id,  # 明文
            "secret_access_key": decrypted["secret_key"],  # 解密
            "session_token": None,  # AKSK 没有 session token
            "region": account.get("region") or "us-east-1",
            "account_id": account.get("account_id"),
        }
    except CredentialDecryptionError:
        raise
    except Exception as e:
        raise CredentialDecryptionError(f"AKSK 凭证提取失败: {e}")


async def _extract_iam_role_credentials(account: dict) -> dict[str, str]:
    """通过 AssumeRole 获取临时凭证

    Args:
        account: 账号信息字典

    Returns:
        凭证字典

    Raises:
        AssumeRoleError: AssumeRole 失败
    """
    role_arn = account.get("role_arn")
    external_id = account.get("external_id")

    if not role_arn:
        raise AssumeRoleError(f"账号 {account.get('id')} 未配置 Role ARN")

    if not external_id:
        account_id = account.get('account_id', 'unknown')
        raise AssumeRoleError(
            f"账号 {account_id} (auth_type=iam_role) 所属组织未配置 external_id"
        )

    try:
        # 生成唯一的会话名称
        session_name = f"costq-{uuid.uuid4()}"

        # 执行 AssumeRole
        credentials = await assume_role(
            role_arn=role_arn,
            session_name=session_name,
            external_id=external_id,
            region=account.get("region") or "us-east-1",
        )

        return {
            "access_key_id": credentials["AccessKeyId"],
            "secret_access_key": credentials["SecretAccessKey"],
            "session_token": credentials["SessionToken"],
            "region": account.get("region") or "us-east-1",
            "account_id": account.get("account_id"),
        }
    except AssumeRoleError:
        raise
    except Exception as e:
        raise AssumeRoleError(f"IAM Role 凭证提取失败: {e}")
