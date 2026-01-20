"""告警管理 API - Alert MCP Server REST 端点

提供完整的告警配置管理功能，支持：
- 创建、查询、更新、删除告警
- 启用/禁用告警
- 发送测试邮件
- 查询告警历史

权限控制：
- 普通用户：只能操作自己的告警
- 管理员：可以操作组织内所有告警
"""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from mcp.server.fastmcp import Context
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db

import logging

logger = logging.getLogger(__name__)
from ..mcp.alert_mcp_server.handlers.alert_handler import (
    create_alert,
    delete_alert,
    list_alerts,
    toggle_alert,
    update_alert,
)
from ..mcp.alert_mcp_server.models.alert_models import (
    CreateAlertParams,
    DeleteAlertParams,
    ListAlertsParams,
    ToggleAlertParams,
    UpdateAlertParams,
)
from ..mcp.alert_mcp_server.utils.db_helper import get_db_session
from ..models.monitoring import MonitoringConfig  # 使用全局的数据库模型
from ..utils.auth import get_current_admin_user, get_current_user

router = APIRouter(prefix="/api/alerts", tags=["告警管理"])


# ========== 请求体模型 ==========


class SendTestEmailRequest(BaseModel):
    """发送测试邮件请求体"""

    account_id: str | None = None


# ========== 辅助函数 ==========


def create_mock_context() -> Context:
    """创建模拟的 MCP Context 对象（用于 API 调用）"""
    # FastMCP Context 只在 MCP 工具调用时需要，REST API 不需要
    # 这里返回 None，handler 函数会处理
    return None


async def check_alert_permission(
    alert_id: str,
    current_user: dict,
    db: Session,  # ✅ 直接接收 db session 参数
    require_admin: bool = False,
) -> dict:
    """检查用户是否有权限访问告警

    Args:
        alert_id: 告警 ID
        current_user: 当前用户
        db: 数据库 Session（从 FastAPI 依赖注入传入）
        require_admin: 是否要求管理员权限

    Returns:
        dict: 告警对象的字典表示

    Raises:
        HTTPException: 权限不足或告警不存在
    """
    from sqlalchemy.orm import joinedload

    # ✅ 直接使用传入的 db session，不再创建新的上下文管理器
    # 关联加载用户信息，以便获取 created_by_username
    alert = (
        db.query(MonitoringConfig)
        .options(joinedload(MonitoringConfig.user))
        .filter(MonitoringConfig.id == alert_id)
        .first()
    )

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"告警不存在: {alert_id}")

    # 多租户隔离检查（UUID类型转换）
    if str(alert.org_id) != str(current_user["org_id"]):
        logger.warning(
            f"⚠️  尝试访问其他组织的告警 - "
            f"User Org: {current_user['org_id']}, Alert Org: {alert.org_id}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该告警")

    # 权限检查
    is_admin = current_user["role"] == "admin"

    if require_admin and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")

    # 普通用户只能访问自己的告警（UUID类型转换）
    if not is_admin and str(alert.user_id) != str(current_user["id"]):
        logger.warning(
            f"⚠️  普通用户尝试访问其他用户的告警 - "
            f"User: {current_user['id']}, Alert Owner: {alert.user_id}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该告警")

    # 强制加载所有属性，避免延迟加载
    # 访问所有基本属性以确保它们被加载到内存
    _ = (
        alert.id,
        alert.org_id,
        alert.user_id,
        alert.query_description,
        alert.display_name,
        alert.is_active,
        alert.check_frequency,
        alert.created_at,
        alert.updated_at,
        alert.last_checked_at,
        alert.account_id,
        alert.account_type,
    )

    # 访问关联的用户对象，确保被加载
    if alert.user:
        _ = alert.user.username

    # 在 Session 还活跃时转换为字典
    return alert.to_dict()


