"""WebSocket API端点 - 使用动态客户端支持多账号"""

import asyncio
import json
import os
import sys
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from ..api.agentcore_response_parser import AgentCoreResponseParser
from ..config.settings import settings
from ..services.agentcore_client import AgentCoreClient
from ..services.audit_logger import get_audit_logger
from ..services.resource_manager import get_resource_manager
from ..services.user_storage import get_user_storage
from ..utils.auth import decode_access_token

import logging

logger = logging.getLogger(__name__)


class QueryRateLimiter:
    """查询速率限制器（简单滑动窗口实现）"""

    def __init__(self, max_queries: int = 60, window_seconds: int = 60):
        """
        Args:
            max_queries: 窗口内最大查询数
            window_seconds: 时间窗口（秒）
        """
        self.max_queries = max_queries
        self.window_seconds = window_seconds
        # 用户ID -> 查询时间戳队列
        self.query_times: dict[str, deque] = {}

    def check_rate_limit(self, user_id: str) -> tuple[bool, str | None]:
        """
        检查是否超过速率限制

        Returns:
            (是否允许, 错误消息)
        """
        now = time.time()

        # 初始化用户队列
        if user_id not in self.query_times:
            self.query_times[user_id] = deque()

        query_queue = self.query_times[user_id]

        # 移除窗口外的旧记录
        while query_queue and query_queue[0] < now - self.window_seconds:
            query_queue.popleft()

        # 检查是否超限
        if len(query_queue) >= self.max_queries:
            wait_time = int(query_queue[0] + self.window_seconds - now)
            return False, f"查询过于频繁，请等待 {wait_time} 秒后重试"

        # 记录本次查询
        query_queue.append(now)
        return True, None


