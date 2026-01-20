"""WebSocket 事件处理器 - 支持 Agent 工作流程展示

提供流式事件发送功能，包括：
- 思考过程 (thinking_start, thinking_step, thinking_end)
- 工具调用 (tool_call_start, tool_call_result, tool_call_error)
- 内容流式 (content_delta)
- 消息完成 (message_complete)
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket

import logging

logger = logging.getLogger(__name__)


class AgentWebSocketHandler:
    """Agent WebSocket 事件处理器

    负责将 Agent 的工作流程转换为前端可识别的流式事件

    **性能优化**: 使用消息批处理，减少网络往返，提升吞吐量
    """

    def __init__(
        self, websocket: WebSocket, enable_batching: bool = True, batch_interval: float = 0.05
    ):
        """初始化处理器

        Args:
            websocket: WebSocket 连接对象
            enable_batching: 是否启用批处理（默认True）
            batch_interval: 批处理间隔（秒，默认50ms - 平衡流畅度和性能）
        """
        self.websocket = websocket
        self.thinking_steps: list[str] = []
        self.tool_calls: dict[str, dict[str, Any]] = {}
        self.thinking_start_time: float | None = None

        # ✅ 批处理配置
        self.enable_batching = enable_batching
        self.batch_interval = batch_interval
        self._message_queue: list[dict[str, Any]] = []
        self._batch_task: asyncio.Task | None = None
        self._last_flush_time = time.time()
        self._queue_lock = asyncio.Lock()

        # ✅ 内容增量专用缓冲区（更激进的批处理）
        self._content_buffer: str = ""
        self._content_buffer_time: float = 0

    async def cleanup(self):
        """清理资源（取消批处理任务）"""
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
            logger.debug("✅ WebSocketHandler 批处理任务已清理")

    # ========== 状态提示消息（新增）==========

    async def send_status_message(
        self, status_type: str, message: str, estimated_seconds: int = None, details: list = None
    ):
        """发送状态提示消息（无进度条）

        Args:
            status_type: 状态类型 (initializing, ready, error)
            message: 状态描述
            estimated_seconds: 预计耗时（秒，可选）
            details: 详细信息列表（可选）
        """
        await self.send_event(
            "status",
            {
                "status_type": status_type,
                "message": message,
                "estimated_seconds": estimated_seconds,
                "details": details or [],
            },
        )
        logger.info(f"📊 状态: {message}")

    async def send_event(self, event_type: str, data: dict[str, Any] | None = None):
        """发送 WebSocket 事件到前端（支持批处理）

        Args:
            event_type: 事件类型
            data: 事件数据（可选）
        """
        message = {"type": event_type, "timestamp": datetime.utcnow().isoformat() + "Z"}

        if data:
            message.update(data)

        if self.enable_batching:
            await self._enqueue_message(message)
        else:
            # 直接发送（旧行为）
            await self.websocket.send_text(json.dumps(message))

    async def _enqueue_message(self, message: dict[str, Any]):
        """将消息加入批处理队列

        Args:
            message: 要发送的消息
        """
        async with self._queue_lock:
            self._message_queue.append(message)

            # 启动批处理任务（如果还没有）
            if self._batch_task is None or self._batch_task.done():
                self._batch_task = asyncio.create_task(self._batch_sender())

    async def _batch_sender(self):
        """批处理发送任务（后台运行）"""
        try:
            while True:
                await asyncio.sleep(self.batch_interval)

                async with self._queue_lock:
                    if not self._message_queue:
                        # 队列为空，退出任务
                        break

                    # 取出所有待发送消息
                    messages_to_send = self._message_queue.copy()
                    self._message_queue.clear()

                # ✅ 检查连接状态后再发送
                try:
                    # 检查连接是否已关闭
                    if self.websocket.client_state.value >= 2:  # CLOSING(2) or CLOSED(3)
                        logger.warning("⚠️  WebSocket 已关闭，停止批处理任务")
                        break

                    # 批量发送
                    if len(messages_to_send) == 1:
                        # 单条消息直接发送
                        await self.websocket.send_text(json.dumps(messages_to_send[0]))
                    else:
                        # 多条消息批量发送
                        batch_message = {
                            "type": "batch",
                            "messages": messages_to_send,
                            "count": len(messages_to_send),
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        await self.websocket.send_text(json.dumps(batch_message))

                    self._last_flush_time = time.time()
                except RuntimeError as e:
                    if "close message has been sent" in str(e):
                        logger.warning("⚠️  WebSocket 连接已关闭，停止批处理任务")
                        break
                    else:
                        raise

        except asyncio.CancelledError:
            # 任务被取消（正常情况，如 WebSocket 断开）
            logger.info("📌 批处理发送任务被取消")
        except Exception as e:
            # 批处理任务异常，记录并退出
            logger.error(f"批处理发送任务异常: {e}", exc_info=True)

    async def flush(self):
        """立即刷新队列中的所有消息"""
        if not self.enable_batching:
            return

        async with self._queue_lock:
            if not self._message_queue:
                return

            messages_to_send = self._message_queue.copy()
            self._message_queue.clear()

        # ✅ P0: 检查 WebSocket 连接状态（刷新页面时优雅跳过）
        try:
            # 检查连接是否已关闭
            if self.websocket.client_state.value >= 2:  # CLOSING(2) or CLOSED(3)
                logger.debug("⏭️  WebSocket 已关闭，跳过消息发送（正常，用户刷新页面）")
                return

            # 立即发送
            if len(messages_to_send) == 1:
                await self.websocket.send_text(json.dumps(messages_to_send[0]))
            elif len(messages_to_send) > 1:
                batch_message = {
                    "type": "batch",
                    "messages": messages_to_send,
                    "count": len(messages_to_send),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                await self.websocket.send_text(json.dumps(batch_message))

            self._last_flush_time = time.time()
        except RuntimeError as e:
            if "close message has been sent" in str(e):
                logger.debug("⏭️  WebSocket 连接已关闭，跳过发送（正常，用户刷新页面）")
            else:
                raise

    # ========== 思考过程事件 ==========

    async def thinking_start(self):
        """开始思考"""
        self.thinking_start_time = time.time()
        self.thinking_steps = []
        await self.send_event("thinking_start")

    async def thinking_step(self, content: str, step_number: int | None = None):
        """添加思考步骤

        Args:
            content: 思考内容
            step_number: 步骤编号（可选，自动递增）
        """
        if step_number is None:
            step_number = len(self.thinking_steps) + 1

        self.thinking_steps.append(content)

        await self.send_event("thinking_step", {"step": step_number, "content": content})

    async def thinking_end(self):
        """结束思考"""
        duration = 0.0
        if self.thinking_start_time:
            duration = time.time() - self.thinking_start_time

        print(f"🧠 [思考结束] 耗时: {round(duration, 2)}s", flush=True)

        await self.send_event("thinking_end", {"duration": round(duration, 2)})

    # ========== 工具调用事件 ==========

    async def tool_call_start(
        self,
        tool_name: str,
        description: str,
        args: dict[str, Any],
        tool_id: str | None = None,
        start_time: float | None = None,  # ✨ 新增：允许传递真实的开始时间
    ) -> str:
        """开始工具调用

        Args:
            tool_name: 工具名称
            description: 工具调用描述
            args: 工具参数
            tool_id: 工具调用 ID（可选，自动生成）
            start_time: 工具调用的真实开始时间（可选，用于延迟发送时保留真实时长）

        Returns:
            str: 工具调用 ID
        """
        if tool_id is None:
            tool_id = f"call_{uuid.uuid4().hex[:8]}"

        # 记录工具调用开始时间（使用传入的时间或当前时间）
        self.tool_calls[tool_id] = {
            "start_time": start_time if start_time is not None else time.time(),
            "name": tool_name,
        }

        # 🔍 诊断日志
        print("📤 [WebSocket] 发送 tool_call_start 事件:")
        print(f"  - tool_id: {tool_id}")
        print(f"  - tool_name: {tool_name}")
        print(f"  - args: {args}")
        print(f"  - args type: {type(args)}")
        print(f"  - args empty: {not args}")

        await self.send_event(
            "tool_call_start",
            {"tool_id": tool_id, "tool_name": tool_name, "description": description, "args": args},
        )

        return tool_id

    async def tool_call_progress(self, tool_id: str, status: str):
        """更新工具调用进度

        Args:
            tool_id: 工具调用 ID
            status: 进度状态
        """
        await self.send_event("tool_call_progress", {"tool_id": tool_id, "status": status})

    async def tool_call_result(self, tool_id: str, result: Any):
        """工具调用成功

        Args:
            tool_id: 工具调用 ID
            result: 工具返回结果
        """
        duration = 0.0
        if tool_id in self.tool_calls:
            start_time = self.tool_calls[tool_id]["start_time"]
            duration = time.time() - start_time

        await self.send_event(
            "tool_call_result",
            {"tool_id": tool_id, "result": result, "duration": round(duration, 2)},
        )

    async def tool_call_error(self, tool_id: str, error: str):
        """工具调用失败

        Args:
            tool_id: 工具调用 ID
            error: 错误信息
        """
        await self.send_event("tool_call_error", {"tool_id": tool_id, "error": error})

    # ========== 内容流式事件 ==========

    async def content_delta(self, delta: str):
        """发送内容增量（立即发送 - 2025最佳实践）

        Args:
            delta: 内容片段
        """
        # ✅ 立即发送，不缓冲
        # 前端使用 requestAnimationFrame 自动合并，后端保持简单高效
        await self.send_event("content_delta", {"delta": delta})

    async def content_stream(self, content: str, chunk_size: int = 10, delay: float = 0.02):
        """流式发送内容（模拟打字机效果）

        Args:
            content: 完整内容
            chunk_size: 每次发送的字符数
            delay: 每次发送间隔（秒）
        """
        import asyncio

        for i in range(0, len(content), chunk_size):
            chunk = content[i : i + chunk_size]
            await self.content_delta(chunk)
            if i + chunk_size < len(content):  # 最后一次不延迟
                await asyncio.sleep(delay)

    # ========== 控制事件 ==========

    async def message_complete(self):
        """消息完成"""
        # ✅ 先刷新剩余的内容缓冲区
        if self._content_buffer:
            await self.send_event("content_delta", {"delta": self._content_buffer})
            self._content_buffer = ""
            self._content_buffer_time = 0

        await self.send_event("message_complete")
        # 立即刷新，确保完成消息及时到达
        await self.flush()

    async def error(self, error: str):
        """发送错误

        Args:
            error: 错误信息
        """
        await self.send_event("error", {"error": error})
        # 立即刷新，确保错误消息及时到达
        await self.flush()

    # ✅ 新增: 生成取消事件
    async def generation_cancelled(
        self, reason: str = "User stopped generation", query_id: str | None = None
    ):
        """发送生成取消事件

        Args:
            reason: 取消原因
            query_id: 查询ID（可选）
        """
        event_data = {"reason": reason}
        if query_id:
            event_data["query_id"] = query_id

        await self.send_event("generation_cancelled", event_data)
        await self.flush()  # 立即刷新，确保取消消息及时到达

    # ========== 向后兼容的旧格式事件 ==========

    async def send_thinking(self, content: str):
        """发送思考消息（旧格式，向后兼容）

        Args:
            content: 思考内容
        """
        await self.send_event("thinking", {"content": content})

    async def send_response(self, content: str):
        """发送响应消息（旧格式，向后兼容）

        Args:
            content: 响应内容
        """
        await self.send_event("response", {"content": content})

    # ========== AWS API 确认相关事件 ==========

    async def request_confirmation(
        self,
        tool_name: str,
        arguments: dict,
        confirmation_id: str,
        title: str,
        description: str,
        warning: str,
        risk_level: str,
        timeout_seconds: int = 300,
    ):
        """请求用户确认 AWS API 操作

        发送确认请求到前端，等待用户响应。

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            confirmation_id: 确认请求 ID
            title: 确认标题
            description: 操作描述
            warning: 风险警告
            risk_level: 风险等级 (low/medium/high)
            timeout_seconds: 超时时间（秒）
        """
        await self.send_event(
            "confirmation_required",
            {
                "confirmation_id": confirmation_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "title": title,
                "description": description,
                "warning": warning,
                "risk_level": risk_level,
                "timeout_seconds": timeout_seconds,
            },
        )

    async def confirmation_approved(self, confirmation_id: str):
        """确认已批准

        Args:
            confirmation_id: 确认请求 ID
        """
        await self.send_event("confirmation_approved", {"confirmation_id": confirmation_id})

    async def confirmation_rejected(self, confirmation_id: str, reason: str = "用户拒绝"):
        """确认被拒绝

        Args:
            confirmation_id: 确认请求 ID
            reason: 拒绝原因
        """
        await self.send_event(
            "confirmation_rejected", {"confirmation_id": confirmation_id, "reason": reason}
        )

    async def confirmation_timeout(self, confirmation_id: str):
        """确认超时

        Args:
            confirmation_id: 确认请求 ID
        """
        await self.send_event("confirmation_timeout", {"confirmation_id": confirmation_id})


# ========== 工具函数 ==========


def extract_tool_info_from_strands_event(event: Any) -> dict[str, Any] | None:
    """从 Strands Agent 事件中提取工具信息

    Args:
        event: Strands Agent 事件对象

    Returns:
        Optional[Dict]: 工具信息字典，如果不是工具调用则返回 None
        {
            "tool_name": str,
            "description": str,
            "args": dict,
            "result": Any (optional)
        }
    """
    # 这个函数需要根据实际的 Strands Agent 事件格式来实现
    # 当前是占位符实现

    if not hasattr(event, "type"):
        return None

    if event.type == "tool_call":
        return {
            "tool_name": getattr(event, "tool_name", "unknown_tool"),
            "description": getattr(event, "description", ""),
            "args": getattr(event, "args", {}),
        }

    if event.type == "tool_result":
        return {"result": getattr(event, "result", None)}

    return None


def generate_tool_description(tool_name: str, args: dict[str, Any]) -> str:
    """生成工具调用描述

    Args:
        tool_name: 工具名称
        args: 工具参数

    Returns:
        str: 人类可读的工具调用描述
    """
    # 针对常见工具生成友好的描述
    descriptions = {
        "get_cost_and_usage": "查询 AWS Cost Explorer 成本数据",
        "get_cost_forecast": "获取 AWS 成本预测",
        "list_cloudtrail_events": "查询 CloudTrail 事件日志",
        "analyze_cost_anomalies": "分析成本异常",
        "get_savings_plans_recommendations": "获取 Savings Plans 推荐",
    }

    base_desc = descriptions.get(tool_name, f"调用 {tool_name} 工具")

    # 添加参数细节
    if "time_period" in args:
        time_period = args["time_period"]
        if isinstance(time_period, dict):
            start = time_period.get("start", "")
            end = time_period.get("end", "")
            if start and end:
                base_desc += f" (时间范围: {start} 至 {end})"

    return base_desc

    # ========== AWS API 确认相关事件 ==========

    async def request_confirmation(
        self,
        tool_name: str,
        arguments: dict,
        confirmation_id: str,
        title: str,
        description: str,
        warning: str,
        risk_level: str,
        timeout_seconds: int = 300,
    ):
        """请求用户确认 AWS API 操作

        发送确认请求到前端，等待用户响应。

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            confirmation_id: 确认请求 ID
            title: 确认标题
            description: 操作描述
            warning: 风险警告
            risk_level: 风险等级 (low/medium/high)
            timeout_seconds: 超时时间（秒）
        """
        await self.send_event(
            "confirmation_required",
            {
                "confirmation_id": confirmation_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "title": title,
                "description": description,
                "warning": warning,
                "risk_level": risk_level,
                "timeout_seconds": timeout_seconds,
            },
        )

    async def confirmation_approved(self, confirmation_id: str):
        """确认已批准

        Args:
            confirmation_id: 确认请求 ID
        """
        await self.send_event("confirmation_approved", {"confirmation_id": confirmation_id})

    async def confirmation_rejected(self, confirmation_id: str, reason: str = "用户拒绝"):
        """确认被拒绝

        Args:
            confirmation_id: 确认请求 ID
            reason: 拒绝原因
        """
        await self.send_event(
            "confirmation_rejected", {"confirmation_id": confirmation_id, "reason": reason}
        )

    async def confirmation_timeout(self, confirmation_id: str):
        """确认超时

        Args:
            confirmation_id: 确认请求 ID
        """
        await self.send_event("confirmation_timeout", {"confirmation_id": confirmation_id})
