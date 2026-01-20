"""AWS SES 客户端管理

提供 AWS SES 邮件发送功能，支持重试机制和错误处理
"""

import logging
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Configure Loguru logging

# SES 配置常量
SES_REGION = os.getenv("SES_REGION", "ap-northeast-1")
SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "no_reply@costq-mail.cloudminos.jp")
SES_CONFIGURATION_SET = os.getenv("SES_CONFIGURATION_SET", "")  # 可选

# Global SES client cache
_ses_client = None


def get_ses_client():
    """获取 SES 客户端（使用平台账号 3532 的 IAM Role）

    权限来源：
    - 本地开发：使用 AWS_PROFILE=3532（通过环境变量传递）
    - AgentCore Runtime：使用 Runtime 关联的 IAM Role（不使用目标账号凭证）

    ⚠️ 重要：Send Email 是平台级服务，必须使用平台账号（3532）的权限
    - 不使用环境变量中的 AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY
    - 这些变量是目标账号（如 6350）的凭证，用于 Cost Explorer 等 MCP
    - SES 必须使用 3532 账号的 IAM Role 或 Profile

    Returns:
        boto3.client: 配置好的 SES 客户端

    Raises:
        Exception: 如果客户端创建失败
    """
    global _ses_client

    if _ses_client is None:
        try:
            # 判断是否在 Docker 容器/Runtime 环境中
            is_container = os.environ.get("DOCKER_CONTAINER") == "1"
            platform_profile = os.environ.get("PLATFORM_AWS_PROFILE", "3532")

            logger.info(
                f"📧 初始化 SES 客户端（平台账号）- "
                f"Region: {SES_REGION}, "
                f"Is Container: {is_container}, "
                f"Platform Profile: {platform_profile if not is_container else 'N/A (using IAM Role)'}"
            )

            # 创建独立的 Session，不使用环境变量中的目标账号凭证
            # 本地开发：使用 PLATFORM_AWS_PROFILE（如 "3532"）
            # Runtime/Container：不设置 profile，使用 IAM Role
            if is_container:
                # Runtime 环境：使用 IAM Role
                # 关键：必须临时清除环境变量中的目标账号凭证，否则 boto3 会优先使用环境变量
                import copy

                original_env = copy.copy(os.environ)

                # 临时删除目标账号的凭证
                for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]:
                    os.environ.pop(key, None)

                try:
                    # 现在 boto3 会自动使用 Runtime 的 IAM Role
                    session = boto3.Session()
                    logger.info("✅ 使用 Runtime IAM Role（已清除环境变量中的目标账号凭证）")
                finally:
                    # 恢复环境变量（其他 MCP 可能需要）
                    for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]:
                        if key in original_env:
                            os.environ[key] = original_env[key]
            else:
                # 本地环境：使用平台账号的 Profile
                session = boto3.Session(profile_name=platform_profile)
                logger.info(f"✅ 使用平台 Profile: {platform_profile}")

            # 创建 SES 客户端
            _ses_client = session.client("ses", region_name=SES_REGION)

            logger.info("✅ SES 客户端创建成功")

        except Exception as e:
            logger.error(f"❌ 创建 SES 客户端失败: {str(e)}", exc_info=True)
            raise

    return _ses_client


async def send_email(
    to_emails: list[str],
    subject: str,
    body_html: str,
    body_text: str | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """发送邮件（带重试机制）

    Args:
        to_emails: 收件人邮箱列表
        subject: 邮件主题
        body_html: HTML 格式邮件正文
        body_text: 纯文本格式邮件正文（可选）
        max_retries: 最大重试次数

    Returns:
        Dict[str, Any]: 发送结果
        {
            'success': True/False,
            'message_id': 'ses-message-id',  # 成功时返回
            'to_emails': ['user@example.com'],
            'error': 'error message'  # 失败时返回
        }

    Raises:
        Exception: 如果所有重试都失败
    """
    client = get_ses_client()

    # 构建邮件内容
    message = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {"Html": {"Data": body_html, "Charset": "UTF-8"}},
    }

    # 添加纯文本版本（如果提供）
    if body_text:
        message["Body"]["Text"] = {"Data": body_text, "Charset": "UTF-8"}

    # 重试逻辑
    last_error = None
    for attempt in range(max_retries):
        try:
            logger.info(
                f"发送邮件 (尝试 {attempt + 1}/{max_retries}): to={to_emails}, subject={subject}"
            )

            # 构建请求参数
            send_params = {
                "Source": SES_SENDER_EMAIL,
                "Destination": {"ToAddresses": to_emails},
                "Message": message,
            }

            # 添加配置集（如果配置）
            if SES_CONFIGURATION_SET:
                send_params["ConfigurationSetName"] = SES_CONFIGURATION_SET

            # 发送邮件
            response = client.send_email(**send_params)

            message_id = response["MessageId"]
            logger.info(f"✅ 邮件发送成功: message_id={message_id}")

            return {"success": True, "message_id": message_id, "to_emails": to_emails}

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            last_error = f"{error_code}: {error_message}"

            logger.warning(f"邮件发送失败 (尝试 {attempt + 1}/{max_retries}): {last_error}")

            # 某些错误不需要重试
            if error_code in [
                "MessageRejected",
                "MailFromDomainNotVerified",
                "ConfigurationSetDoesNotExist",
            ]:
                logger.error(f"不可重试的错误: {error_code}")
                break

        except Exception as e:
            last_error = str(e)
            logger.warning(f"邮件发送失败 (尝试 {attempt + 1}/{max_retries}): {last_error}")

    # 所有重试都失败
    logger.error(f"❌ 邮件发送失败（已重试 {max_retries} 次）: {last_error}")
    return {"success": False, "error": last_error, "to_emails": to_emails}