class ConnectionManager:
    """WebSocket连接管理器 - 支持用户隔离和查询追踪"""

    def __init__(self):
        # 用户ID -> WebSocket连接
        self.active_connections: dict[str, WebSocket] = {}
        # 用户ID -> 会话信息
        self.user_sessions: dict[str, dict] = {}
        # 速率限制器：60次查询/分钟
        self.rate_limiter = QueryRateLimiter(max_queries=60, window_seconds=60)
        # ✅ 新增: 活跃查询追踪 (user_id -> {query_id: query_info})
        self.active_queries: dict[str, dict[str, dict[str, Any]]] = {}
        # ✅ 新增: 查询取消事件 (query_id -> asyncio.Event)
        self.cancel_events: dict[str, asyncio.Event] = {}
        # 🆕 心跳追踪 (user_id -> 最后心跳时间戳)
        self.last_heartbeat: dict[str, float] = {}
        # 🆕 最后查询时间 (user_id -> 最后查询时间戳)
        self.last_query_time: dict[str, float] = {}

        # ✅ P0修复: 超时配置
        self.heartbeat_timeout = 120  # 120秒未收到心跳视为超时
        self.query_timeout = 900  # 900秒（15分钟）未查询视为僵尸连接

        # ✅ P0修复: 后台清理任务
        self._cleanup_task = None

    async def connect(
        self, websocket: WebSocket, user_id: str, org_id: str, role: str, username: str
    ):
        """连接并关联用户"""
        logger.info(f"🔌 开始建立连接 - User: {username} (ID: {user_id})")
        await websocket.accept()
        logger.debug(f"✅ WebSocket accept 完成 - User: {username}")

        # ✅ P0: 如果用户已有连接，断开旧连接（防止竞态条件）
        if user_id in self.active_connections:
            logger.warning(f"⚠️  检测到用户已有连接，将断开旧连接 - User: {username}")
            old_ws = self.active_connections[user_id]
            # 先从字典中移除，确保旧连接的主循环能检测到断开
            self.active_connections.pop(user_id, None)
            try:
                await old_ws.close(code=1000, reason="New connection established")
                logger.info(f"🔄 用户重新连接，旧连接已关闭 - User: {username}")
            except Exception as e:
                logger.warning(f"⚠️  关闭旧连接时出错（可能已关闭） - User: {username}: {e}")

        # 注册新连接
        self.active_connections[user_id] = websocket
        self.user_sessions[user_id] = {
            "org_id": org_id,
            "role": role,
            "username": username,
            "connected_at": datetime.utcnow().isoformat(),
        }
        logger.debug(f"✅ 连接已注册到 active_connections - User: {username}")

        # 🆕 初始化心跳追踪
        now = time.time()
        self.last_heartbeat[user_id] = now
        self.last_query_time[user_id] = now
        logger.debug(f"✅ 心跳和查询时间已初始化 - User: {username}")

        logger.info(
            f"✅ WebSocket连接完成 - User: {username} (ID: {user_id}), Role: {role}, 总连接数: {len(self.active_connections)}"
        )

    async def disconnect(self, user_id: str):
        """断开用户连接并清理所有活跃查询（Phase 2.2: 支持资源清理）"""
        username = self.user_sessions.get(user_id, {}).get("username", user_id)
        logger.info(f"🔌 开始断开连接 - User: {username}")

        # ✅ 新增: 取消该用户的所有活跃查询
        if user_id in self.active_queries:
            query_count = len(self.active_queries[user_id])
            logger.debug(f"🛑 取消 {query_count} 个活跃查询 - User: {username}")

            for query_id, query_info in list(self.active_queries[user_id].items()):
                # 触发取消事件
                cancel_event = self.cancel_events.get(query_id)
                if cancel_event:
                    cancel_event.set()
                    logger.info(f"🛑 WebSocket断开，取消查询 - User: {username}, Query: {query_id}")

                # Phase 2.2: 清理 StreamingAgent 资源
                streaming_agent = query_info.get("streaming_agent")
                if streaming_agent and hasattr(streaming_agent, "cleanup_resources"):
                    try:
                        await streaming_agent.cleanup_resources()
                        logger.debug(f"✅ StreamingAgent资源已清理 - Query: {query_id}")
                    except Exception as e:
                        logger.error(
                            f"❌ 清理 StreamingAgent 资源失败 - Query: {query_id}, Error: {e}"
                        )

            # ✅ 安全清理查询记录（防止重复清理）
            if user_id in self.active_queries:
                # 先收集该用户的所有 query_id（用于清理 cancel_events）
                user_query_ids = list(self.active_queries[user_id].keys())

                # 删除活跃查询记录
                del self.active_queries[user_id]
                logger.debug(f"✅ 活跃查询记录已清理 - User: {username}")

                # 清理该用户的所有取消事件
                for query_id in user_query_ids:
                    if query_id in self.cancel_events:
                        del self.cancel_events[query_id]
                        logger.debug(f"✅ 取消事件已清理 - Query: {query_id}")

        # ✅ 修复: 真正关闭 WebSocket 连接
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                # 发送 close frame 到客户端
                await websocket.close(code=1000, reason="Connection cleanup")
                logger.debug(f"✅ WebSocket连接已关闭 - User: {username}")
            except Exception as e:
                logger.warning(f"⚠️ 关闭WebSocket连接失败（可能已断开）- User: {username}: {e}")
            finally:
                # 确保从字典中移除
                del self.active_connections[user_id]
                logger.debug(f"✅ WebSocket连接已移除 - User: {username}")
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            logger.debug(f"✅ 会话信息已清理 - User: {username}")

        # 🆕 清理心跳追踪
        if user_id in self.last_heartbeat:
            del self.last_heartbeat[user_id]
            logger.debug(f"✅ 心跳追踪已清理 - User: {username}")
        if user_id in self.last_query_time:
            del self.last_query_time[user_id]
            logger.debug(f"✅ 查询时间追踪已清理 - User: {username}")

        logger.info(
            f"❌ WebSocket断开完成 - User: {username}, 剩余连接数: {len(self.active_connections)}"
        )

    async def send_to_user(self, user_id: str, message: str):
        """只发送给特定用户"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                import traceback

                username = self.user_sessions.get(user_id, {}).get("username", user_id)
                logger.error(f"❌ 发送消息失败 - User: {username}, Error: {e}")
                logger.error(f"异常类型: {type(e).__name__}")
                logger.error(f"异常堆栈:\n{traceback.format_exc()}")
                logger.warning(f"⚠️  将断开用户连接 - User: {username}")
                await self.disconnect(user_id)
        else:
            # 🆕 添加警告：尝试向不存在的连接发送消息
            username = self.user_sessions.get(user_id, {}).get("username", user_id)
            logger.warning(
                f"⚠️  尝试向不存在的连接发送消息 - User: {username}, "
                f"当前活跃连接数: {len(self.active_connections)}"
            )

    def get_user_session(self, user_id: str) -> dict | None:
        """获取用户会话信息"""
        return self.user_sessions.get(user_id)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息（兼容旧代码）"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"❌ 发送个人消息失败: {type(e).__name__}: {e}")
            raise  # 重新抛出异常，让调用者处理

    # ✅ 新增: 查询管理方法
    def register_query(
        self, user_id: str, query_id: str, query_info: dict[str, Any], streaming_agent: Any = None
    ) -> asyncio.Event:
        """注册新查询并创建取消事件

        Args:
            user_id: 用户ID
            query_id: 查询ID
            query_info: 查询信息(content, account_ids等)
            streaming_agent: StreamingAgentWrapper 实例（Phase 2.2 新增）

        Returns:
            asyncio.Event: 取消事件
        """
        # 初始化用户查询字典
        if user_id not in self.active_queries:
            self.active_queries[user_id] = {}

        # 创建取消事件
        cancel_event = asyncio.Event()
        self.cancel_events[query_id] = cancel_event

        # 注册查询
        self.active_queries[user_id][query_id] = {
            **query_info,
            "status": "running",
            "started_at": time.time(),
            "streaming_agent": streaming_agent,  # Phase 2.2: 存储agent引用
        }

        logger.info(f"📝 注册查询 - User: {user_id}, Query: {query_id}")
        return cancel_event

    async def unregister_query(self, user_id: str, query_id: str):
        """注销查询（Phase 2.2: 异步，支持资源清理）

        Args:
            user_id: 用户ID
            query_id: 查询ID
        """
        # Phase 2.2: 清理 StreamingAgent 资源
        if user_id in self.active_queries and query_id in self.active_queries[user_id]:
            streaming_agent = self.active_queries[user_id][query_id].get("streaming_agent")
            if streaming_agent and hasattr(streaming_agent, "cleanup_resources"):
                try:
                    await streaming_agent.cleanup_resources()
                except Exception as e:
                    logger.error(f"❌ 清理 StreamingAgent 资源失败 - Query: {query_id}, Error: {e}")

        # 清理取消事件
        if query_id in self.cancel_events:
            del self.cancel_events[query_id]

        # 清理查询记录
        if user_id in self.active_queries:
            if query_id in self.active_queries[user_id]:
                del self.active_queries[user_id][query_id]

            # 如果用户没有活跃查询，清理用户记录
            if not self.active_queries[user_id]:
                del self.active_queries[user_id]

        logger.info(f"🗑️  注销查询 - User: {user_id}, Query: {query_id}")

    def cancel_query(self, user_id: str, query_id: str) -> bool:
        """取消指定查询

        Args:
            user_id: 用户ID
            query_id: 查询ID

        Returns:
            bool: 是否成功触发取消
        """
        # 检查查询是否存在
        if user_id not in self.active_queries or query_id not in self.active_queries[user_id]:
            logger.warning(f"⚠️  查询不存在 - User: {user_id}, Query: {query_id}")
            return False

        # 获取取消事件
        cancel_event = self.cancel_events.get(query_id)
        if not cancel_event:
            logger.warning(f"⚠️  取消事件不存在 - Query: {query_id}")
            return False

        # 触发取消
        cancel_event.set()

        # 更新查询状态
        self.active_queries[user_id][query_id]["status"] = "cancelling"
        self.active_queries[user_id][query_id]["cancelled_at"] = time.time()

        logger.info(f"🛑 触发查询取消 - User: {user_id}, Query: {query_id}")
        return True

    # ✅ P0修复: 启动超时检测任务
    async def start_cleanup_task(self):
        """启动后台清理任务（定期检查超时连接）"""
        if self._cleanup_task is not None:
            logger.warning("清理任务已在运行，跳过启动")
            return

        async def cleanup_loop():
            """后台清理循环"""
            iteration = 0
            while True:
                try:
                    await asyncio.sleep(60)  # 每60秒检查一次
                    iteration += 1
                    logger.debug(f"🔍 清理任务执行 - 第 {iteration} 次检查")
                    await self._check_and_cleanup_timeouts()
                    logger.debug(f"🔍 清理任务完成 - 第 {iteration} 次检查")
                except asyncio.CancelledError:
                    logger.info("清理任务被取消")
                    break
                except Exception as e:
                    logger.error(f"❌ 清理任务异常（第 {iteration} 次）: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("✅ 超时连接清理任务已启动（间隔60秒）")

    # ✅ P0修复: 停止清理任务
    async def stop_cleanup_task(self):
        """停止后台清理任务"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("🛑 超时连接清理任务已停止")

    # ✅ P0修复: 检查并清理超时连接
    async def _check_and_cleanup_timeouts(self):
        """检查并清理超时的连接"""
        now = time.time()
        timeout_users = []

        # 🔍 DEBUG: 记录检查开始
        active_count = len(self.active_connections)
        logger.debug(f"🔍 开始超时检查 - 当前活跃连接数: {active_count}")

        for user_id in list(self.active_connections.keys()):
            # 检查心跳超时
            last_heartbeat = self.last_heartbeat.get(user_id, now)
            heartbeat_interval = now - last_heartbeat

            # 检查查询超时
            last_query = self.last_query_time.get(user_id, now)
            query_interval = now - last_query

            # 判断是否超时
            if heartbeat_interval > self.heartbeat_timeout:
                username = self.user_sessions.get(user_id, {}).get("username", user_id)
                logger.warning(
                    f"⚠️ 检测到心跳超时 - User: {username}, "
                    f"上次心跳: {heartbeat_interval:.1f}秒前"
                )
                timeout_users.append((user_id, "heartbeat"))

            elif query_interval > self.query_timeout:
                username = self.user_sessions.get(user_id, {}).get("username", user_id)
                logger.warning(
                    f"⚠️ 检测到僵尸连接 - User: {username}, "
                    f"上次查询: {query_interval / 60:.1f}分钟前"
                )
                timeout_users.append((user_id, "idle"))

        # 🔍 DEBUG: 记录检测结果
        logger.info(f"🔍 超时检查完成 - 检测到 {len(timeout_users)} 个超时连接")
        if timeout_users:
            logger.info(f"🔍 超时用户列表: {[(uid, reason) for uid, reason in timeout_users]}")

        # 清理超时连接（每个连接独立异常处理，确保一个失败不影响其他）
        cleaned_count = 0
        logger.info(f"🔍 开始清理循环 - 待清理数量: {len(timeout_users)}")

        for i, (user_id, reason) in enumerate(timeout_users, 1):
            username = self.user_sessions.get(user_id, {}).get("username", user_id)
            logger.debug(f"🔍 处理第 {i}/{len(timeout_users)} 个超时连接: {username}")

            try:
                logger.info(f"🧹 清理超时连接 - User: {username}, 原因: {reason}")

                # 发送断开通知（尝试，可能失败）
                # ⚠️ 注意：send_to_user 在失败时会调用 disconnect，所以需要检查连接是否还存在
                if user_id in self.active_connections:
                    logger.debug(f"🔍 连接仍存在，尝试发送断开通知 - User: {username}")
                    try:
                        await self.send_to_user(
                            user_id,
                            json.dumps({
                                "type": "connection_timeout",
                                "reason": reason,
                                "message": "连接超时，请刷新页面重连",
                                "timestamp": now
                            })
                        )
                        await asyncio.sleep(0.5)  # 等待消息发送
                        logger.debug(f"✅ 超时通知已发送 - User: {username}")
                    except Exception as e:
                        logger.warning(f"⚠️ 发送超时通知失败（连接可能已断开）- User: {username}: {e}")
                else:
                    logger.debug(f"🔍 连接已不存在（可能被其他进程清理）- User: {username}")

                # 强制断开连接（如果 send_to_user 已经断开，这里会跳过）
                if user_id in self.active_connections:
                    logger.debug(f"🔍 执行 disconnect - User: {username}")
                    await self.disconnect(user_id)
                    cleaned_count += 1
                    logger.info(f"✅ 连接已清理 - User: {username}")
                else:
                    logger.debug(f"ℹ️  连接已在发送通知时断开 - User: {username}")
                    cleaned_count += 1

            except Exception as e:
                logger.error(f"❌ 清理连接失败 - User: {username}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 继续清理下一个连接

        logger.debug(f"🔍 清理循环结束 - 实际清理: {cleaned_count}/{len(timeout_users)}")

        if timeout_users:
            logger.warning(f"🧹 本次清理了 {cleaned_count}/{len(timeout_users)} 个超时连接")
        else:
            logger.debug(f"🔍 本次检查未发现超时连接")


manager = ConnectionManager()


# ✅ 辅助函数：构建消息 metadata（提取重复代码）
def build_message_metadata(token_usage_data: dict | None) -> str | None:
    """
    构建消息的 metadata JSON 字符串

    Args:
        token_usage_data: Token 统计数据字典

    Returns:
        metadata JSON 字符串，失败时返回 None
    """
    if not token_usage_data:
        return None

    metadata_dict = {"token_usage": token_usage_data}

    try:
        return json.dumps(metadata_dict)
    except (TypeError, ValueError) as e:
        logger.error(f"❌ Token 统计序列化失败: {e}")
        return None


async def websocket_endpoint(
    websocket: WebSocket,
    token: str,  # ✅ WebSocket查询参数直接声明，不需要Query(...)
):
    """WebSocket端点处理函数 - 支持动态多账号和用户认证"""

    # ✅ P0修复: 启动清理任务（如果未启动）
    if manager._cleanup_task is None:
        await manager.start_cleanup_task()

    # 1. 验证Token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        org_id = payload.get("org_id")
        role = payload.get("role")

        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            logger.warning("❌ WebSocket连接失败: Token中缺少用户ID")
            return

        # ✅ 验证 org_id（Memory 集成需要）
        if not org_id:
            logger.warning(f"⚠️  Token 中缺少 org_id - User: {user_id}，Memory 集成将被禁用")
        else:
            logger.debug(f"✅ Token 验证成功 - User: {user_id}, Org: {org_id}, Role: {role}")

    except HTTPException as e:
        await websocket.close(code=1008, reason="Unauthorized")
        logger.warning(f"❌ WebSocket连接失败: Token验证失败 - {e.detail}")
        return
    except Exception as e:
        await websocket.close(code=1008, reason="Authentication error")
        logger.error(f"❌ WebSocket连接失败: 认证错误 - {e}")
        return

    # 2. 验证用户状态
    user_storage = get_user_storage()
    try:
        user = user_storage.get_user_by_id(user_id)
        if not user:
            await websocket.close(code=1008, reason="User not found")
            logger.warning(f"❌ WebSocket连接失败: 用户不存在 - ID: {user_id}")
            return

        if not user.get("is_active", True):
            await websocket.close(code=1008, reason="User inactive")
            logger.warning(f"❌ WebSocket连接失败: 用户已禁用 - {user.get('username')}")
            return

        username = user.get("username", "Unknown")

        # ✅ 检查租户是否被禁用（新增）
        # 白名单策略：默认False，明确激活才允许访问
        organization = user_storage.get_organization_by_id(org_id)
        if not organization or not organization.get("is_active", False):
            await websocket.close(code=1008, reason="Tenant inactive")
            logger.warning(f"❌ WebSocket连接失败: 租户未激活 - User: {username}, Org: {org_id}")
            return

    except Exception as e:
        await websocket.close(code=1008, reason="User verification failed")
        logger.error(f"❌ WebSocket连接失败: 用户验证错误 - {e}")
        return

    # 3. ========== 检查资源限制 ==========
    resource_manager = get_resource_manager()
    connection_id = f"{user_id}:{uuid.uuid4()}"

    # 检查WebSocket连接数限制
    if not await resource_manager.check_websocket_limit(user_id):
        await websocket.close(
            code=1008, reason="Too many connections. Please close other tabs or sessions."
        )
        logger.warning(f"❌ WebSocket连接被拒绝: 用户 {username} 连接数达到上限")
        return

    # 4. 建立连接并关联用户（manager.connect会调用websocket.accept）
    await manager.connect(websocket, user_id, org_id, role, username)

    # 注册连接到资源管理器
    await resource_manager.register_websocket(connection_id, websocket)

    # 发送欢迎消息（添加异常处理，防止React Strict Mode双重挂载导致的竞态条件）
    try:
        await manager.send_to_user(
            user_id,
            json.dumps(
                {
                    "type": "system",
                    "content": f"欢迎 {username}！WebSocket连接已建立。",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )
    except Exception as e:
        # 如果发送失败（连接已被新连接替换），忽略错误
        logger.debug(f"发送欢迎消息失败（可能连接已被替换）: {e}")

    try:
        logger.info(f"🔄 进入WebSocket消息循环 - User: {username}")
        while True:
            # ✅ P0: 检查当前连接是否仍然有效（防止用户刷新页面后旧连接继续运行）
            if manager.active_connections.get(user_id) != websocket:
                logger.info(f"🔌 检测到新连接已建立，退出旧连接循环 - User: {username}")
                break

            # ✅ P0: 检查 WebSocket 连接状态，防止已关闭的连接尝试接收数据
            try:
                # 接收消息（阻塞等待）
                logger.debug(f"⏳ 等待接收消息... - User: {username}")
                data = await websocket.receive_text()
                logger.debug(f"📩 收到原始数据 ({len(data)} 字节) - User: {username}")
            except RuntimeError as e:
                # WebSocket 已断开连接（通常发生在用户刷新页面时）
                if "WebSocket is not connected" in str(e) or 'Need to call "accept" first' in str(
                    e
                ):
                    logger.info(
                        f"🔌 WebSocket连接已断开（用户刷新页面或网络中断） - User: {username}"
                    )
                    break
                raise  # 其他 RuntimeError 继续抛出

            if data.strip():
                try:
                    # 解析消息（支持JSON格式）
                    try:
                        message_data = json.loads(data)

                        # 🔐 检查是否是确认响应消息
                        message_type = message_data.get("type")

                        # ✅ 心跳处理 (Ping/Pong)
                        if message_type == "ping":
                            # 🆕 更新心跳时间戳
                            now = time.time()
                            last_heartbeat = manager.last_heartbeat.get(user_id, now)
                            interval = now - last_heartbeat
                            manager.last_heartbeat[user_id] = now

                            # 🆕 仅在间隔异常时记录（正常30秒间隔不记录，避免日志过多）
                            if interval > 60:  # 超过60秒才记录
                                logger.warning(
                                    f"💓 心跳间隔异常 - User: {username}, 间隔: {interval:.1f}秒"
                                )

                            await websocket.send_text(json.dumps({"type": "pong"}))
                            continue

                        if message_type == "confirmation_response":
                            confirmation_id = message_data.get("confirmation_id")
                            approved = message_data.get("approved", False)

                            logger.info(
                                f"📨 收到确认响应 - User: {username}, "
                                f"ID: {confirmation_id}, Approved: {approved}"
                            )

                            # TODO: 将确认响应传递给 Agent
                            # 当前 Strands Agent 无法中断执行，
                            # 这个功能需要在前端完成后进一步实现
                            # 暂时只记录日志

                            if approved:
                                await manager.send_to_user(
                                    user_id,
                                    json.dumps(
                                        {
                                            "type": "info",
                                            "content": "✅ 操作已批准，继续执行...",
                                            "timestamp": time.time(),
                                        }
                                    ),
                                )
                            else:
                                await manager.send_to_user(
                                    user_id,
                                    json.dumps(
                                        {
                                            "type": "info",
                                            "content": "❌ 操作已拒绝",
                                            "timestamp": time.time(),
                                        }
                                    ),
                                )

                            continue  # 处理完确认响应，继续等待下一条消息

                        # ✅ 新增: 处理取消生成消息
                        if message_type == "cancel_generation":
                            query_id = message_data.get("query_id")
                            logger.info(f"🛑 收到取消请求 - User: {username}, Query: {query_id}")

                            # 触发取消
                            success = manager.cancel_query(user_id, query_id)

                            if success:
                                # 发送取消确认
                                await manager.send_to_user(
                                    user_id,
                                    json.dumps(
                                        {
                                            "type": "cancellation_acknowledged",
                                            "query_id": query_id,
                                            "timestamp": time.time(),
                                        }
                                    ),
                                )
                                logger.info(f"✅ 取消确认已发送 - Query: {query_id}")
                            else:
                                # 查询不存在或已完成
                                await manager.send_to_user(
                                    user_id,
                                    json.dumps(
                                        {
                                            "type": "error",
                                            "content": "查询不存在或已完成",
                                            "query_id": query_id,
                                            "timestamp": time.time(),
                                        }
                                    ),
                                )

                            continue  # 处理完取消请求，继续等待下一条消息

                        # ✅ 修改: 支持新的查询消息格式（包含query_id）
                        if message_type == "query":
                            query_id = message_data.get("query_id")
                            query = message_data.get("content", data)
                            account_ids = message_data.get("account_ids", [])
                            gcp_account_ids = message_data.get("gcp_account_ids", [])
                        else:
                            # 向后兼容：旧格式查询（无type字段）
                            query_id = f"query_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                            query = message_data.get("content", data)
                            account_ids = message_data.get("account_ids", [])  # AWS 账号
                            gcp_account_ids = message_data.get("gcp_account_ids", [])  # GCP 账号
                        # 🆕 记录查询时间戳和间隔
                        now = time.time()
                        last_query = manager.last_query_time.get(user_id, now)
                        query_interval = now - last_query
                        manager.last_query_time[user_id] = now

                        # 🆕 记录查询和空闲时长
                        if query_interval > 300:  # 超过5分钟记录
                            logger.info(
                                f"📨 收到查询 - User: {username}, QueryID: {query_id}, "
                                f"Content: {query[:50]}..., 距上次查询: {query_interval / 60:.1f}分钟"
                            )
                        else:
                            logger.info(
                                f"📨 收到查询 - User: {username}, QueryID: {query_id}, Content: {query[:50]}..."
                            )

                        sys.stdout.flush()
                        print(f"🔍 DEBUG - AWS account_ids: {account_ids}", flush=True)
                        print(f"🔍 DEBUG - GCP account_ids: {gcp_account_ids}", flush=True)
                        if account_ids:
                            print(f"🔑 选中 AWS 账号: {len(account_ids)} 个", flush=True)
                        if gcp_account_ids:
                            print(f"🔑 选中 GCP 账号: {len(gcp_account_ids)} 个", flush=True)
                    except json.JSONDecodeError:
                        query = data
                        account_ids = []
                        gcp_account_ids = []
                        print(f"📨 收到查询 (文本): {query}", flush=True)

                    # ✅ 速率限制检查
                    allowed, error_msg = manager.rate_limiter.check_rate_limit(user_id)
                    if not allowed:
                        logger.warning(f"⚠️  查询速率限制 - User: {username}, {error_msg}")
                        await manager.send_to_user(
                            user_id,
                            json.dumps(
                                {
                                    "type": "error",
                                    "content": f"⚠️ {error_msg}",
                                    "timestamp": time.time(),
                                }
                            ),
                        )
                        continue

                    # ========== 并发查询限制检查 ==========
                    query_slot_id = f"{user_id}:{uuid.uuid4()}"
                    if not await resource_manager.check_query_limit(user_id):
                        logger.warning(f"⚠️  并发查询限制 - User: {username}")
                        await manager.send_to_user(
                            user_id,
                            json.dumps(
                                {
                                    "type": "error",
                                    "content": "⚠️ Too many concurrent queries. Please wait for previous queries to complete.",
                                    "timestamp": time.time(),
                                }
                            ),
                        )
                        continue

                    # ✅ 记录审计日志
                    audit_logger = get_audit_logger()
                    if account_ids:
                        audit_logger.log_query(user_id, org_id, query, account_ids, "aws")
                    if gcp_account_ids:
                        audit_logger.log_query(user_id, org_id, query, gcp_account_ids, "gcp")

                    # 4. 权限验证 - 普通用户只能访问被授权的账号
                    if role != "admin":
                        # 验证AWS账号权限
                        if account_ids:
                            allowed_aws_accounts = user_storage.get_user_aws_accounts(user_id)
                            unauthorized_aws = [
                                aid for aid in account_ids if aid not in allowed_aws_accounts
                            ]

                            if unauthorized_aws:
                                logger.warning(
                                    f"⚠️  权限不足 - User: {username}, 未授权AWS账号: {unauthorized_aws}"
                                )
                                await manager.send_to_user(
                                    user_id,
                                    json.dumps(
                                        {
                                            "type": "error",
                                            "content": f"❌ 您没有访问以下AWS账号的权限: {', '.join(unauthorized_aws[:3])}{'...' if len(unauthorized_aws) > 3 else ''}",
                                            "timestamp": time.time(),
                                        }
                                    ),
                                )
                                continue

                        # 验证GCP账号权限
                        if gcp_account_ids:
                            allowed_gcp_accounts = user_storage.get_user_gcp_accounts(user_id)
                            unauthorized_gcp = [
                                gid for gid in gcp_account_ids if gid not in allowed_gcp_accounts
                            ]

                            if unauthorized_gcp:
                                logger.warning(
                                    f"⚠️  权限不足 - User: {username}, 未授权GCP账号: {unauthorized_gcp}"
                                )
                                await manager.send_to_user(
                                    user_id,
                                    json.dumps(
                                        {
                                            "type": "error",
                                            "content": f"❌ 您没有访问以下GCP账号的权限: {', '.join(unauthorized_gcp[:3])}{'...' if len(unauthorized_gcp) > 3 else ''}",
                                            "timestamp": time.time(),
                                        }
                                    ),
                                )
                                continue
                    else:
                        logger.info(f"✅ 管理员访问 - User: {username}, 跳过权限检查")

                    # 性能追踪
                    query_start = time.time()

                    # ============================================================
                    # AgentCore Runtime 模式：账号信息处理
                    # ============================================================
                    # ✅ 移除：不再需要 AgentManager 和 MCPManager（由 Runtime 内部管理）
                    from ..services.account_storage import get_account_storage
                    from ..services.aws_credentials_provider import get_credentials_provider
                    from ..services.gcp_account_storage_postgresql import (
                        get_gcp_account_storage_postgresql,
                    )
                    from ..services.gcp_credentials_provider import get_gcp_credentials_provider

                    aws_credentials_provider = get_credentials_provider()
                    gcp_credentials_provider = get_gcp_credentials_provider()
                    aws_account_storage = get_account_storage()
                    gcp_account_storage = get_gcp_account_storage_postgresql()

                    # ✅ AgentCore Runtime 模式：MCP 和 Agent 由 Runtime 内部管理
                    # 不需要在 FastAPI 层创建 MCP Manager 和 Agent Manager

                    # 1. 检查当前用户是否有任何账号（AWS 或 GCP）- 多租户架构
                    # 管理员可以访问本组织所有账号，普通用户只能访问授权账号
                    if role == "admin":
                        # 1.1 管理员：获取本组织所有账号
                        all_aws_accounts = aws_account_storage.list_accounts(org_id=org_id)
                        all_gcp_accounts = gcp_account_storage.list_accounts(org_id=org_id)
                        logger.info(
                            f"✅ 管理员账号列表 - Org: {org_id}, AWS: {len(all_aws_accounts)}, GCP: {len(all_gcp_accounts)}"
                        )
                    else:
                        # 1.2 普通用户：获取被授权的AWS账号ID列表
                        authorized_aws_account_ids = user_storage.get_user_aws_accounts(user_id)

                        # 1.3 普通用户：获取本组织GCP账号列表
                        all_gcp_accounts = gcp_account_storage.list_accounts(org_id=org_id)

                        # 1.4 普通用户：根据权限过滤AWS账号
                        all_aws_accounts_raw = aws_account_storage.list_accounts(org_id=org_id)
                        all_aws_accounts = [
                            acc
                            for acc in all_aws_accounts_raw
                            if acc["id"] in authorized_aws_account_ids
                        ]
                        logger.info(
                            f"✅ 普通用户账号列表 - Org: {org_id}, AWS: {len(all_aws_accounts)}/{len(all_aws_accounts_raw)}, GCP: {len(all_gcp_accounts)}"
                        )

                    if not all_aws_accounts and not all_gcp_accounts:
                        # 没有配置任何账号，提示用户添加
                        print("⚠️  未配置任何账号，提示用户先添加", flush=True)
                        await manager.send_personal_message(
                            json.dumps(
                                {
                                    "type": "response",
                                    "content": """❗ **请先配置云账号**

您还没有添加任何云账号。请按以下步骤操作：

**添加 AWS 账号：**
1. 点击侧边栏的 **"AWS 账号"** 按钮
2. 点击 **"添加账号"**
3. 填写您的 AWS 凭证信息

**添加 GCP 账号：**
1. 点击侧边栏的 **"GCP 账号"** 按钮
2. 点击 **"添加账号"**
3. 上传您的 GCP Service Account JSON

添加完成后，您就可以开始查询了！

💡 如果需要帮助，请参考文档或联系管理员。""",
                                    "timestamp": time.time(),
                                }
                            ),
                            websocket,
                        )
                        continue  # 跳过后续处理

                    # 2. 确定要使用的账号（优先用户选择的账号，未选择时优先 AWS，然后 GCP）
                    account_id_to_use = None
                    account_type = None  # 'aws' or 'gcp'

                    # 🆕 多账号查询检测
                    if account_ids and len(account_ids) > 1:
                        # 用户选择了多个 AWS 账号 - 启用串行查询
                        logger.info(f"🔀 检测到多账号查询 - 账号数: {len(account_ids)}")
                        await handle_multi_account_query_serial(
                            websocket=websocket,
                            user_id=user_id,
                            org_id=org_id,
                            username=username,
                            query_id=query_id,
                            query=query,
                            account_ids=account_ids,
                            agent_manager=agent_manager,
                            aws_credentials_provider=aws_credentials_provider,
                            aws_account_storage=aws_account_storage,
                            manager=manager,
                            resource_manager=resource_manager,
                        )
                        continue  # 跳过单账号处理逻辑

                    if account_ids and len(account_ids) > 0:
                        # 用户选择了 AWS 账号
                        account_id_to_use = account_ids[0]
                        account_type = "aws"
                        print(f"🔑 选中 AWS 账号: {account_id_to_use}", flush=True)
                    elif gcp_account_ids and len(gcp_account_ids) > 0:
                        # 用户选择了 GCP 账号
                        account_id_to_use = gcp_account_ids[0]
                        account_type = "gcp"
                        print(f"🔑 选中 GCP 账号: {account_id_to_use}", flush=True)
                    elif all_aws_accounts:
                        # 没有选择，默认使用第一个有权限的 AWS 账号（AWS优先）
                        default_account = all_aws_accounts[0]
                        account_id_to_use = default_account["id"]
                        account_type = "aws"
                        print(
                            f"📌 未选择账号，使用默认 AWS 账号: {default_account.get('alias')} (ID: {account_id_to_use})",
                            flush=True,
                        )
                    elif all_gcp_accounts:
                        # 没有 AWS，使用第一个 GCP 账号
                        default_account = all_gcp_accounts[0]
                        account_id_to_use = default_account["id"]
                        account_type = "gcp"
                        print(
                            f"📌 未选择账号，使用默认 GCP 账号: {default_account.get('account_name')} (ID: {account_id_to_use})",
                            flush=True,
                        )

                    sys.stdout.flush()

                    # 3. ✅ 提前获取或创建 session_id（但不影响主流程）
                    session_id = None  # ✅ 默认为 None，即使失败也不影响查询
                    chat_storage = None

                    # ✅ 添加调试日志（使用 print 确保输出）
                    print(
                        f"📋 查询参数 - "
                        f"User: {user_id}, "
                        f"Org: {org_id}, "
                        f"Session(前端): {message_data.get('session_id')}",
                        flush=True,
                    )
                    logger.info(
                        f"📋 查询参数 - "
                        f"User: {user_id}, "
                        f"Org: {org_id}, "
                        f"Session(前端): {message_data.get('session_id')}"
                    )

                    try:
                        from ..services.chat_storage import get_chat_storage

                        chat_storage = get_chat_storage()

                        session_id = message_data.get("session_id")  # 从前端获取 session_id

                        # ✅ 如果是临时 ID（temp_ 开头），直接创建新会话
                        if session_id and session_id.startswith("temp_"):
                            logger.info(f"🆔 检测到临时ID，将创建新会话: {session_id}")
                            session_id = None

                        if session_id:
                            # 前端传递了真实的 session_id，验证并复用
                            try:
                                existing_session = chat_storage.get_session(session_id)
                                if existing_session and existing_session["user_id"] == user_id:
                                    logger.info(f"♻️  复用现有会话 - Session: {session_id}")
                                else:
                                    # Session 不存在或不属于当前用户，创建新Session
                                    logger.warning(
                                        f"⚠️ Session {session_id} 不存在或不属于用户 {user_id}，创建新Session"
                                    )
                                    session_id = None
                            except Exception as e:
                                logger.error(f"❌ 验证Session失败: {e}，将继续查询但不保存历史")
                                session_id = None

                        if not session_id:
                            # 创建新Session
                            session_title = query[:20] + "..." if len(query) > 20 else query
                            try:
                                session = chat_storage.create_session(
                                    user_id=user_id, org_id=org_id, title=session_title
                                )
                                session_id = session["id"]
                                logger.info(f"🆕 创建新会话 - Session: {session_id}")

                                # ✅ 立即通知前端新创建的 session_id
                                await manager.send_to_user(
                                    user_id,
                                    json.dumps(
                                        {
                                            "type": "session_created",
                                            "session_id": session_id,
                                            "query_id": query_id,
                                            "timestamp": time.time(),
                                        }
                                    ),
                                )
                                logger.info(f"📤 已发送 session_id 给前端: {session_id}")

                            except Exception as e:
                                logger.error(f"❌ 创建会话失败: {e}，将继续查询但不保存历史")
                                session_id = None

                    except Exception as e:
                        logger.error(f"❌ 会话管理初始化失败: {e}，将继续查询但不保存历史")
                        session_id = None
                        chat_storage = None

                    # ✅ 添加最终参数日志（使用 print 确保输出）
                    print(
                        f"📦 最终参数 - "
                        f"User: {user_id}, "
                        f"Org: {org_id}, "
                        f"Session: {session_id}, "
                        f"Account: {account_id_to_use}",
                        flush=True,
                    )
                    logger.info(
                        f"📦 最终参数 - "
                        f"User: {user_id}, "
                        f"Org: {org_id}, "
                        f"Session: {session_id}, "
                        f"Account: {account_id_to_use}"
                    )

                    # ✅ 关键修复：在获取凭证之前立即发送初始化状态消息
                    await manager.send_personal_message(
                        json.dumps(
                            {
                                "type": "status",
                                "status_type": "initializing",
                                "message": "正在初始化账号连接...",
                                "session_id": session_id,
                                "query_id": query_id,
                            }
                        ),
                        websocket,
                    )

                    # 4. 获取账号凭证和初始化客户端（根据账号类型）
                    gcp_account_info = None
                    credentials = None

                    try:
                        if account_type == "gcp":
                            # GCP 账号处理
                            gcp_account_info = gcp_credentials_provider.get_account_info(
                                account_id_to_use
                            )
                            if not gcp_account_info:
                                raise Exception(f"GCP 账号 {account_id_to_use} 不存在")

                            account_name = gcp_account_info.get("account_name", "Unknown")
                            project_id = gcp_account_info.get("project_id", "Unknown")
                            print(
                                f"✅ GCP 凭证获取成功 - {account_name} (项目: {project_id})",
                                flush=True,
                            )

                            # ✅ 注意：AgentCore Runtime 架构下，MCP 客户端由 Runtime 内部管理
                            # 不需要在这里初始化 GCP MCP 客户端
                            # 以下代码已废弃（client_manager 在 AgentCore 架构下不存在）

                            # TODO: 如果未来需要预初始化 GCP 凭证，在这里添加逻辑
                            logger.info(
                                f"✅ GCP 账号信息已加载 - {account_name} (项目: {project_id})"
                            )
                        else:
                            # AWS 账号处理
                            credentials = aws_credentials_provider.get_credentials(
                                account_id_to_use
                            )
                            print(
                                f"✅ AWS 凭证获取成功 - {credentials['alias']} ({credentials['account_id']})",
                                flush=True,
                            )
                    except Exception as e:
                        print(f"❌ 获取账号凭证/初始化失败: {e}", flush=True)
                        await manager.send_personal_message(
                            json.dumps(
                                {
                                    "type": "error",
                                    "content": f"账号初始化失败: {str(e)}",
                                    "timestamp": time.time(),
                                }
                            ),
                            websocket,
                        )
                        continue

                    # ✅ AgentCore Runtime 模式：MCP 客户端由 Runtime 内部创建
                    # FastAPI 只负责准备账号信息，传递给 Runtime

                    # 5. 构建查询（根据账号类型）
                    if account_type == "gcp":
                        enhanced_query = f"""用户查询: {query}

当前查询的 GCP 账号:
- 账号名称: {gcp_account_info.get("account_name", "Unknown")}
- GCP 项目 ID: {gcp_account_info.get("project_id", "Unknown")}
- 组织 ID: {gcp_account_info.get("organization_id", "Unknown")}

请使用当前 GCP 账号的数据进行分析。"""
                        account_display_name = gcp_account_info.get(
                            "account_name", account_id_to_use
                        )
                    else:
                        enhanced_query = f"""用户查询: {query}

当前查询的 AWS 账号:
- 账号别名: {credentials["alias"]}
- AWS 账号 ID: {credentials["account_id"]}

请使用当前 AWS 账号的数据进行分析。"""
                        account_display_name = credentials["alias"]

                    # 6. 执行查询（使用 AgentCore Runtime）
                    print(
                        f"🚀 开始查询 - Account: {account_display_name}, Query ID: {query_id}",
                        flush=True,
                    )
                    sys.stdout.flush()

                    # ========== 获取查询槽位（并发限制）==========
                    logger.info(f"🎫 准备获取查询槽位 - User: {username}, QueryID: {query_id}")
                    async with resource_manager.acquire_query_slot(user_id, query_slot_id):
                        logger.info(f"✅ 已获取查询槽位 - User: {username}, QueryID: {query_id}")

                        # ✅ 注册查询并获取取消事件
                        cancel_event = manager.register_query(
                            user_id,
                            query_id,
                            {
                                "content": query,
                                "account_id": account_id_to_use,
                                "account_type": account_type,
                            },
                        )
                        logger.debug(f"📝 查询已注册到取消系统 - User: {username}, QueryID: {query_id}")

                        # ✅ 保存用户消息（session_id 已在前面获取）
                        if chat_storage and session_id:
                            try:
                                chat_storage.save_message(
                                    session_id=session_id,
                                    user_id=user_id,
                                    message_type="user",
                                    content=query,
                                )
                                logger.info(f"💾 已保存用户消息 - Session: {session_id}")
                            except Exception as e:
                                logger.error(f"❌ 保存用户消息失败: {e}")

                        # ✅ 初始化 Runtime 客户端和解析器
                        client = AgentCoreClient(
                            runtime_arn=settings.AGENTCORE_RUNTIME_ARN,
                            region=settings.AGENTCORE_REGION,
                        )
                        parser = AgentCoreResponseParser(
                            session_id=session_id
                        )  # ✅ 传递 session_id

                        # ✅ 发送连接状态消息（MCP已初始化，准备调用Runtime）
                        await manager.send_personal_message(
                            json.dumps(
                                {
                                    "type": "status",
                                    "status_type": "processing",
                                    "message": f"已连接到 {account_display_name}，正在启动分析...",
                                    "session_id": session_id,
                                    "query_id": query_id,
                                }
                            ),
                            websocket,
                        )

                        # ✅ 调用 Runtime 并流式转发
                        assistant_response = []
                        event_count = 0
                        token_usage_data = None  # ✅ 收集 Token 统计数据

                        try:
                            logger.info(
                                f"🚀 开始调用 AgentCore Runtime - "
                                f"User: {username}, QueryID: {query_id}, "
                                f"Account: {account_id_to_use} ({account_type})"
                            )
                            print("🔍 DEBUG - 开始调用 Runtime streaming...", flush=True)

                            async for event in client.invoke_streaming(
                                prompt=enhanced_query,
                                account_id=account_id_to_use,
                                session_id=session_id,
                                user_id=user_id,
                                org_id=org_id,
                                account_type=account_type,  # ✅ 传递账号类型
                            ):
                                event_count += 1

                                # ✅ 优化：只打印事件计数，不打印完整内容（避免日志爆炸）
                                if event_count % 20 == 0 or event_count == 1:
                                    logger.info(f"📊 已处理 {event_count} 个事件")

                                # 检查取消
                                if cancel_event.is_set():
                                    logger.info(f"查询 {query_id} 被用户取消")
                                    await manager.send_personal_message(
                                        json.dumps(
                                            {
                                                "type": "generation_cancelled",
                                                "query_id": query_id,
                                                "message": "生成已取消",
                                            }
                                        ),
                                        websocket,
                                    )
                                    break

                                # 解析 SSE 事件 → WebSocket 消息
                                ws_messages = parser.parse_event(event)

                                # ✅ 优化：只在首次或关键事件时打印
                                if ws_messages and event_count == 1:
                                    event_types = [msg.get("type") for msg in ws_messages]
                                    logger.debug(f"首次事件类型: {event_types}")

                                # 发送给前端
                                for ws_msg in ws_messages:
                                    await manager.send_personal_message(
                                        json.dumps(ws_msg), websocket
                                    )

                                    # ✅ 收集 Token 统计数据
                                    if ws_msg.get("type") == "token_usage":
                                        token_usage_data = ws_msg.get("usage")
                                        logger.info(f"💾 收集到 Token 统计数据: {token_usage_data}")

                                    # 收集文本内容（包括错误消息）
                                    if ws_msg.get("type") == "chunk":
                                        assistant_response.append(ws_msg["content"])
                                        # ✅ 添加详细日志：检查chunk中是否包含invoke标签
                                        chunk_content = ws_msg["content"]
                                        if (
                                            "<invoke" in chunk_content
                                            or "tool" in chunk_content.lower()
                                        ):
                                            print(
                                                f"🔍 DEBUG - chunk包含特殊内容: {chunk_content[:100]}",
                                                flush=True,
                                            )
                                        else:
                                            print(
                                                f"📝 DEBUG - 收集chunk: {len(chunk_content)} 字符",
                                                flush=True,
                                            )
                                    elif ws_msg.get("type") == "error":
                                        assistant_response.append(ws_msg["content"])
                                        print(
                                            f"❌ DEBUG - 收集error: {ws_msg['content']}", flush=True
                                        )

                            response = "".join(assistant_response) if assistant_response else None

                            query_time = time.time() - query_start

                            # ✅ P0修复：检查响应是否为空
                            if not response or len(response.strip()) == 0:
                                # 响应为空，记录错误并发送失败complete
                                logger.error(
                                    f"❌ Runtime返回空响应 - "
                                    f"Query: {query_id}, "
                                    f"耗时: {query_time:.2f}秒, "
                                    f"事件数: {event_count}"
                                )

                                # 发送错误complete事件
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "complete",
                                        "success": False,
                                        "error": "服务器未返回响应，请重试或简化问题",
                                        "query_id": query_id,
                                        "timestamp": time.time(),
                                        "meta": {
                                            "query_time": query_time,
                                            "event_count": event_count,
                                        }
                                    }),
                                    websocket,
                                )
                            else:
                                # ✅ 保存助手响应消息到数据库
                                if chat_storage and session_id:
                                    try:
                                        # ✅ 使用辅助函数构建 metadata
                                        metadata_json = build_message_metadata(token_usage_data)

                                        await asyncio.get_event_loop().run_in_executor(
                                            None,
                                            chat_storage.save_message,
                                            session_id,
                                            user_id,
                                            "assistant",
                                            response.strip(),
                                            metadata_json,  # ✅ 传递 Token 统计
                                            None,  # tool_calls
                                            None,  # tool_results
                                            None,  # token_count
                                        )
                                        logger.info(
                                            f"💾 已保存助手响应 - Session: {session_id}, Length: {len(response)}, Token统计: {'有' if token_usage_data else '无'}"
                                        )
                                    except Exception as e:
                                        logger.error(f"❌ 保存助手响应失败: {e}")

                                # 发送成功complete事件
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "complete",
                                        "success": True,
                                        "query_id": query_id,
                                        "timestamp": time.time(),
                                        "meta": {
                                            "query_time": query_time,
                                            "event_count": event_count,
                                            "response_length": len(response),
                                        }
                                    }),
                                    websocket,
                                )

                            # Phase 4: 记录查询性能到指标收集器
                            from ..utils.metrics import get_metrics

                            metrics = get_metrics()
                            primary_account_id = account_ids[0] if account_ids else "unknown"
                            metrics.record_query_time(primary_account_id, query_time)

                            print(f"⏱️  查询耗时: {query_time:.2f}秒 ✅", flush=True)
                            print(
                                f"✅ Runtime响应完成，长度: {len(response) if response else 0}",
                                flush=True,
                            )
                            logger.info(f"查询 {query_id} 完成")

                        except Exception as e:
                            logger.error(
                                f"❌ Runtime 调用失败 - User: {username}, QueryID: {query_id}, Error: {e}",
                                exc_info=True
                            )
                            await manager.send_personal_message(
                                json.dumps(
                                    {
                                        "type": "error",
                                        "content": f"查询失败: {str(e)}",
                                        "query_id": query_id,
                                    }
                                ),
                                websocket,
                            )

                        finally:
                            # ✅ 查询完成或异常，注销查询
                            await manager.unregister_query(user_id, query_id)
                            print(f"🗑️  查询已清理 - Query ID: {query_id}", flush=True)

                except Exception as e:
                    print(f"❌ 处理请求时出错: {e}", flush=True)
                    import traceback

                    traceback.print_exc()

                    await manager.send_personal_message(
                        json.dumps(
                            {
                                "type": "error",
                                "content": f"处理请求失败: {str(e)}",
                                "timestamp": time.time(),
                            }
                        ),
                        websocket,
                    )

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket正常断开 - User: {username}")
        await manager.disconnect(user_id)
    except Exception as e:
        # ✅ P0: 捕获其他异常，确保资源清理
        logger.error(
            f"❌ WebSocket异常退出 - User: {username}, "
            f"UserID: {user_id}, Error: {type(e).__name__}: {e}"
        )
        import traceback
        logger.error(f"异常堆栈:\n{traceback.format_exc()}")

        # 尝试断开连接（可能失败，但要记录）
        try:
            await manager.disconnect(user_id)
        except Exception as disconnect_error:
            logger.error(f"❌ 断开连接时再次异常 - User: {username}: {disconnect_error}")
    finally:
        # ========== 清理资源管理器中的连接 ==========
        try:
            await resource_manager.unregister_websocket(connection_id)
            logger.info(f"🧹 资源清理完成 - User: {username}, ConnectionID: {connection_id}")
        except Exception as cleanup_error:
            logger.error(f"❌ 清理资源时异常 - User: {username}: {cleanup_error}")