# ========== API 端点 ==========


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_alert_endpoint(
    params: CreateAlertParams, current_user: dict = Depends(get_current_user)
):
    """创建新告警

    **权限**: 所有登录用户

    **说明**:
    - 告警将属于当前用户和其组织
    - 自动设置 user_id 和 org_id
    """
    logger.info(f"📝 创建告警 - User: {current_user['username']}, Org: {current_user['org_id']}")

    # 设置用户和组织信息
    params.user_id = current_user["id"]
    params.org_id = current_user["org_id"]

    try:
        result = await create_alert(create_mock_context(), params)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "创建告警失败")
            )

        # 查询完整的告警对象
        alert_id = result["alert_id"]
        with get_db_session() as db:
            alert = db.query(MonitoringConfig).filter(MonitoringConfig.id == alert_id).first()

            if not alert:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="告警创建成功但无法查询",
                )

            # 强制加载所有属性
            _ = (
                alert.id,
                alert.org_id,
                alert.user_id,
                alert.query_description,
                alert.display_name,
                alert.is_active,
                alert.check_frequency,
                alert.created_at,
                alert.updated_at,
                alert.last_checked_at,
            )

            # 在 Session 还活跃时转换为字典
            alert_dict = alert.to_dict()

        logger.info(f"✅ 告警创建成功 - ID: {alert_id}")

        # 返回包含完整告警对象的响应
        return {
            "success": True,
            "alert_id": alert_id,
            "alert": alert_dict,
            "message": result.get("message", "告警创建成功"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 创建告警失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建告警失败: {str(e)}"
        )


@router.get("/")
async def list_alerts_endpoint(
    status_filter: str = "all", current_user: dict = Depends(get_current_user)
):
    """查询告警列表

    **权限**: 所有登录用户

    **说明**:
    - 所有用户（包括管理员）只能查看自己创建的告警
    - 确保数据隔离和隐私保护

    **参数**:
    - status_filter: 状态过滤 (all/active/inactive)
    """
    logger.info(
        f"📋 查询告警列表 - User: {current_user['username']}, "
        f"Role: {current_user['role']}, Filter: {status_filter}"
    )

    is_admin = current_user["role"] == "admin"

    params = ListAlertsParams(
        org_id=current_user["org_id"],
        user_id=current_user["id"],
        is_admin=is_admin,
        status_filter=status_filter,
    )

    try:
        result = await list_alerts(create_mock_context(), params)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "查询告警列表失败"),
            )

        logger.info(f"✅ 返回 {result['count']} 个告警")
        return result

    except Exception as e:
        logger.error(f"❌ 查询告警列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"查询告警列表失败: {str(e)}"
        )


