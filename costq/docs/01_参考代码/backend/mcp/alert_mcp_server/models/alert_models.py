"""Alert MCP Server Pydantic 模型定义

用于 MCP 工具参数验证
"""

import re

from pydantic import BaseModel, Field, field_validator

from ..constants import CHECK_FREQUENCIES


class CreateAlertParams(BaseModel):
    """创建告警参数"""

    query_description: str = Field(
        ...,
        description="完整的自然语言描述，包含查询逻辑、阈值判断和邮件发送。例如：'每天查询prod-01账号的SP覆盖率，如果低于70%，发邮件给finance@company.com'",
        min_length=10,
        max_length=5000,
    )

    display_name: str | None = Field(
        None, description="告警显示名称，用于UI展示。如果不提供，将自动生成", max_length=200
    )

    user_id: str | None = Field(
        None, description="创建用户的ID（API调用时自动设置）", min_length=1, max_length=36
    )

    org_id: str | None = Field(
        None, description="组织ID（API调用时自动设置，多租户隔离）", min_length=1, max_length=36
    )

    check_frequency: str = Field(
        default="daily",
        description="检查频率：hourly（每小时）、daily（每天）、weekly（每周）、monthly（每月）",
    )

    # ✅ 新增：账号字段
    account_id: str | None = Field(None, description="关联的云账号ID（AWS或GCP）", max_length=36)

    account_type: str | None = Field(None, description="账号类型：aws 或 gcp", max_length=10)

    @field_validator("check_frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        """验证检查频率"""
        if v not in CHECK_FREQUENCIES:
            raise ValueError(f"无效的检查频率。允许的值: {', '.join(CHECK_FREQUENCIES.keys())}")
        return v

    @field_validator("query_description")
    @classmethod
    def validate_query_description(cls, v: str) -> str:
        """验证查询描述，防止恶意内容（XSS）"""
        v = v.strip()

        # 检查危险字符
        dangerous_patterns = [
            r"<script",
            r"javascript:",
            r"on\w+\s*=",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("查询描述包含不允许的内容")

        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        """验证显示名称"""
        if v:
            v = v.strip()
            if re.search(r"[<>]", v):
                raise ValueError("显示名称包含不允许的字符")
        return v


class ListAlertsParams(BaseModel):
    """查询告警列表参数"""

    org_id: str = Field(..., description="组织ID（多租户隔离）", min_length=1, max_length=36)

    user_id: str = Field(
        ..., description="当前用户ID（必需，用于权限验证）", min_length=1, max_length=36
    )

    is_admin: bool = Field(default=False, description="是否是管理员。非管理员只能查看自己的告警")

    status_filter: str | None = Field(
        default="all", description="状态过滤：active（仅启用）、inactive（仅禁用）、all（全部）"
    )

    @field_validator("status_filter")
    @classmethod
    def validate_status(cls, v: str | None) -> str:
        """验证状态过滤"""
        if v and v not in ["active", "inactive", "all"]:
            raise ValueError("无效的状态过滤。允许的值: active, inactive, all")
        return v or "all"


class UpdateAlertParams(BaseModel):
    """更新告警参数"""

    alert_id: str | None = Field(
        None, description="要更新的告警ID（由路由参数提供）", min_length=1, max_length=36
    )

    query_description: str | None = Field(
        None, description="新的自然语言描述", min_length=10, max_length=5000
    )

    display_name: str | None = Field(None, description="新的显示名称", max_length=200)

    check_frequency: str | None = Field(None, description="新的检查频率")

    # ✅ 新增：账号字段
    account_id: str | None = Field(None, description="关联的云账号ID（AWS或GCP）", max_length=36)

    account_type: str | None = Field(None, description="账号类型：aws 或 gcp", max_length=10)

    user_id: str | None = Field(
        None, description="操作用户的ID（由请求上下文提供）", min_length=1, max_length=36
    )

    org_id: str | None = Field(
        None, description="组织ID（由请求上下文提供）", min_length=1, max_length=36
    )

    @field_validator("check_frequency")
    @classmethod
    def validate_frequency(cls, v: str | None) -> str | None:
        """验证检查频率"""
        if v and v not in CHECK_FREQUENCIES:
            raise ValueError(f"无效的检查频率。允许的值: {', '.join(CHECK_FREQUENCIES.keys())}")
        return v


class ToggleAlertParams(BaseModel):
    """启用/禁用告警参数"""

    alert_id: str = Field(..., description="要切换状态的告警ID", min_length=1, max_length=36)

    user_id: str = Field(
        ..., description="操作用户的ID（用于权限验证）", min_length=1, max_length=36
    )

    org_id: str = Field(..., description="组织ID（用于权限验证）", min_length=1, max_length=36)


class DeleteAlertParams(BaseModel):
    """删除告警参数"""

    alert_id: str = Field(..., description="要删除的告警ID", min_length=1, max_length=36)

    user_id: str = Field(
        ..., description="操作用户的ID（用于权限验证）", min_length=1, max_length=36
    )

    org_id: str = Field(..., description="组织ID（用于权限验证）", min_length=1, max_length=36)


class SendEmailParams(BaseModel):
    """发送告警邮件参数（核心工具）"""

    to_emails: list[str] = Field(..., description="收件人邮箱列表", min_length=1, max_length=10)

    subject: str = Field(..., description="邮件主题", min_length=1, max_length=200)

    body_html: str = Field(..., description="HTML格式邮件正文", min_length=1, max_length=50000)

    body_text: str | None = Field(
        None, description="纯文本格式邮件正文（可选，作为HTML的备用）", max_length=50000
    )

    alert_id: str | None = Field(None, description="关联的告警ID（用于记录历史）", max_length=36)

    org_id: str | None = Field(None, description="组织ID（用于记录历史）", max_length=36)

    @field_validator("to_emails")
    @classmethod
    def validate_emails(cls, v: list[str]) -> list[str]:
        """验证邮箱格式"""
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        for email in v:
            if not re.match(email_pattern, email):
                raise ValueError(f"无效的邮箱地址: {email}")

        return v
