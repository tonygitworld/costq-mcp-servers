"""数据库辅助类

提供告警配置和历史记录的数据库操作
"""

import logging
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.monitoring import AlertHistory, MonitoringConfig

from ..constants import ERROR_MESSAGES, MAX_ALERTS_PER_ORG, MAX_ALERTS_PER_USER


@contextmanager
def get_db_session():
    """获取数据库会话（上下文管理器）

    使用示例:
        with get_db_session() as db:
            # 执行数据库操作
            pass
    """
    db = next(get_db())
    try:
        yield db
        # 只有在没有异常时才 commit
        db.commit()
    except Exception as e:
        # 发生异常时回滚
        db.rollback()
        logger.error(f"数据库操作失败: {str(e)}", exc_info=True)
        raise
    finally:
        # 确保连接总是被关闭
        try:
            db.close()
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {str(e)}", exc_info=True)


class AlertDBHelper:
    """告警数据库操作辅助类"""

    @staticmethod
    def create_alert(
        db: Session,
        org_id: str,
        user_id: str,
        query_description: str,
        display_name: str,
        check_frequency: str = "daily",
        account_id: str | None = None,  # ✅ 新增
        account_type: str | None = None,  # ✅ 新增
    ) -> MonitoringConfig:
        """创建告警配置

        Args:
            db: 数据库会话
            org_id: 组织ID
            user_id: 用户ID
            query_description: 自然语言描述
            display_name: 显示名称
            check_frequency: 检查频率
            account_id: 关联的云账号ID（可选）
            account_type: 账号类型（aws/gcp，可选）

        Returns:
            MonitoringConfig: 创建的告警配置

        Raises:
            ValueError: 如果超过告警数量限制
        """
        # 检查用户告警数量限制
        user_alert_count = (
            db.query(MonitoringConfig).filter(MonitoringConfig.user_id == user_id).count()
        )

        if user_alert_count >= MAX_ALERTS_PER_USER:
            raise ValueError(
                f"{ERROR_MESSAGES['ALERT_LIMIT_EXCEEDED']} (用户限制: {MAX_ALERTS_PER_USER})"
            )

        # 检查组织告警数量限制
        org_alert_count = (
            db.query(MonitoringConfig).filter(MonitoringConfig.org_id == org_id).count()
        )

        if org_alert_count >= MAX_ALERTS_PER_ORG:
            raise ValueError(
                f"{ERROR_MESSAGES['ALERT_LIMIT_EXCEEDED']} (组织限制: {MAX_ALERTS_PER_ORG})"
            )

        # 创建告警配置
        alert = MonitoringConfig(
            org_id=org_id,
            user_id=user_id,
            query_description=query_description,
            display_name=display_name,
            check_frequency=check_frequency,
            is_active=True,
            account_id=account_id,  # ✅ 新增
            account_type=account_type,  # ✅ 新增
        )

        db.add(alert)
        db.flush()  # 获取生成的 ID

        logger.info(
            f"创建告警成功: alert_id={alert.id}, user_id={user_id}, org_id={org_id}, account_id={account_id}"
        )

        return alert

    @staticmethod
    def list_alerts(
        db: Session, org_id: str, user_id: str, is_admin: bool = False, status_filter: str = "all"
    ) -> list[MonitoringConfig]:
        """查询告警列表

        Args:
            db: 数据库会话
            org_id: 组织ID
            user_id: 当前用户ID（必需，用于权限验证）
            is_admin: 是否是管理员（保留参数用于兼容性，但不影响查询逻辑）
            status_filter: 状态过滤（active/inactive/all）

        Returns:
            List[MonitoringConfig]: 告警配置列表
        """
        from sqlalchemy.orm import joinedload

        # 预加载关联数据，避免 N+1 查询
        query = (
            db.query(MonitoringConfig)
            .options(joinedload(MonitoringConfig.user), joinedload(MonitoringConfig.organization))
            .filter(MonitoringConfig.org_id == org_id)
        )

        # ✅ 权限修复：所有用户（包括管理员）只能查看自己创建的告警
        query = query.filter(MonitoringConfig.user_id == user_id)

        # 状态过滤
        if status_filter == "active":
            query = query.filter(MonitoringConfig.is_active == True)
        elif status_filter == "inactive":
            query = query.filter(MonitoringConfig.is_active == False)

        # 按创建时间倒序
        query = query.order_by(MonitoringConfig.created_at.desc())

        alerts = query.all()

        logger.info(
            f"查询告警列表: org_id={org_id}, user_id={user_id}, is_admin={is_admin}, count={len(alerts)}"
        )

        return alerts

    @staticmethod
    def get_alert_by_id(
        db: Session, alert_id: str, org_id: str, user_id: str | None = None
    ) -> MonitoringConfig | None:
        """根据ID获取告警配置

        Args:
            db: 数据库会话
            alert_id: 告警ID
            org_id: 组织ID（权限验证）
            user_id: 用户ID（可选，如果提供则验证用户权限）

        Returns:
            Optional[MonitoringConfig]: 告警配置，如果不存在或无权限则返回None
        """
        query = db.query(MonitoringConfig).filter(
            and_(MonitoringConfig.id == alert_id, MonitoringConfig.org_id == org_id)
        )

        # 用户权限验证
        if user_id:
            query = query.filter(MonitoringConfig.user_id == user_id)

        return query.first()

    @staticmethod
    def update_alert(
        db: Session,
        alert_id: str,
        org_id: str,
        user_id: str,
        query_description: str | None = None,
        display_name: str | None = None,
        check_frequency: str | None = None,
        account_id: str | None = None,  # ✅ 新增
        account_type: str | None = None,  # ✅ 新增
    ) -> MonitoringConfig | None:
        """更新告警配置

        Args:
            db: 数据库会话
            alert_id: 告警ID
            org_id: 组织ID（权限验证）
            user_id: 用户ID（权限验证）
            query_description: 新的自然语言描述
            display_name: 新的显示名称
            check_frequency: 新的检查频率
            account_id: 新的账号ID（可选）
            account_type: 新的账号类型（可选）

        Returns:
            Optional[MonitoringConfig]: 更新后的告警配置，如果不存在或无权限则返回None
        """
        alert = AlertDBHelper.get_alert_by_id(db, alert_id, org_id, user_id)

        if not alert:
            return None

        # 更新字段
        if query_description is not None:
            alert.query_description = query_description

        if display_name is not None:
            alert.display_name = display_name

        if check_frequency is not None:
            alert.check_frequency = check_frequency

        # ✅ 新增：更新账号字段
        if account_id is not None:
            alert.account_id = account_id

        if account_type is not None:
            alert.account_type = account_type

        alert.updated_at = datetime.now(UTC)

        db.flush()

        logger.info(
            f"更新告警成功: alert_id={alert_id}, user_id={user_id}, account_id={account_id}"
        )

        return alert

    @staticmethod
    def toggle_alert(
        db: Session, alert_id: str, org_id: str, user_id: str
    ) -> MonitoringConfig | None:
        """切换告警启用状态

        Args:
            db: 数据库会话
            alert_id: 告警ID
            org_id: 组织ID（权限验证）
            user_id: 用户ID（权限验证）

        Returns:
            Optional[MonitoringConfig]: 更新后的告警配置，如果不存在或无权限则返回None
        """
        alert = AlertDBHelper.get_alert_by_id(db, alert_id, org_id, user_id)

        if not alert:
            return None

        # 切换状态
        alert.is_active = not alert.is_active
        alert.updated_at = datetime.now(UTC)

        db.flush()

        logger.info(f"切换告警状态: alert_id={alert_id}, is_active={alert.is_active}")

        return alert

    @staticmethod
    def delete_alert(db: Session, alert_id: str, org_id: str, user_id: str) -> bool:
        """删除告警配置

        Args:
            db: 数据库会话
            alert_id: 告警ID
            org_id: 组织ID（权限验证）
            user_id: 用户ID（权限验证）

        Returns:
            bool: 是否删除成功
        """
        alert = AlertDBHelper.get_alert_by_id(db, alert_id, org_id, user_id)

        if not alert:
            return False

        db.delete(alert)
        db.flush()

        logger.info(f"删除告警成功: alert_id={alert_id}, user_id={user_id}")

        return True

    @staticmethod
    def create_history(
        db: Session,
        alert_id: str,
        org_id: str,
        triggered: bool,
        current_value: float | None = None,
        email_sent: bool = False,
        email_error: str | None = None,
        execution_result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> AlertHistory:
        """创建告警历史记录

        Args:
            db: 数据库会话
            alert_id: 告警ID
            org_id: 组织ID
            triggered: 是否触发
            current_value: 当前值
            email_sent: 邮件是否发送成功
            email_error: 邮件发送错误信息
            execution_result: 完整执行结果
            error_message: 执行错误信息

        Returns:
            AlertHistory: 创建的历史记录
        """
        history = AlertHistory(
            alert_id=alert_id,
            org_id=org_id,
            triggered=triggered,
            current_value=current_value,
            email_sent=email_sent,
            email_error=email_error,
            execution_result=execution_result,
            error_message=error_message,
        )

        db.add(history)
        db.flush()

        logger.info(
            f"创建告警历史: alert_id={alert_id}, triggered={triggered}, email_sent={email_sent}"
        )

        return history

    @staticmethod
    def get_alert_history(
        db: Session, alert_id: str, org_id: str, limit: int = 50
    ) -> list[AlertHistory]:
        """获取告警历史记录

        Args:
            db: 数据库会话
            alert_id: 告警ID
            org_id: 组织ID（权限验证）
            limit: 返回记录数量限制

        Returns:
            List[AlertHistory]: 历史记录列表
        """
        histories = (
            db.query(AlertHistory)
            .filter(and_(AlertHistory.alert_id == alert_id, AlertHistory.org_id == org_id))
            .order_by(AlertHistory.created_at.desc())
            .limit(limit)
            .all()
        )

        logger.info(f"查询告警历史: alert_id={alert_id}, count={len(histories)}")

        return histories