@router.get("/{alert_id}")
async def get_alert_endpoint(
    alert_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """获取单个告警详情

    **权限**: 所有登录用户

    **说明**:
    - 管理员：可以查看组织内任何告警
    - 普通用户：只能查看自己的告警
    """
    logger.info(f"🔍 获取告警详情 - User: {current_user['username']}, Alert ID: {alert_id}")

    # 权限检查（返回字典）
    alert_dict = await check_alert_permission(alert_id, current_user, db)

    try:
        # 直接返回告警字典
        result = {"success": True, "alert": alert_dict}

        logger.info(f"✅ 返回告警详情 - ID: {alert_id}")
        return result

    except Exception as e:
        logger.error(f"❌ 获取告警详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取告警详情失败: {str(e)}"
        )


@router.put("/{alert_id}")
async def update_alert_endpoint(
    alert_id: str,
    params: UpdateAlertParams,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新告警配置

    **权限**: 所有登录用户

    **说明**:
    - 管理员：可以更新组织内任何告警
    - 普通用户：只能更新自己的告警
    """
    logger.info(f"✏️  更新告警 - User: {current_user['username']}, Alert ID: {alert_id}")

    # 权限检查
    await check_alert_permission(alert_id, current_user, db)

    # 设置告警 ID 和组织 ID
    params.alert_id = alert_id
    params.org_id = current_user["org_id"]

    try:
        result = await update_alert(create_mock_context(), params)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "更新告警失败")
            )

        # 查询完整的告警对象
        with get_db_session() as db:
            alert = db.query(MonitoringConfig).filter(MonitoringConfig.id == alert_id).first()

            if not alert:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="告警更新成功但无法查询",
                )

            # 强制加载所有属性
            _ = (
                alert.id,
                alert.org_id,
                alert.user_id,
                alert.query_description,
                alert.display_name,
                alert.is_active,
                alert.check_frequency,
                alert.created_at,
                alert.updated_at,
                alert.last_checked_at,
            )

            # 在 Session 还活跃时转换为字典
            alert_dict = alert.to_dict()

        logger.info(f"✅ 告警更新成功 - ID: {alert_id}")

        # 返回包含完整告警对象的响应
        return {
            "success": True,
            "alert": alert_dict,
            "message": result.get("message", "告警更新成功"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新告警失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新告警失败: {str(e)}"
        )


@router.delete("/{alert_id}")
async def delete_alert_endpoint(
    alert_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """删除告警

    **权限**: 所有登录用户

    **说明**:
    - 管理员：可以删除组织内任何告警
    - 普通用户：只能删除自己的告警
    """
    logger.info(f"🗑️  删除告警 - User: {current_user['username']}, Alert ID: {alert_id}")

    # 权限检查
    await check_alert_permission(alert_id, current_user, db)

    # 构造删除参数
    params = DeleteAlertParams(
        alert_id=alert_id, user_id=current_user["id"], org_id=current_user["org_id"]
    )

    try:
        result = await delete_alert(create_mock_context(), params)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "删除告警失败")
            )

        logger.info(f"✅ 告警删除成功 - ID: {alert_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除告警失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除告警失败: {str(e)}"
        )


@router.post("/{alert_id}/toggle")
async def toggle_alert_endpoint(
    alert_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """启用/禁用告警

    **权限**: 所有登录用户

    **说明**:
    - 管理员：可以切换组织内任何告警
    - 普通用户：只能切换自己的告警
    - 自动切换当前状态（启用→禁用，禁用→启用）
    """
    logger.info(f"🔄 切换告警状态 - User: {current_user['username']}, Alert ID: {alert_id}")

    # 权限检查
    await check_alert_permission(alert_id, current_user, db)

    # 构造切换参数
    params = ToggleAlertParams(
        alert_id=alert_id, user_id=current_user["id"], org_id=current_user["org_id"]
    )

    try:
        result = await toggle_alert(create_mock_context(), params)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "切换告警状态失败"),
            )

        # 查询完整的告警对象
        with get_db_session() as db:
            alert = db.query(MonitoringConfig).filter(MonitoringConfig.id == alert_id).first()

            if not alert:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="告警状态切换成功但无法查询",
                )

            # 强制加载所有属性
            _ = (
                alert.id,
                alert.org_id,
                alert.user_id,
                alert.query_description,
                alert.display_name,
                alert.is_active,
                alert.check_frequency,
                alert.created_at,
                alert.updated_at,
                alert.last_checked_at,
            )

            # 在 Session 还活跃时转换为字典
            alert_dict = alert.to_dict()

        logger.info(f"✅ 告警状态切换成功 - ID: {alert_id}, New Status: {result.get('is_active')}")

        # 返回包含完整告警对象的响应
        return {
            "success": True,
            "alert": alert_dict,
            "is_active": result.get("is_active"),
            "message": result.get("message", "告警状态切换成功"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 切换告警状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"切换告警状态失败: {str(e)}"
        )


@router.get("/{alert_id}/history")
async def get_alert_history_endpoint(
    alert_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """获取告警执行历史

    **权限**: 所有登录用户

    **说明**:
    - 管理员：可以查看组织内任何告警的历史
    - 普通用户：只能查看自己告警的历史
    - 按执行时间倒序排列
    """
    logger.info(f"📜 获取告警历史 - User: {current_user['username']}, Alert ID: {alert_id}")

    # 权限检查
    await check_alert_permission(alert_id, current_user, db)

    try:
        # 查询告警执行日志（修复：查询正确的表）
        with get_db_session() as db:
            from sqlalchemy import desc

            from backend.models.alert_execution_log import AlertExecutionLog

            history_records = (
                db.query(AlertExecutionLog)
                .filter(AlertExecutionLog.alert_id == alert_id)
                .order_by(desc(AlertExecutionLog.started_at))
                .all()
            )

            # 强制加载所有属性
            history_list = []
            for record in history_records:
                # 访问所有属性确保被加载
                _ = (
                    record.id,
                    record.alert_id,
                    record.triggered,
                    record.current_value,
                    record.email_sent,
                    record.error_message,
                    record.started_at,
                    record.completed_at,
                    record.execution_type,
                    record.success,
                    record.execution_duration_ms,
                )
                history_list.append(record.to_dict())

        logger.info(f"✅ 返回 {len(history_list)} 条历史记录")

        return {"success": True, "count": len(history_list), "history": history_list}

    except Exception as e:
        logger.error(f"❌ 获取告警历史失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取告警历史失败: {str(e)}"
        )


@router.post("/{alert_id}/send-test")
async def send_test_email_endpoint(
    alert_id: str,
    request_body: SendTestEmailRequest = Body(
        default=SendTestEmailRequest()
    ),  # ✅ 使用 Pydantic 模型，默认空对象
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """执行告警检查（通过 Agent）

    **权限**: 所有登录用户
    **预计执行时间**: 30-90 秒
    **说明**: 执行完成后请检查您的邮箱

    **新特性**:
    - 使用 Agent 执行真实的告警检查
    - 查询真实的 AWS 数据
    - 判断是否满足阈值条件
    - 条件性发送告警邮件
    - 记录详细的执行日志

    **权限**:
    - 管理员：可以测试组织内任何告警
    - 普通用户：只能测试自己的告警
    """
    logger.info(f"🚀 执行告警测试 - User: {current_user['username']}, Alert ID: {alert_id}")

    # 权限检查（返回字典）
    alert_dict = await check_alert_permission(alert_id, current_user, db)

    # 获取账号ID（从请求体或告警配置中）
    account_id = request_body.account_id or alert_dict.get("account_id")
    account_type = alert_dict.get("account_type", "aws")

    # 如果没有指定账号，返回错误
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先为告警配置关联账号，或在请求中指定 account_id",
        )

    # 调用 AlertAgentManager 执行告警检查
    from backend.agent.alert_agent import AlertAgentManager

    alert_agent = AlertAgentManager()

    try:
        result = await alert_agent.execute_alert_check(
            alert_id=alert_id,
            alert_name=alert_dict["display_name"],
            query_description=alert_dict["query_description"],
            org_id=current_user["org_id"],
            account_id=account_id,
            account_type=account_type,
            user_id=current_user["id"],  # ✅ 修复：使用 'id' 而不是 'sub'
            is_test=True,
        )

        logger.info(
            f"✅ 告警测试完成 - "
            f"Alert: {alert_id}, "
            f"Triggered: {result.get('triggered')}, "
            f"Time: {result.get('execution_duration_ms')}ms"
        )

        # 返回简洁的结构化结果
        return {
            "success": result.get("success", False),
            "triggered": result.get("triggered", False),
            "current_value": result.get("current_value"),
            "threshold": result.get("threshold"),
            "threshold_operator": result.get("threshold_operator"),
            "email_sent": result.get("email_sent", False),
            "to_emails": result.get("to_emails"),
            "message": result.get("message", "告警检查已完成"),
            "execution_time_ms": result.get("execution_duration_ms"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 告警测试失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"告警测试失败: {str(e)}"
        )


# ========== 调度器管理接口（仅管理员）==========


@router.get("/scheduler/status")
async def get_scheduler_status(current_user: dict = Depends(get_current_admin_user)):
    """获取告警调度器状态（仅管理员）

    返回调度器的运行状态、下次执行时间等信息

    权限：仅管理员
    """
    try:
        from backend.services.alert_scheduler import alert_scheduler

        status = alert_scheduler.get_status()

        logger.info(f"🔍 管理员查询调度器状态: {current_user['username']}")

        return {"success": True, "scheduler": status}
    except Exception as e:
        logger.error(f"❌ 获取调度器状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取调度器状态失败: {str(e)}",
        )


@router.post("/scheduler/trigger")
async def trigger_manual_scan(current_user: dict = Depends(get_current_admin_user)):
    """手动触发一次告警扫描（仅管理员，用于测试）

    立即执行一次告警扫描任务，无需等待定时触发

    注意：这是测试功能，正常情况下由调度器自动执行

    权限：仅管理员
    """
    logger.info(f"🔧 管理员手动触发告警扫描: {current_user['username']}")

    try:
        from backend.services.alert_scheduler import alert_scheduler

        # 执行扫描
        result = await alert_scheduler.scan_and_execute_alerts()

        logger.info(
            f"✅ 手动扫描完成 - "
            f"总计: {result['total_alerts']}, "
            f"已执行: {result['executed']}, "
            f"成功: {result['success']}, "
            f"失败: {result['failed']}"
        )

        return {"success": True, "message": "扫描已完成", "result": result}
    except Exception as e:
        logger.error(f"❌ 手动扫描失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"扫描失败: {str(e)}"
        )