# ============================================================
# 多账号串行查询函数（Agent 完全控制版）
# ============================================================


async def handle_multi_account_query_serial(
    websocket: WebSocket,
    user_id: str,
    org_id: str,
    username: str,
    query_id: str,
    query: str,
    account_ids: list[str],
    agent_manager,
    aws_credentials_provider,
    aws_account_storage,
    manager,
    resource_manager,
    session_id: str | None = None,  # ✅ 添加 session_id 参数
):
    """多账号串行查询处理器（Agent 完全控制版）

    核心设计：
    1. 串行查询每个账号
    2. 为每个账号构建特殊的增强查询
    3. 最后一个账号的查询会触发 Agent 输出结果列表和汇总（如果需要）
    """

    logger.info(f"🔀 开始多账号串行查询 - User: {username}, 账号数: {len(account_ids)}")

    # 注册查询（同步函数，返回 asyncio.Event）
    cancel_event = manager.register_query(
        user_id, query_id, {"content": query, "account_ids": account_ids, "mode": "serial"}
    )

    try:
        # 获取查询槽位（并发控制）
        query_slot_id = f"{user_id}:{uuid.uuid4()}"
        async with resource_manager.acquire_query_slot(user_id, query_slot_id):
            # 串行查询每个账号
            for index, account_id in enumerate(account_ids):
                # 检查是否取消
                if cancel_event.is_set():
                    logger.info(f"🛑 多账号查询已取消 - Query: {query_id}")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "content_delta",
                                "query_id": query_id,
                                "delta": "\n\n🛑 查询已取消\n",
                                "timestamp": time.time(),
                            }
                        )
                    )
                    break

                # 获取账号信息
                account = aws_account_storage.get_account(account_id, org_id)
                account_name = account.get("alias", account_id) if account else account_id
                aws_account_id = (
                    account.get("account_number", account_id) if account else account_id
                )

                logger.info(
                    f"📍 [{index + 1}/{len(account_ids)}] 查询账号: {account_name} ({aws_account_id})"
                )

                # 🔔 发送查询进度提示（只在非第一个账号前显示）
                if index > 0:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "content_delta",
                                "query_id": query_id,
                                "delta": f"\n\n📊 正在查询账号 {index + 1}/{len(account_ids)}: {account_name}...\n\n",
                                "timestamp": time.time(),
                            }
                        )
                    )

                # 构建账号特定的增强查询（与单账号格式完全一致）
                is_last_account = index == len(account_ids) - 1
                enhanced_query = build_account_specific_query(
                    original_query=query,
                    account_name=account_name,
                    aws_account_id=aws_account_id,
                    current_index=index + 1,
                    total_accounts=len(account_ids),
                    is_last=is_last_account,
                )

                try:
                    # 执行单账号查询（复用现有逻辑）
                    await query_single_account(
                        websocket=websocket,
                        user_id=user_id,
                        org_id=org_id,
                        account_id=account_id,
                        account_name=account_name,
                        query_id=f"{query_id}_account_{index}",
                        enhanced_query=enhanced_query,
                        agent_manager=agent_manager,
                        aws_credentials_provider=aws_credentials_provider,
                        manager=manager,
                        cancel_event=cancel_event,
                        session_id=session_id,  # 传递session_id支持Memory
                    )

                except Exception as e:
                    logger.error(
                        f"❌ [{index + 1}/{len(account_ids)}] {account_name} 查询失败: {e}"
                    )

                    # 发送错误消息
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "content_delta",
                                "query_id": query_id,
                                "delta": f"\n\n❌ [{account_name}] 查询失败: {str(e)}\n\n",
                                "timestamp": time.time(),
                            }
                        )
                    )

            # ✅ 所有账号查询完成后，发送完成提示
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "content_delta",
                        "query_id": query_id,
                        "delta": f"\n\n✅ 查询完成 ({len(account_ids)} 个账号)\n",
                        "timestamp": time.time(),
                    }
                )
            )

            # 发送完成事件
            await websocket.send_text(
                json.dumps(
                    {"type": "message_complete", "query_id": query_id, "timestamp": time.time()}
                )
            )

    except Exception as e:
        logger.error(f"❌ 多账号查询异常: {e}")
        import traceback

        traceback.print_exc()

        # 发送错误消息
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "query_id": query_id,
                    "message": f"多账号查询失败: {str(e)}",
                    "timestamp": time.time(),
                }
            )
        )

    finally:
        # 清理查询
        await manager.unregister_query(user_id, query_id)


