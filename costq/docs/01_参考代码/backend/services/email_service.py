"""邮件服务（使用公共SES客户端）

提供统一的邮件发送接口，支持HTML和纯文本格式。

**使用场景：**
- 用户注册邮箱验证
- 添加用户邮箱验证
- 密码重置邮件
- 用户邀请邮件
- 其他非 Agent 场景的邮件发送

**架构说明：**
- 本服务使用公共 SES 客户端（backend.services.aws_ses_client）
- Agent 场景的邮件发送应使用 Send Email MCP
- 两者底层使用相同的 SES 配置和客户端逻辑

**为什么使用公共 SES 客户端：**
- 部署到 AgentCore Runtime 后，MCP 代码不在 FastAPI 容器内
- 公共 SES 客户端确保 EmailService 始终可用
- 避免跨容器依赖问题
"""

from typing import Any


from backend.services.aws_ses_client import get_sender_email

import logging

logger = logging.getLogger(__name__)

# 使用公共 SES 客户端（不再依赖 Alert MCP）
from backend.services.aws_ses_client import send_email as ses_send_email


class EmailService:
    """邮件服务封装层"""

    @staticmethod
    async def send_html_email(
        to_emails: list[str], subject: str, html_body: str, text_body: str | None = None
    ) -> dict[str, Any]:
        """
        发送HTML邮件（复用SES客户端）

        Args:
            to_emails: 收件人邮箱列表
            subject: 邮件主题
            html_body: HTML格式邮件正文
            text_body: 纯文本格式邮件正文（可选）

        Returns:
            Dict[str, Any]: 发送结果
            {
                'success': True/False,
                'message_id': 'ses-message-id',  # 成功时返回
                'to_emails': ['email1@example.com'],
                'error': 'error message'  # 失败时返回
            }
        """
        logger.info(f"📧 发送邮件 - 收件人: {to_emails}, 主题: {subject}")

        try:
            result = await ses_send_email(
                to_emails=to_emails, subject=subject, body_html=html_body, body_text=text_body
            )

            if result.get("success"):
                logger.info(f"✅ 邮件发送成功 - message_id: {result.get('message_id')}")
            else:
                logger.error(f"❌ 邮件发送失败 - error: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"❌ 邮件发送异常: {str(e)}")
            return {"success": False, "error": str(e), "to_emails": to_emails}

    @staticmethod
    def get_sender_email() -> str:
        """获取发件人邮箱"""
        return get_sender_email()


# 全局邮件服务实例
_email_service = EmailService()


def get_email_service() -> EmailService:
    """获取邮件服务实例"""
    return _email_service
