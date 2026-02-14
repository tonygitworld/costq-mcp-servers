"""环境变量管理模块

使用 os.environ 管理 AWS 凭证。
boto3 自动识别这些标准环境变量，无需额外配置。

注意：环境变量是进程级别的，适用于：
    - Lambda 函数（每个请求独立容器）
    - 单线程/单请求的 MCP Server
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# boto3 标准环境变量名
_ENV_ACCESS_KEY = 'AWS_ACCESS_KEY_ID'
_ENV_SECRET_KEY = 'AWS_SECRET_ACCESS_KEY'
_ENV_SESSION_TOKEN = 'AWS_SESSION_TOKEN'
_ENV_REGION = 'AWS_DEFAULT_REGION'


def set_aws_credentials(
    access_key_id: str,
    secret_access_key: str,
    session_token: Optional[str] = None,
    region: str = "us-east-1",
) -> None:
    """设置 AWS 凭证到环境变量

    Args:
        access_key_id: AWS Access Key ID
        secret_access_key: AWS Secret Access Key
        session_token: AWS Session Token（临时凭证，可选）
        region: AWS 区域
    """
    os.environ[_ENV_ACCESS_KEY] = access_key_id
    os.environ[_ENV_SECRET_KEY] = secret_access_key

    # Session Token 处理：有值则设置，无值则删除（避免残留）
    if session_token:
        os.environ[_ENV_SESSION_TOKEN] = session_token
    elif _ENV_SESSION_TOKEN in os.environ:
        del os.environ[_ENV_SESSION_TOKEN]

    os.environ[_ENV_REGION] = region

    # ✅ 不记录任何凭证信息（包括 AccessKeyId 前缀）
    logger.info(f"✅ AWS 凭证已设置到环境变量: Region={region}")


def is_credentials_set() -> bool:
    """检查 AWS 凭证是否已设置

    Returns:
        True 如果已设置，False 否则
    """
    return (
        _ENV_ACCESS_KEY in os.environ
        and _ENV_SECRET_KEY in os.environ
    )