def build_account_specific_query(
    original_query: str,
    account_name: str,
    aws_account_id: str,
    current_index: int,
    total_accounts: int,
    is_last: bool,
) -> str:
    """构建账号特定的增强查询

    ✅ 使用与单账号查询完全相同的格式，确保输出一致性
    ✅ 每个账号独立查询，不要求 Agent 生成汇总（因为它看不到其他账号结果）
    """

    # 所有账号使用完全相同的格式（与单账号查询一致）
    return f"""用户查询: {original_query}

当前查询的 AWS 账号:
- 账号别名: {account_name}
- AWS 账号 ID: {aws_account_id}

请使用当前 AWS 账号的数据进行分析。"""


async def query_single_account(
    websocket: WebSocket,
    user_id: str,
    org_id: str,
    account_id: str,
    account_name: str,
    query_id: str,
    enhanced_query: str,
    agent_manager,
    aws_credentials_provider,
    manager,
    cancel_event: asyncio.Event,
    session_id: str | None = None,
):
    """查询单个账号（使用 AgentCore Runtime）"""

    logger.debug(f"🔍 查询单个账号: {account_name} (ID: {account_id})")

    # ✅ 初始化 Runtime 客户端和解析器
    client = AgentCoreClient(
        runtime_arn=settings.AGENTCORE_RUNTIME_ARN, region=settings.AGENTCORE_REGION
    )
    parser = AgentCoreResponseParser(session_id=session_id)  # ✅ 传递 session_id

    # ✅ 获取 ChatStorage 实例（用于保存消息）
    from ..services.chat_storage import get_chat_storage

    chat_storage = get_chat_storage()

    # ✅ 创建或使用会话
    if not session_id:
        session_title = enhanced_query[:20] + "..." if len(enhanced_query) > 20 else enhanced_query
        try:
            session = chat_storage.create_session(
                user_id=user_id, org_id=org_id, title=session_title
            )
            session_id = session["id"]
            logger.info(f"💾 创建新会话 (多账号子查询) - Session: {session_id}")
        except Exception as e:
            logger.error(f"❌ 创建会话失败: {e}")
            session_id = None

    # ✅ 保存用户消息
    if chat_storage and session_id:
        try:
            chat_storage.save_message(
                session_id=session_id, user_id=user_id, message_type="user", content=enhanced_query
            )
            logger.info(f"💾 已保存用户消息 (多账号子查询) - Session: {session_id}")
        except Exception as e:
            logger.error(f"❌ 保存用户消息失败: {e}")

    # ✅ 调用 Runtime 并流式转发
    assistant_response = []
    token_usage_data = None  # ✅ 收集 Token 统计数据

    try:
        async for event in client.invoke_streaming(
            prompt=enhanced_query,
            account_id=account_id,
            session_id=session_id,
            user_id=user_id,
            org_id=org_id,
        ):
            # 检查取消
            if cancel_event.is_set():
                logger.info(f"子查询 {query_id} 被用户取消")
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "generation_cancelled",
                            "query_id": query_id,
                            "message": "生成已取消",
                        }
                    ),
                    websocket,
                )
                break

            # 解析 SSE 事件 → WebSocket 消息
            ws_messages = parser.parse_event(event)

            # 发送给前端
            for ws_msg in ws_messages:
                await manager.send_personal_message(json.dumps(ws_msg), websocket)

                # ✅ 收集 Token 统计数据
                if ws_msg.get("type") == "token_usage":
                    token_usage_data = ws_msg.get("usage")

                # 收集文本内容
                if ws_msg.get("type") == "chunk":
                    assistant_response.append(ws_msg["content"])

        response = "".join(assistant_response) if assistant_response else None

        # ✅ 保存助手响应
        if chat_storage and session_id and response:
            try:
                # ✅ 使用辅助函数构建 metadata
                metadata_json = build_message_metadata(token_usage_data)

                await asyncio.get_event_loop().run_in_executor(
                    None,
                    chat_storage.save_message,
                    session_id,
                    user_id,
                    "assistant",
                    response.strip(),
                    metadata_json,  # ✅ 传递 Token 统计
                    None,  # tool_calls
                    None,  # tool_results
                    None,  # token_count
                )
                logger.info(
                    f"💾 已保存助手响应 (多账号子查询) - Session: {session_id}, Length: {len(response)}, Token统计: {'有' if token_usage_data else '无'}"
                )
            except Exception as e:
                logger.error(f"❌ 保存助手响应失败: {e}")

        logger.info(f"✅ 账号 {account_name} 查询完成")

    except Exception as e:
        logger.error(f"Runtime 调用失败: {e}", exc_info=True)
        await manager.send_personal_message(
            json.dumps(
                {
                    "type": "error",
                    "content": f"账号 {account_name} 查询失败: {str(e)}",
                    "query_id": query_id,
                }
            ),
            websocket,
        )
        raise
