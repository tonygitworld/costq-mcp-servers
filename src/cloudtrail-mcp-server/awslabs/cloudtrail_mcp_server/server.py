# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""awslabs cloudtrail MCP Server implementation."""

import logging

from awslabs.cloudtrail_mcp_server.tools import CloudTrailTools
from mcp.server.fastmcp import FastMCP

from cred_extract_services.context_manager import set_aws_credentials
from cred_extract_services.credential_extractor import extract_aws_credentials
from cred_extract_services.exceptions import (
    AccountNotFoundError,
    AssumeRoleError,
    CredentialDecryptionError,
    CredentialExtractionError,
    DatabaseConnectionError,
)

logger = logging.getLogger(__name__)

# 导出异常类，便于调用方捕获
__all__ = [
    "_setup_account_context",
    "mcp",
    "main",
    "CredentialExtractionError",
    "AccountNotFoundError",
    "CredentialDecryptionError",
    "AssumeRoleError",
    "DatabaseConnectionError",
]


# Create FastMCP server for AgentCore Runtime
# AgentCore requires stateless HTTP servers on 0.0.0.0:8000/mcp
mcp = FastMCP(
    name='awslabs.cloudtrail-mcp-server',
    instructions='Use this MCP server to query AWS CloudTrail events for security investigations, compliance auditing, and operational troubleshooting. Supports event lookup by various attributes (username, event name, resource name, etc.), user activity analysis, API call tracking, and advanced CloudTrail Lake SQL queries for complex analytics. Can search the last 90 days of management events and provides detailed event summaries and activity analysis.',
    dependencies=[
        'boto3',
        'botocore',
        'pydantic',
        'loguru',
    ],
    host="0.0.0.0",
    stateless_http=True
)

# Initialize and register CloudTrail tools
try:
    cloudtrail_tools = CloudTrailTools()
    cloudtrail_tools.register(mcp)
    logger.info("CloudTrail tools registered successfully")
except Exception as e:
    logger.error('Error initializing CloudTrail tools: %s', str(e))
    raise


async def _setup_account_context(
    target_account_id: str,
) -> dict[str, str]:
    """设置 AWS 凭证上下文

    统一入口函数，完成以下操作：
    1. 查询账号信息（自包含数据库查询）
    2. 提取凭证（AKSK 解密 / IAM Role AssumeRole）
    3. 设置环境变量

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

    logger.info("AWS 凭证上下文设置完成: %s", cred_info)
    return cred_info


def main():
    """Run the MCP server with streamable HTTP transport for AgentCore."""
    # AgentCore Runtime expects servers to run with streamable-http transport
    mcp.run(transport="streamable-http")


if __name__ == '__main__':
    main()
