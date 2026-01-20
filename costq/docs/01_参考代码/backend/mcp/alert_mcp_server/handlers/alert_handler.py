"""Alert MCP Server Handler Functions

提供5个核心MCP工具的处理函数
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context

from backend.services.audit_logger import get_audit_logger

from ..constants import ERROR_MESSAGES, SUCCESS_MESSAGES
from ..models.alert_models import (
    CreateAlertParams,
    DeleteAlertParams,
    ListAlertsParams,
    ToggleAlertParams,
    UpdateAlertParams,
)
from ..utils.db_helper import AlertDBHelper, get_db_session

# Configure Loguru logging


async def create_alert(context: Context, params: CreateAlertParams) -> dict[str, Any]:
    """创建告警配置

    **使用场景：**
    - 用户想要创建新的成本告警
    - 需要监控特定的AWS成本指标
    - 设置自动化的成本通知

    **功能说明：**
    - 使用纯自然语言描述告警规则
    - 支持多种检查频率（每小时/每天/每周/每月）
    - 自动进行多租户隔离
    - 检查告警数量限制

    Args:
        context: MCP上下文
        params: 创建告警参数

    Returns:
        Dict[str, Any]: 创建结果
        {
            'success': True/False,
            'alert_id': 'uuid',  # 成功时返回
            'message': '告警创建成功',
            'error': 'error message'  # 失败时返回
        }
    """
    try:
        logger.info(f"创建告警: user_id={params.user_id}, org_id={params.org_id}")

        with get_db_session() as db:
            # 生成显示名称（如果未提供）
            display_name = params.display_name or f"告警-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            # 创建告警
            alert = AlertDBHelper.create_alert(
                db=db,
                org_id=params.org_id,
                user_id=params.user_id,
                query_description=params.query_description,
                display_name=display_name,
                check_frequency=params.check_frequency,
                account_id=params.account_id,
                account_type=params.account_type,
            )

            # 记录审计日志
            audit_logger = get_audit_logger()
            audit_logger.log_alert_create(
                user_id=params.user_id,
                org_id=params.org_id,
                alert_id=alert.id,
                display_name=alert.display_name,
                query_description=params.query_description,
            )

            return {
                "success": True,
                "alert_id": alert.id,
                "display_name": alert.display_name,
                "message": SUCCESS_MESSAGES["ALERT_CREATED"],
            }

    except ValueError as e:
        logger.warning(f"创建告警失败（参数错误）: {str(e)}")
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"创建告警失败: {str(e)}", exc_info=True)
        return {"success": False, "error": f"{ERROR_MESSAGES['DATABASE_ERROR']}: {str(e)}"}


async def list_alerts(context: Context, params: ListAlertsParams) -> dict[str, Any]:
    """查询告警列表

    **使用场景：**
    - 查看所有告警配置
    - 查看特定用户的告警
    - 过滤启用/禁用的告警

    **功能说明：**
    - 所有用户（包括管理员）只能查看自己创建的告警
    - 支持按状态过滤（active/inactive/all）
    - 自动进行多租户隔离
    - 按创建时间倒序排列

    Args:
        context: MCP上下文
        params: 查询参数

    Returns:
        Dict[str, Any]: 查询结果
        {
            'success': True/False,
            'alerts': [...],  # 告警列表
            'count': 10,
            'error': 'error message'  # 失败时返回
        }
    """
    try:
        logger.info(
            f"查询告警列表: org_id={params.org_id}, user_id={params.user_id}, is_admin={params.is_admin}, status={params.status_filter}"
        )

        with get_db_session() as db:
            alerts = AlertDBHelper.list_alerts(
                db=db,
                org_id=params.org_id,
                user_id=params.user_id,
                is_admin=params.is_admin,
                status_filter=params.status_filter,
            )

            # 转换为字典列表（使用 to_dict() 方法确保字段映射正确）
            # 强制加载关联的用户对象
            for alert in alerts:
                if alert.user:
                    _ = alert.user.username

            alert_list = [alert.to_dict() for alert in alerts]

            return {"success": True, "alerts": alert_list, "count": len(alert_list)}

    except Exception as e:
        logger.error(f"查询告警列表失败: {str(e)}", exc_info=True)
        return {"success": False, "error": f"{ERROR_MESSAGES['DATABASE_ERROR']}: {str(e)}"}


async def update_alert(context: Context, params: UpdateAlertParams) -> dict[str, Any]:
    """更新告警配置

    **使用场景：**
    - 修改告警的自然语言描述
    - 更改告警显示名称
    - 调整检查频率

    **功能说明：**
    - 只更新提供的字段
    - 自动验证用户权限
    - 自动更新时间戳

    Args:
        context: MCP上下文
        params: 更新参数

    Returns:
        Dict[str, Any]: 更新结果
    """
    try:
        logger.info(f"更新告警: alert_id={params.alert_id}, user_id={params.user_id}")

        with get_db_session() as db:
            alert = AlertDBHelper.update_alert(
                db=db,
                alert_id=params.alert_id,
                org_id=params.org_id,
                user_id=params.user_id,
                query_description=params.query_description,
                display_name=params.display_name,
                check_frequency=params.check_frequency,
                account_id=params.account_id,
                account_type=params.account_type,
            )

            if not alert:
                return {"success": False, "error": ERROR_MESSAGES["ALERT_NOT_FOUND"]}

            # 记录审计日志
            audit_logger = get_audit_logger()
            changes = {}
            if params.query_description:
                changes["query_description"] = params.query_description
            if params.display_name:
                changes["display_name"] = params.display_name
            if params.check_frequency:
                changes["check_frequency"] = params.check_frequency

            audit_logger.log_alert_update(
                user_id=params.user_id,
                org_id=params.org_id,
                alert_id=alert.id,
                display_name=alert.display_name,
                changes=changes if changes else None,
            )

            return {
                "success": True,
                "alert_id": alert.id,
                "message": SUCCESS_MESSAGES["ALERT_UPDATED"],
            }

    except Exception as e:
        logger.error(f"更新告警失败: {str(e)}", exc_info=True)
        return {"success": False, "error": f"{ERROR_MESSAGES['DATABASE_ERROR']}: {str(e)}"}


async def toggle_alert(context: Context, params: ToggleAlertParams) -> dict[str, Any]:
    """启用/禁用告警

    **使用场景：**
    - 临时禁用告警
    - 重新启用告警
    - 快速切换告警状态

    **功能说明：**
    - 自动切换is_active状态
    - 自动验证用户权限
    - 返回新的状态

    Args:
        context: MCP上下文
        params: 切换参数

    Returns:
        Dict[str, Any]: 切换结果
    """
    try:
        logger.info(f"切换告警状态: alert_id={params.alert_id}, user_id={params.user_id}")

        with get_db_session() as db:
            alert = AlertDBHelper.toggle_alert(
                db=db, alert_id=params.alert_id, org_id=params.org_id, user_id=params.user_id
            )

            if not alert:
                return {"success": False, "error": ERROR_MESSAGES["ALERT_NOT_FOUND"]}

            # 记录审计日志
            audit_logger = get_audit_logger()
            audit_logger.log_alert_toggle(
                user_id=params.user_id,
                org_id=params.org_id,
                alert_id=alert.id,
                is_active=alert.is_active,
                display_name=alert.display_name,
            )

            status_text = "已启用" if alert.is_active else "已禁用"

            return {
                "success": True,
                "alert_id": alert.id,
                "is_active": alert.is_active,
                "message": f"{SUCCESS_MESSAGES['ALERT_TOGGLED']} - {status_text}",
            }

    except Exception as e:
        logger.error(f"切换告警状态失败: {str(e)}", exc_info=True)
        return {"success": False, "error": f"{ERROR_MESSAGES['DATABASE_ERROR']}: {str(e)}"}


async def delete_alert(context: Context, params: DeleteAlertParams) -> dict[str, Any]:
    """删除告警配置

    **使用场景：**
    - 删除不再需要的告警
    - 清理过期的告警配置

    **功能说明：**
    - 自动验证用户权限
    - 级联删除关联的历史记录

    Args:
        context: MCP上下文
        params: 删除参数

    Returns:
        Dict[str, Any]: 删除结果
    """
    try:
        logger.info(f"删除告警: alert_id={params.alert_id}, user_id={params.user_id}")

        with get_db_session() as db:
            # 在删除前获取告警信息用于审计日志
            from backend.models.monitoring import MonitoringConfig

            alert = (
                db.query(MonitoringConfig)
                .filter(
                    MonitoringConfig.id == params.alert_id, MonitoringConfig.org_id == params.org_id
                )
                .first()
            )

            if not alert:
                return {"success": False, "error": ERROR_MESSAGES["ALERT_NOT_FOUND"]}

            # 保存告警信息用于审计日志
            alert_info = {
                "display_name": alert.display_name,
                "query_description": alert.query_description,
            }

            success = AlertDBHelper.delete_alert(
                db=db, alert_id=params.alert_id, org_id=params.org_id, user_id=params.user_id
            )

            if not success:
                return {"success": False, "error": ERROR_MESSAGES["ALERT_NOT_FOUND"]}

            # 记录审计日志
            audit_logger = get_audit_logger()
            audit_logger.log_alert_delete(
                user_id=params.user_id,
                org_id=params.org_id,
                alert_id=params.alert_id,
                display_name=alert_info.get("display_name"),
                query_description=alert_info.get("query_description"),
            )

            return {
                "success": True,
                "alert_id": params.alert_id,
                "message": SUCCESS_MESSAGES["ALERT_DELETED"],
            }

    except Exception as e:
        logger.error(f"删除告警失败: {str(e)}", exc_info=True)
        return {"success": False, "error": f"{ERROR_MESSAGES['DATABASE_ERROR']}: {str(e)}"}
