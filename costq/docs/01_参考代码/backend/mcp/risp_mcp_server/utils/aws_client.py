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

"""AWS client management for RISP MCP Server.

This module provides AWS Cost Explorer client management with proper session handling and caching.
Based on the upstream Cost Explorer MCP Server implementation.
"""

import logging
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

from ..constants import SERVICE_NAME_MAPPING

# Configure Loguru logging

# Global client cache
_cost_explorer_client = None


def get_cost_explorer_client():
    """Get Cost Explorer client with proper session management and caching.

    This function replicates the client management approach from the upstream
    Cost Explorer MCP Server to ensure consistency and reliability.

    Returns:
        boto3.client: Configured Cost Explorer client (cached after first call)

    Raises:
        Exception: If client creation fails
    """
    global _cost_explorer_client

    if _cost_explorer_client is None:
        try:
            # Read environment variables dynamically
            # 优先使用MCP专用的AWS配置，然后回退到通用配置
            aws_region = os.environ.get("MCP_AWS_DEFAULT_REGION") or os.environ.get(
                "AWS_REGION", "us-east-1"
            )
            aws_profile = os.environ.get("MCP_AWS_PROFILE") or os.environ.get("AWS_PROFILE")

            logger.info(f"Creating Cost Explorer client for region: {aws_region}")

            if aws_profile:
                logger.info(f"Using AWS profile: {aws_profile}")
                _cost_explorer_client = boto3.Session(
                    profile_name=aws_profile, region_name=aws_region
                ).client("ce")
            else:
                logger.info("Using default AWS credentials from environment")
                # ⭐ 修复：不传参数的 Session() 会从环境变量读取凭证
                # 包括 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
                _cost_explorer_client = boto3.Session().client("ce", region_name=aws_region)

            logger.info("Cost Explorer client created successfully")

        except Exception as e:
            logger.error(f"Error creating Cost Explorer client: {str(e)}", exc_info=True)
            raise

    return _cost_explorer_client


def reset_cost_explorer_client():
    """Reset the cached Cost Explorer client.

    This function can be used to force recreation of the client,
    useful for testing or when credentials change.
    """
    global _cost_explorer_client
    _cost_explorer_client = None
    logger.info("Cost Explorer client cache reset")


def validate_aws_credentials() -> bool:
    """Validate AWS credentials by making a simple API call.

    Returns:
        bool: True if credentials are valid, False otherwise
    """
    try:
        client = get_cost_explorer_client()
        # Make a simple call to validate credentials
        client.get_dimension_values(
            TimePeriod={"Start": "2024-01-01", "End": "2024-01-02"}, Dimension="SERVICE"
        )
        logger.info("AWS credentials validated successfully")
        return True
    except Exception as e:
        logger.error(f"AWS credentials validation failed: {str(e)}", exc_info=True)
        return False


def get_aws_account_id() -> str | None:
    """Get the current AWS account ID.

    Returns:
        Optional[str]: AWS account ID if available, None otherwise
    """
    try:
        sts_client = boto3.client("sts")
        response = sts_client.get_caller_identity()
        account_id = response.get("Account")
        logger.info(f"Current AWS account ID: {account_id}")
        return account_id
    except Exception as e:
        logger.error(f"Failed to get AWS account ID: {str(e)}", exc_info=True)
        return None


def get_aws_region() -> str:
    """Get the current AWS region.

    优先使用MCP专用的AWS区域配置，然后回退到通用配置

    Returns:
        str: AWS region name
    """
    return os.environ.get("MCP_AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION", "us-east-1")


def get_aws_profile() -> str | None:
    """Get the current AWS profile.

    优先使用MCP专用的AWS配置文件，然后回退到通用配置

    Returns:
        Optional[str]: AWS profile name if set, None otherwise
    """
    return os.environ.get("MCP_AWS_PROFILE") or os.environ.get("AWS_PROFILE")


async def call_aws_api_with_retry(
    client, api_name: str, params: dict[str, Any], max_retries: int = 2
) -> dict[str, Any]:
    """调用AWS API并实现智能重试

    Args:
        client: AWS客户端实例
        api_name: API方法名称
        params: API调用参数
        max_retries: 最大重试次数

    Returns:
        API响应结果

    Raises:
        Exception: 重试失败后抛出最后一次的异常
    """
    from .validators import prepare_api_params_for_ri_apis

    # 预防性处理：对于不支持MatchOptions的API，提前移除MatchOptions
    params = prepare_api_params_for_ri_apis(api_name, params)

    for attempt in range(max_retries + 1):
        try:
            # 调用API
            method = getattr(client, api_name)
            logger.info(f"调用AWS API: {api_name} (尝试 {attempt + 1}/{max_retries + 1})")
            return method(**params)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = str(e)

            logger.warning(f"AWS API调用失败: {error_msg}")

            # 注意：MatchOptions错误已通过预防性处理避免，不再需要重试处理

            # 处理服务名称错误
            if "Invalid Service" in error_msg and attempt < max_retries:
                logger.warning("检测到服务名称错误，尝试修复服务名称并重试")

                # 尝试修复服务名称
                if "Service" in params:
                    original_service = params["Service"]
                    if original_service in SERVICE_NAME_MAPPING:
                        params["Service"] = SERVICE_NAME_MAPPING[original_service]
                        logger.info(f"服务名称已修复: {original_service} -> {params['Service']}")
                        continue
                    else:
                        logger.warning(f"无法修复服务名称: {original_service}")

            # 处理限流错误
            elif error_code == "ThrottlingException" and attempt < max_retries:
                import asyncio

                wait_time = (attempt + 1) * 2  # 指数退避
                logger.warning(f"检测到限流，等待 {wait_time} 秒后重试")
                await asyncio.sleep(wait_time)
                continue

            # 其他错误或最后一次尝试失败，抛出异常
            if attempt == max_retries:
                logger.error(f"AWS API调用最终失败: {error_msg}")
            raise

        except Exception as e:
            # 非ClientError异常，直接抛出
            logger.error(f"AWS API调用出现非预期错误: {str(e)}", exc_info=True)
            raise


def map_service_name(service: str) -> str:
    """将简化的服务名称映射为AWS API要求的完整名称

    Args:
        service: 简化的服务名称

    Returns:
        AWS API要求的完整服务名称
    """
    if service in SERVICE_NAME_MAPPING:
        mapped_name = SERVICE_NAME_MAPPING[service]
        logger.info(f"服务名称映射: {service} -> {mapped_name}")
        return mapped_name

    # 如果已经是完整名称，直接返回
    logger.info(f"服务名称无需映射: {service}")
    return service


def validate_service_name(service: str) -> bool:
    """验证服务名称是否有效

    Args:
        service: 服务名称

    Returns:
        是否为有效的服务名称
    """
    from ..constants import VALID_RI_SERVICES, VALID_RI_SERVICES_SIMPLE

    # 检查是否为有效的完整名称或简化名称
    is_valid = service in VALID_RI_SERVICES or service in VALID_RI_SERVICES_SIMPLE

    if not is_valid:
        logger.warning(f"无效的服务名称: {service}")
        logger.info(f"有效的服务名称: {VALID_RI_SERVICES_SIMPLE}")

    return is_valid
