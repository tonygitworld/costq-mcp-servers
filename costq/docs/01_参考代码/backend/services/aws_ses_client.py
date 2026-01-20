"""AWS SES 客户端（公共模块）

提供 AWS SES 邮件发送功能，供以下场景使用：
1. EmailService（用户注册、验证、邀请等非 Agent 场景）
2. 其他需要直接发送邮件的非 Agent 场景

注意：
- Agent 场景应使用 Send Email MCP（通过 MCP 工具调用）
- 本模块专为非 Agent 场景设计（FastAPI 直接调用）
- 与 Send Email MCP 使用相同的 SES 配置和客户端逻辑

设计原则：
- 无业务依赖（纯邮件发送功能）
- 完整的错误处理
- 单例模式客户端（性能优化）
- 环境变量配置（灵活性）
"""

import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

import logging

logger = logging.getLogger(__name__)

# ============ SES 配置常量 ============
SES_REGION = os.getenv("SES_REGION", "ap-northeast-1")
SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "no_reply@costq-mail.cloudminos.jp")
SES_CONFIGURATION_SET = os.getenv("SES_CONFIGURATION_SET", "")  # 可选

# ============ 全局 SES 客户端缓存 ============
_ses_client = None


def get_ses_client():
    """获取或创建 SES 客户端（单例模式）

    使用全局变量缓存客户端，避免重复创建。
    线程安全性：boto3 客户端本身是线程安全的。

    Returns:
        boto3.client: SES 客户端实例
    """
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses", region_name=SES_REGION)
        logger.info(f"✅ Created SES client for region: {SES_REGION}")
    return _ses_client


async def send_email(
    to_emails: list[str],
    subject: str,
    body_html: str | None = None,
    body_text: str | None = None,
    from_email: str | None = None,
) -> dict[str, Any]:
    """发送邮件（支持HTML和纯文本格式）

    参数说明：
    - to_emails: 收件人邮箱列表（必需）
    - subject: 邮件主题（必需）
    - body_html: HTML格式邮件正文（可选，推荐）
    - body_text: 纯文本格式邮件正文（可选）
    - from_email: 发件人邮箱（可选，默认使用 SES_SENDER_EMAIL）

    注意：
    - body_html 和 body_text 至少提供一个
    - 优先使用 body_html（更丰富的格式）
    - from_email 必须在 AWS SES 中验证过

    返回值：
    {
        'success': True/False,
        'message_id': 'ses-message-id',  # 成功时返回
        'to_emails': ['email@example.com'],
        'error': 'error message'  # 失败时返回
    }

    示例：
    >>> result = await send_email(
    ...     to_emails=['user@example.com'],
    ...     subject='欢迎注册 CostQ',
    ...     body_html='<h1>欢迎！</h1><p>您的验证码是：123456</p>',
    ...     body_text='欢迎！您的验证码是：123456'
    ... )
    >>> if result['success']:
    ...     print(f"邮件发送成功: {result['message_id']}")
    """
    # ============ 参数验证 ============
    if not from_email:
        from_email = SES_SENDER_EMAIL

    if not body_html and not body_text:
        logger.error("❌ 邮件正文为空: body_html 和 body_text 都未提供")
        return {
            "success": False,
            "error": "必须提供 body_html 或 body_text 之一",
            "to_emails": to_emails,
        }

    if not to_emails:
        logger.error("❌ 收件人列表为空")
        return {"success": False, "error": "收件人列表不能为空", "to_emails": []}

    # ============ 发送邮件 ============
    try:
        ses_client = get_ses_client()

        # 构建邮件体
        body = {}
        if body_html:
            body["Html"] = {"Data": body_html, "Charset": "UTF-8"}
        if body_text:
            body["Text"] = {"Data": body_text, "Charset": "UTF-8"}

        # 构建发送参数
        send_params = {
            "Source": from_email,
            "Destination": {"ToAddresses": to_emails},
            "Message": {"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": body},
        }

        # 添加配置集（如果配置了）
        if SES_CONFIGURATION_SET:
            send_params["ConfigurationSetName"] = SES_CONFIGURATION_SET

        # 发送邮件
        logger.info(f"📧 发送邮件 - 发件人: {from_email}, 收件人: {to_emails}, 主题: {subject}")

        response = ses_client.send_email(**send_params)

        message_id = response["MessageId"]
        logger.info(f"✅ 邮件发送成功 - MessageId: {message_id}")

        return {"success": True, "message_id": message_id, "to_emails": to_emails}

    except ClientError as e:
        # AWS SES 客户端错误
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        logger.error(f"❌ SES ClientError: {error_code} - {error_message} | 收件人: {to_emails}")

        return {"success": False, "error": f"{error_code}: {error_message}", "to_emails": to_emails}

    except Exception as e:
        # 其他未预期的错误
        logger.error(f"❌ 邮件发送异常: {str(e)} | 收件人: {to_emails}", exc_info=True)

        return {"success": False, "error": str(e), "to_emails": to_emails}


# ============ 辅助函数 ============


def get_sender_email() -> str:
    """获取当前配置的发件人邮箱

    Returns:
        str: 发件人邮箱地址
    """
    return SES_SENDER_EMAIL


def get_ses_region() -> str:
    """获取当前配置的 SES 区域

    Returns:
        str: AWS 区域代码
    """
    return SES_REGION


# ============ 模块导出 ============

__all__ = [
    "send_email",
    "get_ses_client",
    "get_sender_email",
    "get_ses_region",
    "SES_REGION",
    "SES_SENDER_EMAIL",
    "SES_CONFIGURATION_SET",
]
