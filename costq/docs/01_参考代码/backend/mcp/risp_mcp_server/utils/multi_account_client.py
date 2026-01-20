"""多账号 AWS 客户端管理

该模块为 MCP 工具提供多账号支持：
1. 根据 account_id 获取凭证
2. 创建特定账号的 boto3 客户端
3. 与现有代码兼容（无 account_id 时使用默认 Profile）
"""

import logging
import os
import sys

# 导入凭证提供服务
# 需要添加项目根目录到 Python 路径
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.services.aws_credentials_provider import get_credentials_provider

# Configure Loguru logging


def get_cost_explorer_client_for_account(account_id: str | None = None):
    """获取指定账号的 Cost Explorer 客户端

    如果提供 account_id，使用该账号的 AKSK 凭证。
    如果不提供，使用默认的本地 Profile（兼容现有代码）。

    Args:
        account_id: 可选的账号 ID。如果为 None，使用默认 Profile

    Returns:
        boto3.client: Cost Explorer 客户端

    Example:
        # 使用特定账号
        ce_client = get_cost_explorer_client_for_account('account-id-123')

        # 使用默认 Profile（兼容现有代码）
        ce_client = get_cost_explorer_client_for_account()
    """
    try:
        if account_id:
            # 多账号模式：使用 AKSK
            logger.info(f"🔑 创建多账号 CE 客户端 - Account ID: {account_id}")

            # 获取凭证提供服务
            credentials_provider = get_credentials_provider()

            # 创建 Session
            session = credentials_provider.create_session(account_id)

            # 创建 Cost Explorer 客户端
            ce_client = session.client("ce")

            # 获取账号信息用于日志
            account_info = credentials_provider.get_account_info(account_id)
            logger.info(
                f"✅ CE 客户端创建成功 - Account: {account_info['alias']} "
                f"({account_info['account_id']})"
            )

            return ce_client

        else:
            # 单账号模式：使用本地 Profile（兼容现有代码）
            logger.info("🔑 创建默认 CE 客户端 - 使用本地 Profile")

            aws_region = os.environ.get("MCP_AWS_DEFAULT_REGION") or os.environ.get(
                "AWS_REGION", "us-east-1"
            )
            aws_profile = os.environ.get("MCP_AWS_PROFILE") or os.environ.get("AWS_PROFILE")

            if aws_profile:
                logger.info(f"使用 AWS Profile: {aws_profile}")
                session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
            else:
                logger.info("使用默认 AWS 凭证")
                session = boto3.Session(region_name=aws_region)

            ce_client = session.client("ce")
            logger.info("✅ CE 客户端创建成功（默认 Profile）")

            return ce_client

    except Exception as e:
        logger.error(f"❌ Cost Explorer 客户端创建失败: {e}", exc_info=True)
        raise


def get_compute_optimizer_client_for_account(account_id: str | None = None):
    """获取指定账号的 Compute Optimizer 客户端

    Args:
        account_id: 可选的账号 ID。如果为 None，使用默认 Profile

    Returns:
        boto3.client: Compute Optimizer 客户端
    """
    try:
        if account_id:
            logger.info(f"🔑 创建多账号 Compute Optimizer 客户端 - Account ID: {account_id}")

            credentials_provider = get_credentials_provider()
            session = credentials_provider.create_session(account_id)
            client = session.client("compute-optimizer")

            account_info = credentials_provider.get_account_info(account_id)
            logger.info(f"✅ Compute Optimizer 客户端创建成功 - Account: {account_info['alias']}")

            return client

        else:
            logger.info("🔑 创建默认 Compute Optimizer 客户端")

            aws_region = os.environ.get("MCP_AWS_DEFAULT_REGION") or os.environ.get(
                "AWS_REGION", "us-east-1"
            )
            aws_profile = os.environ.get("MCP_AWS_PROFILE") or os.environ.get("AWS_PROFILE")

            if aws_profile:
                session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
            else:
                session = boto3.Session(region_name=aws_region)

            client = session.client("compute-optimizer")
            logger.info("✅ Compute Optimizer 客户端创建成功（默认 Profile）")

            return client

    except Exception as e:
        logger.error(f"❌ Compute Optimizer 客户端创建失败: {e}", exc_info=True)
        raise


def get_cost_optimization_hub_client_for_account(account_id: str | None = None):
    """获取指定账号的 Cost Optimization Hub 客户端

    Args:
        account_id: 可选的账号 ID。如果为 None，使用默认 Profile

    Returns:
        boto3.client: Cost Optimization Hub 客户端
    """
    try:
        if account_id:
            logger.info(f"🔑 创建多账号 Cost Optimization Hub 客户端 - Account ID: {account_id}")

            credentials_provider = get_credentials_provider()
            session = credentials_provider.create_session(account_id)
            client = session.client("cost-optimization-hub")

            account_info = credentials_provider.get_account_info(account_id)
            logger.info(
                f"✅ Cost Optimization Hub 客户端创建成功 - Account: {account_info['alias']}"
            )

            return client

        else:
            logger.info("🔑 创建默认 Cost Optimization Hub 客户端")

            aws_region = os.environ.get("MCP_AWS_DEFAULT_REGION") or os.environ.get(
                "AWS_REGION", "us-east-1"
            )
            aws_profile = os.environ.get("MCP_AWS_PROFILE") or os.environ.get("AWS_PROFILE")

            if aws_profile:
                session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
            else:
                session = boto3.Session(region_name=aws_region)

            client = session.client("cost-optimization-hub")
            logger.info("✅ Cost Optimization Hub 客户端创建成功（默认 Profile）")

            return client

    except Exception as e:
        logger.error(f"❌ Cost Optimization Hub 客户端创建失败: {e}", exc_info=True)
        raise


# 向后兼容的工厂函数
def create_aws_client(service_name: str, account_id: str | None = None):
    """创建 AWS 服务客户端的通用工厂函数

    Args:
        service_name: AWS 服务名称 (ce, compute-optimizer, cost-optimization-hub)
        account_id: 可选的账号 ID

    Returns:
        boto3.client: AWS 服务客户端

    Example:
        client = create_aws_client('ce', 'account-id-123')
    """
    service_map = {
        "ce": get_cost_explorer_client_for_account,
        "compute-optimizer": get_compute_optimizer_client_for_account,
        "cost-optimization-hub": get_cost_optimization_hub_client_for_account,
    }

    if service_name not in service_map:
        raise ValueError(f"不支持的服务: {service_name}")

    return service_map[service_name](account_id)
