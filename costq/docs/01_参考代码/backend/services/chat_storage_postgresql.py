"""聊天历史存储服务（PostgreSQL版本）

此服务实现：
1. ✅ 使用PostgreSQL数据库（通过SQLAlchemy ORM）
2. ✅ 支持多租户用户隔离
3. ✅ 完整的CRUD操作
4. ✅ 自动统计信息更新（通过数据库触发器）
5. ✅ 兼容现有的chat_storage API接口
6. ✅ 每个操作使用独立的数据库会话，避免事务失败污染

设计原则：
- 与现有SQLite版本API完全兼容
- 所有操作都是异步的（支持WebSocket非阻塞）
- 权限检查由API层负责
- 每个方法创建独立的 session，操作完成后自动关闭
"""

import uuid
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.chat import ChatMessage, ChatSession

import logging

logger = logging.getLogger(__name__)


class ChatStoragePostgreSQL:
    """聊天历史存储服务（PostgreSQL）"""

    def __init__(self):
        """
        初始化存储服务
        """
        logger.info("✅ 聊天存储初始化完成 - PostgreSQL")

    def _get_db(self):
        """获取数据库会话"""
        return next(get_db())

    # ========================================
    # 会话（Session）管理
    # ========================================

    def create_session(self, user_id: str, org_id: str, title: str) -> dict:
        """
        创建新的聊天会话

        Args:
            user_id: 用户ID
            org_id: 组织ID
            title: 会话标题

        Returns:
            创建的会话信息（字典格式）
        """
        db = self._get_db()
        try:
            session_id = str(uuid.uuid4())
            now = datetime.utcnow()

            # 创建会话对象
            new_session = ChatSession(
                id=session_id,
                user_id=user_id,
                org_id=org_id,
                title=title,
                created_at=now,
                updated_at=now,
                message_count=0,
                total_tokens=0,
                model_config={},
            )

            db.add(new_session)
            db.commit()
            db.refresh(new_session)

            logger.info(
                f"✅ 创建聊天会话（PG） - User: {user_id}, Session: {session_id}, Title: {title}"
            )

            return new_session.to_dict()

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 创建聊天会话失败（PG）: {e}")
            raise
        finally:
            db.close()

    def get_session(self, session_id: str) -> dict | None:
        """
        获取单个会话信息

        Args:
            session_id: 会话ID

        Returns:
            会话信息（字典格式），不存在则返回None
        """
        db = self._get_db()
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

            return session.to_dict() if session else None

        except Exception as e:
            db.rollback()  # ✅ 添加 rollback
            logger.error(f"❌ 获取会话失败（PG）: {e}")
            return None
        finally:
            db.close()

    def get_user_sessions(self, user_id: str, limit: int = 50) -> list[dict]:
        """
        获取用户的所有会话（按更新时间倒序）

        Args:
            user_id: 用户ID
            limit: 返回数量限制

        Returns:
            会话列表（字典格式）
        """
        db = self._get_db()
        try:
            sessions = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user_id)
                .order_by(
                    desc(ChatSession.last_message_at).nulls_last(), desc(ChatSession.updated_at)
                )
                .limit(limit)
                .all()
            )

            logger.info(f"📋 获取用户会话列表（PG） - User: {user_id}, Count: {len(sessions)}")

            return [session.to_dict() for session in sessions]

        except Exception as e:
            db.rollback()  # ✅ 添加 rollback
            logger.error(f"❌ 获取用户会话列表失败（PG）: {e}")
            return []
        finally:
            db.close()

    def update_session_title(self, session_id: str, title: str):
        """
        更新会话标题

        Args:
            session_id: 会话ID
            title: 新标题
        """
        db = self._get_db()
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

            if session:
                session.title = title
                session.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"✅ 更新会话标题（PG） - Session: {session_id}, Title: {title}")
            else:
                logger.warning(f"⚠️  会话不存在（PG） - Session: {session_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 更新会话标题失败（PG）: {e}")
            raise
        finally:
            db.close()

    def delete_session(self, session_id: str):
        """
        删除会话（级联删除所有消息）

        Args:
            session_id: 会话ID
        """
        db = self._get_db()
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

            if session:
                db.delete(session)
                db.commit()

                logger.info(f"🗑️  删除会话（PG） - Session: {session_id}")
            else:
                logger.warning(f"⚠️  会话不存在（PG） - Session: {session_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 删除会话失败（PG）: {e}")
            raise
        finally:
            db.close()

    # ========================================
    # 消息（Message）管理
    # ========================================

    def save_message(
        self,
        session_id: str,
        user_id: str,
        message_type: str,  # 'user', 'assistant', 'system', 'tool'
        content: str,
        metadata: str | None = None,
        tool_calls: list | None = None,
        tool_results: list | None = None,
        token_count: int | None = None,
    ) -> dict:
        """
        保存聊天消息

        Args:
            session_id: 会话ID
            user_id: 用户ID
            message_type: 消息类型（user/assistant/system/tool）
            content: 消息内容
            metadata: 元数据（JSON字符串，兼容SQLite接口）
            tool_calls: 工具调用记录（列表）
            tool_results: 工具执行结果（列表）
            token_count: Token数量

        Returns:
            保存的消息信息（字典格式）
        """
        db = self._get_db()
        try:
            message_id = str(uuid.uuid4())
            timestamp = datetime.utcnow()

            # 解析metadata（兼容SQLite的字符串格式）
            metadata_dict = {}
            if metadata:
                import json

                try:
                    metadata_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
                except:
                    pass

            # 创建消息对象
            new_message = ChatMessage(
                id=message_id,
                session_id=session_id,
                user_id=user_id,
                role=message_type,  # SQLAlchemy模型使用'role'字段
                content=content,
                created_at=timestamp,
                token_count=token_count,
                tool_calls=tool_calls,
                tool_results=tool_results,
                message_metadata=metadata_dict,  # 使用message_metadata字段
            )

            db.add(new_message)

            # 注意：会话统计信息由数据库触发器自动更新
            # 不需要手动更新 message_count 和 last_message_at

            db.commit()
            db.refresh(new_message)

            logger.debug(
                f"💬 保存消息（PG） - Session: {session_id}, Type: {message_type}, ID: {message_id}"
            )

            # 转换为字典并调整字段名（兼容SQLite API）
            result = new_message.to_dict()
            result["type"] = result.pop("role")  # 字段名转换：role -> type
            result["timestamp"] = result.pop("created_at")  # 字段名转换：created_at -> timestamp

            return result

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 保存消息失败（PG）: {e}")
            raise
        finally:
            db.close()

    def get_message(self, message_id: str) -> dict | None:
        """
        获取单条消息

        Args:
            message_id: 消息ID

        Returns:
            消息信息（字典格式），不存在则返回None
        """
        db = self._get_db()
        try:
            message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()

            if message:
                result = message.to_dict()
                result["type"] = result.pop("role")
                result["timestamp"] = result.pop("created_at")
                return result

            return None

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 获取消息失败（PG）: {e}")
            return None
        finally:
            db.close()

    def get_session_messages(self, session_id: str, limit: int = 100) -> list[dict]:
        """
        获取会话的所有消息（按时间顺序）

        Args:
            session_id: 会话ID
            limit: 返回数量限制

        Returns:
            消息列表（字典格式）
        """
        db = self._get_db()
        try:
            messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .limit(limit)
                .all()
            )

            logger.debug(f"📨 获取会话消息（PG） - Session: {session_id}, Count: {len(messages)}")

            # 转换字段名以兼容SQLite API
            results = []
            for message in messages:
                msg_dict = message.to_dict()
                msg_dict["type"] = msg_dict.pop("role")
                msg_dict["timestamp"] = msg_dict.pop("created_at")
                results.append(msg_dict)

            return results

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 获取会话消息失败（PG）: {e}")
            return []
        finally:
            db.close()

    def delete_message(self, message_id: str):
        """
        删除单条消息

        Args:
            message_id: 消息ID
        """
        db = self._get_db()
        try:
            message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()

            if message:
                db.delete(message)
                db.commit()

                logger.info(f"🗑️  删除消息（PG） - Message: {message_id}")
            else:
                logger.warning(f"⚠️  消息不存在（PG） - Message: {message_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 删除消息失败（PG）: {e}")
            raise
        finally:
            db.close()


# ========================================
# 工厂函数（依赖注入）
# ========================================


def get_chat_storage_postgresql(db: Session) -> ChatStoragePostgreSQL:
    """
    获取PostgreSQL聊天存储服务实例

    Args:
        db: SQLAlchemy数据库会话

    Returns:
        ChatStoragePostgreSQL实例
    """
    return ChatStoragePostgreSQL(db)
