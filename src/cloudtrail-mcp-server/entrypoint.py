"""凭证提取服务主入口

提供统一的凭证提取和上下文设置接口。
自包含模块，不依赖项目代码。

使用示例：
    # 1. 作为 Python 模块使用
    from entrypoint import setup_aws_credentials_context

    # 设置凭证上下文
    cred_info = await setup_aws_credentials_context("account-uuid-123")
    print(f"凭证已设置: {cred_info}")

    # 2. 作为 MCP Server 启动
    python entrypoint.py
"""

import asyncio
import logging
import os
import sys

from cred_extract_services.context_manager import set_aws_credentials
from cred_extract_services.credential_extractor import extract_aws_credentials
from cred_extract_services.exceptions import (
    AccountNotFoundError,
    AssumeRoleError,
    CredentialDecryptionError,
    CredentialExtractionError,
    DatabaseConnectionError,
)

# 避免循环导入：延迟导入 server（仅在 main() 函数中需要）
# from awslabs.billing_cost_management_mcp_server.server import mcp, setup

logger = logging.getLogger(__name__)

# 导出异常类，便于调用方捕获
__all__ = [
    "_setup_account_context",
    "CredentialExtractionError",
    "AccountNotFoundError",
    "CredentialDecryptionError",
    "AssumeRoleError",
    "DatabaseConnectionError",
]


async def _setup_account_context(
    target_account_id: str,
) -> dict[str, str]:
    """设置 AWS 凭证上下文

    统一入口函数，完成以下操作：
    1. 查询账号信息（自包含数据库查询）
    2. 提取凭证（AKSK 解密 / IAM Role AssumeRole）
    3. 设置 ContextVar

    前置条件：
        - target_account_id 已通过权限验证
        - 调用方有权访问该账号

    Args:
        target_account_id: AWS 账号 ID（数据库主键）

    Returns:
        凭证信息字典（用于日志记录，已脱敏）
        {
            "account_id": "123456789012",
            "account_alias": "production",
            "auth_type": "iam_role",
            "region": "us-east-1"
        }

    Raises:
        AccountNotFoundError: 账号不存在
        CredentialDecryptionError: 凭证解密失败
        AssumeRoleError: AssumeRole 失败
        DatabaseConnectionError: 数据库连接失败

    环境变量：
        DATABASE_URL: 数据库连接 URL（可选，与 RDS_SECRET_NAME 二选一）
        RDS_SECRET_NAME: AWS Secrets Manager 密钥名称
        ENCRYPTION_KEY: Fernet 加密密钥（Base64 编码）
        AWS_REGION: AWS 区域（默认 us-east-1）
    """
    # ✅ 不记录 AccountId（敏感信息）
    logger.info("开始设置 AWS 凭证上下文")

    # 1. 提取凭证
    credentials = await extract_aws_credentials(target_account_id)

    # 2. 设置环境变量
    set_aws_credentials(
        access_key_id=credentials["access_key_id"],
        secret_access_key=credentials["secret_access_key"],
        session_token=credentials.get("session_token"),
        region=credentials["region"],
    )

    # 3. 返回脱敏信息（用于日志）
    cred_info = {
        "account_id": credentials["account_id"],
        "account_alias": credentials.get("alias", "Unknown"),
        "auth_type": credentials["auth_type"],
        "region": credentials["region"],
    }

    logger.info(f"✅ AWS 凭证上下文设置完成: {cred_info}")
    return cred_info


def main():
    """启动 MCP Server（支持 stdio 和 streamable-http 传输）

    环境变量配置：
        FASTMCP_TRANSPORT: 传输类型，默认 'streamable-http'
            - 'stdio': 标准输入输出传输（本地测试）
            - 'streamable-http': HTTP 传输（AgentCore Runtime）
        FASTMCP_HOST: 服务器地址，默认 '0.0.0.0'
        FASTMCP_PORT: 服务器端口，默认 8000
        FASTMCP_STATELESS_HTTP: 是否启用无状态 HTTP，默认 'true'

    AgentCore Runtime 配置：
        - Runtime 期望 MCP server 运行在 0.0.0.0:8000/mcp
        - 使用 streamable-http 传输协议
        - 启用 stateless_http 模式

    使用示例：
        # 启动 streamable-http server（生产环境）
        python entrypoint.py

        # 启动 stdio server（本地测试）
        FASTMCP_TRANSPORT=stdio python entrypoint.py
    """

    # 延迟导入，避免循环依赖
    from awslabs.cloudtrail_mcp_server.server import mcp

    # 尝试导入 setup 函数（有些 MCP Server 可能没有）
    try:
        from awslabs.cloudtrail_mcp_server.server import setup
        has_setup = True
    except ImportError:
        has_setup = False
        logger.info("ℹ️  MCP Server 没有 setup 函数，直接启动")

    # 从环境变量读取传输配置
    transport = os.environ.get("FASTMCP_TRANSPORT", "streamable-http")
    host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
    port = int(os.environ.get("FASTMCP_PORT", "8000"))
    stateless = os.environ.get("FASTMCP_STATELESS_HTTP", "true").lower() == "true"

    logger.info(f"🚀 启动 MCP Server: transport={transport}, host={host}, port={port}")

    # 如果有 setup 函数，先运行初始化
    if has_setup:
        logger.info("🔧 运行 setup 初始化...")
        asyncio.run(setup())

    # 根据传输类型运行 server
    if transport == "stdio":
        logger.info("📡 使用 stdio 传输（本地测试模式）")
        mcp.run(transport=transport)
    else:
        logger.info(f"📡 使用 {transport} 传输: http://{host}:{port}/mcp")
        logger.info(f"   Stateless HTTP: {stateless}")
        mcp.run(transport=transport, host=host, port=port, stateless_http=stateless)


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    main()
