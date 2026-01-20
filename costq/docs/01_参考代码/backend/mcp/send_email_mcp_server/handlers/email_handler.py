"""邮件发送处理器

提供邮件发送的核心实现，包括参数验证和错误处理。
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

from ..utils.ses_client import send_email as ses_send_email


async def send_email(
    to_emails: list[str], subject: str, body_html: str = "", body_text: str = ""
) -> dict[str, Any]:
    """发送邮件（核心实现）

    功能：
        - 使用 AWS SES 发送邮件
        - 支持 HTML 和纯文本格式
        - 自动重试机制（最多3次）
        - 详细的错误日志

    参数验证：
        - to_emails 不能为空
        - subject 不能为空
        - body_html 或 body_text 至少提供一个

    Args:
        to_emails: 收件人邮箱列表
        subject: 邮件主题
        body_html: HTML邮件正文（可选）
        body_text: 纯文本邮件正文（可选）

    Returns:
        Dict[str, Any]: 发送结果
        {
            'success': True/False,
            'message_id': 'ses-message-id',  # 成功时返回
            'to_emails': ['user@example.com'],
            'error': 'error message'  # 失败时返回
        }

    Raises:
        ValueError: 参数验证失败

    Examples:
        >>> result = await send_email(
        ...     to_emails=["user@example.com"],
        ...     subject="测试邮件",
        ...     body_html="<h1>测试</h1>",
        ...     body_text="测试"
        ... )
        >>> assert result['success'] == True
    """
    # 参数验证
    if not to_emails:
        raise ValueError("收件人列表不能为空")

    if not subject:
        raise ValueError("邮件主题不能为空")

    if not body_html and not body_text:
        raise ValueError("邮件正文不能为空（HTML或纯文本至少提供一个）")

    logger.info(f"📧 发送邮件 - 收件人: {to_emails}, 主题: {subject}")

    try:
        # 调用 SES 发送
        result = await ses_send_email(
            to_emails=to_emails,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            max_retries=3,
        )

        if result.get("success"):
            logger.info(f"✅ 邮件发送成功 - message_id: {result.get('message_id')}")
        else:
            logger.error(f"❌ 邮件发送失败 - error: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"❌ 邮件发送异常: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "to_emails": to_emails}
