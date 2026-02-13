"""AWS STS 客户端模块

自包含模块，替代 backend.services.iam_role_session_factory。
提供 STS AssumeRole 功能获取临时凭证。
"""

import asyncio
import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .exceptions import AssumeRoleError

logger = logging.getLogger(__name__)

# 默认会话时长（秒）
DEFAULT_DURATION_SECONDS = 3600  # 1 小时


async def assume_role(
    role_arn: str,
    session_name: str,
    external_id: str,
    duration_seconds: int = DEFAULT_DURATION_SECONDS,
    region: Optional[str] = None,
) -> dict[str, str]:
    """通过 STS AssumeRole 获取临时凭证

    Args:
        role_arn: IAM Role ARN
        session_name: 会话名称（建议使用 UUID）
        external_id: External ID（必选，用于跨账号安全验证）
        duration_seconds: 凭证有效期（秒），默认 3600（1 小时）
        region: AWS 区域（可选，默认从环境变量读取）

    Returns:
        临时凭证字典
        {
            "AccessKeyId": "ASIA...",
            "SecretAccessKey": "...",
            "SessionToken": "...",
            "Expiration": datetime
        }

    Raises:
        AssumeRoleError: AssumeRole 失败
    """
    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")

    def _assume_role_sync():
        """同步执行 AssumeRole（在线程池中运行）"""
        try:
            sts_client = boto3.client("sts", region_name=region)

            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                DurationSeconds=duration_seconds,
                ExternalId=external_id,
            )

            credentials = response["Credentials"]
            # ✅ 不记录任何凭证信息（包括 AccessKeyId 前缀）
            logger.info(f"AssumeRole 成功 (使用 ExternalId): SessionName={session_name}")
            return credentials

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise AssumeRoleError(
                f"AssumeRole 失败 [{error_code}]: {error_message}"
            )
        except Exception as e:
            raise AssumeRoleError(f"AssumeRole 失败: {e}")

    # 在线程池中执行（避免阻塞事件循环）
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _assume_role_sync)


def assume_role_sync(
    role_arn: str,
    session_name: str,
    external_id: str,
    duration_seconds: int = DEFAULT_DURATION_SECONDS,
    region: Optional[str] = None,
) -> dict[str, str]:
    """同步版本的 AssumeRole（用于非异步环境）

    Args:
        role_arn: IAM Role ARN
        session_name: 会话名称
        external_id: External ID（必选，用于跨账号安全验证）
        duration_seconds: 凭证有效期（秒）
        region: AWS 区域

    Returns:
        临时凭证字典

    Raises:
        AssumeRoleError: AssumeRole 失败
    """
    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")

    try:
        sts_client = boto3.client("sts", region_name=region)

        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=duration_seconds,
            ExternalId=external_id,
        )

        credentials = response["Credentials"]
        # ✅ 不记录凭证信息
        logger.info(f"AssumeRole 成功 (使用 ExternalId): SessionName={session_name}")
        return credentials

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        raise AssumeRoleError(
            f"AssumeRole 失败 [{error_code}]: {error_message}"
        )
    except Exception as e:
        raise AssumeRoleError(f"AssumeRole 失败: {e}")
