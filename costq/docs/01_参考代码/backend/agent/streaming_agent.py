"""流式 Agent 包装器 - 支持工作流程展示

包装 Strands Agent，在执行过程中发送流式事件到前端。
使用 Strands Agent 的 stream_async 方法捕获真实的工具调用事件。
"""

import asyncio
import logging
import time
from typing import Any

from strands import Agent

# 引入 ChatStorage 依赖
# 注意：这里使用 TYPE_CHECKING 来避免循环导入，或者直接导入类
# 由于 ChatStoragePostgreSQL 在 backend/services/chat_storage_postgresql.py 中定义
# 且该文件没有导入 streaming_agent，所以直接导入应该是安全的
from backend.services.chat_storage_postgresql import ChatStoragePostgreSQL

logger = logging.getLogger(__name__)


class StreamingAgentWrapper:
    """流式 Agent 包装器

    在 Strands Agent 执行过程中发送流式事件到前端。
    核心改进：使用 stream_async 捕获真实的工具调用事件。
    支持查询取消功能。
    """

    def __init__(
        self,
        agent: Agent,
        websocket_handler: Any,
        cancel_event: asyncio.Event | None = None,
        query_id: str | None = None,
        chat_storage: ChatStoragePostgreSQL | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ):
        """初始化包装器

        Args:
            agent: Strands Agent 实例
            websocket_handler: WebSocket 事件处理器
            cancel_event: 取消事件（可选）
            query_id: 查询ID（可选）
            chat_storage: 聊天存储服务（可选）
            session_id: 会话ID（可选）
            user_id: 用户ID（可选）
        """
        self.agent = agent
        self.ws = websocket_handler

        # ✅ 新增: 取消控制
        self.cancel_event = cancel_event or asyncio.Event()
        self.query_id = query_id
        self.request_state = {}  # Strands Agent 的 request_state

        # ✅ 聊天记录存储
        self.chat_storage = chat_storage
        self.session_id = session_id
        self.user_id = user_id

        # 工具调用状态跟踪
        self.active_tool_calls: dict[str, dict[str, Any]] = {}  # toolUseId -> tool_info

        # ✅ Phase 2.1: Agent 执行任务（用于强制取消）
        self.agent_task: asyncio.Task | None = None

        # ✅ Phase 2.3: 工具调用超时设置（秒）
        self.tool_call_timeout = 60  # 默认60秒超时

    async def process_query(
        self, query: str, account_info: dict[str, Any], account_type: str = "aws"
    ) -> str:
        """处理查询并发送流式事件

        Args:
            query: 用户查询
            account_info: 账号信息
            account_type: 账号类型 ('aws' 或 'gcp')

        Returns:
            str: Agent 的最终响应
        """
        try:
            # ========== 0. 凭证刷新已由 RefreshableSession 自动处理 ==========
            # ✅ 不再需要手动刷新凭证
            # boto3 的 DeferredRefreshableCredentials 会在凭证过期前自动刷新

            # ========== 1. 思考过程 ==========
            await self._send_thinking_process(query, account_info, account_type)

            # ========== 2. 执行 Agent 并处理事件流 ==========
            # Phase 2.1: 包装为 asyncio.Task 以支持强制取消
            self.agent_task = asyncio.create_task(
                self._execute_with_event_stream(query)
            )

            try:
                final_response = await self.agent_task
            except asyncio.CancelledError:
                logger.info(f"🛑 Agent Task 已被取消 - Query: {self.query_id}")
                await self.ws.generation_cancelled("Task was cancelled", self.query_id)
                return ""  # 返回空响应

            # ========== 3. 完成 ==========
            await self.ws.message_complete()

            return final_response

        except asyncio.CancelledError:
            # Task 被取消时的清理
            logger.info(f"🛑 Query 处理已取消 - Query: {self.query_id}")
            raise
        except Exception as e:
            logger.error(f"流式 Agent 执行失败: {e}")
            await self.ws.error(str(e))
            raise
        finally:
            # Phase 2.2: 无论成功、失败还是取消，都清理资源
            await self.cleanup_resources()

    async def _send_thinking_process(
        self, query: str, account_info: dict[str, Any], account_type: str
    ):
        """发送思考过程

        Args:
            query: 用户查询
            account_info: 账号信息
            account_type: 账号类型
        """
        await self.ws.thinking_start()

        # 思考步骤（基于查询内容智能生成）
        steps = self._generate_thinking_steps(query, account_type)

        for i, step in enumerate(steps, 1):
            await self.ws.thinking_step(step, i)
            # 移除延迟，确保思考步骤在工具调用之前到达前端

        await self.ws.thinking_end()

    def _generate_thinking_steps(self, query: str, account_type: str) -> list[str]:
        """根据查询生成思考步骤

        Args:
            query: 用户查询
            account_type: 账号类型

        Returns:
            list[str]: 思考步骤列表
        """
        query_lower = query.lower()
        steps = []

        # 步骤 1: 分析查询
        steps.append(
            f"分析用户查询：{query[:50]}..."
            if len(query) > 50
            else f"分析用户查询：{query}"
        )

        # 步骤 2: 确定查询类型和工具
        if any(
            keyword in query_lower
            for keyword in ["成本", "cost", "费用", "花费", "账单"]
        ):
            if account_type == "aws":
                steps.append("识别为成本查询，准备使用 AWS Cost Explorer 工具")
            else:
                steps.append("识别为成本查询，准备使用 GCP Billing 工具")
        elif any(
            keyword in query_lower for keyword in ["日志", "log", "cloudtrail", "事件"]
        ):
            steps.append("识别为日志查询，准备使用 CloudTrail 工具")
        elif any(
            keyword in query_lower
            for keyword in ["优化", "optimize", "推荐", "recommend"]
        ):
            steps.append("识别为优化建议查询，准备使用成本优化工具")
        else:
            steps.append("分析查询意图，选择合适的工具")

        # 步骤 3: 确定查询参数
        if any(
            keyword in query_lower
            for keyword in ["本月", "这个月", "this month", "当月"]
        ):
            steps.append("确定时间范围：本月（当前月份）")
        elif any(
            keyword in query_lower for keyword in ["上月", "上个月", "last month"]
        ):
            steps.append("确定时间范围：上月")
        elif any(keyword in query_lower for keyword in ["今天", "today", "当天"]):
            steps.append("确定时间范围：今天")
        else:
            steps.append("确定查询参数和时间范围")

        # 步骤 4: 规划回答
        steps.append("规划回答结构：数据分析 + 可视化 + 优化建议")

        return steps

    def cancel(self):
        """外部调用此方法取消生成

        Phase 2.1: 支持强制取消 asyncio.Task
        """
        logger.info(f"🛑 收到取消请求 - Query: {self.query_id}")

        # 1. 设置取消事件（Phase 1 机制）
        self.cancel_event.set()
        self.request_state["stop_event_loop"] = True

        # 2. 强制取消 asyncio.Task（Phase 2.1 新增）
        if self.agent_task and not self.agent_task.done():
            logger.info(f"🛑 强制取消 Agent Task - Query: {self.query_id}")
            self.agent_task.cancel()

    async def cleanup_resources(self):
        """Phase 2.2: 清理资源

        在查询完成或取消后调用，释放所有相关资源
        """
        logger.info(f"🧹 开始清理资源 - Query: {self.query_id}")

        try:
            # 1. 清理活跃的工具调用
            if self.active_tool_calls:
                logger.debug(f"  清理 {len(self.active_tool_calls)} 个活跃工具调用")
                self.active_tool_calls.clear()

            # 2. 取消并等待 Agent Task（如果还在运行）
            if self.agent_task and not self.agent_task.done():
                logger.debug("  取消 Agent Task")
                self.agent_task.cancel()
                try:
                    await asyncio.wait_for(self.agent_task, timeout=2.0)
                except (TimeoutError, asyncio.CancelledError):
                    pass  # 预期的异常

            # 3. 清理 request_state
            if self.request_state:
                logger.debug("  清理 request_state")
                self.request_state.clear()

            # 4. 重置取消事件
            if self.cancel_event.is_set():
                self.cancel_event.clear()

            logger.info(f"✅ 资源清理完成 - Query: {self.query_id}")

        except Exception as e:
            logger.error(f"❌ 资源清理失败 - Query: {self.query_id}, Error: {e}")

    async def _execute_with_event_stream(self, query: str) -> str:
        """使用 stream_async 执行 Agent 并处理事件流

        这是核心方法，捕获 Strands Agent 的真实事件流并转发到前端。

        Args:
            query: 用户查询

        Returns:
            str: 最终响应文本
        """
        final_text = ""

        # 重置取消标志
        self.request_state["stop_event_loop"] = False

        # ⭐ Prompt Caching 指标
        cache_metrics = {
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_hit": False,
        }

        try:
            logger.info(f"🚀 开始流式执行 Agent: {query[:50]}...")

            # ✅ 使用 invocation_state 替代已废弃的 request_state
            async for event in self.agent.stream_async(
                query, invocation_state=self.request_state
            ):
                # 🔍 调试：记录所有事件类型
                event_types = list(event.keys())
                logger.debug(f"🎯 [事件] 类型: {event_types}")

                # ✅ 在每个事件之间检查取消标志
                if self.cancel_event.is_set() or self.request_state.get(
                    "stop_event_loop"
                ):
                    logger.info(f"🛑 检测到取消信号，停止生成 - Query: {self.query_id}")
                    await self.ws.generation_cancelled(
                        "User stopped generation", self.query_id
                    )
                    break

                # ========== 处理不同类型的事件 ==========

                # 1. 初始化事件
                if "init_event_loop" in event:
                    # logger.debug("📍 事件: 初始化事件循环")  # 已静默
                    continue

                # 2. 开始事件
                if "start" in event:
                    # logger.debug("📍 事件: 开始")  # 已静默
                    continue

                if "start_event_loop" in event:
                    # logger.debug("📍 事件: 事件循环开始")  # 已静默
                    continue

                # 3. 工具调用事件（重要！）
                if "current_tool_use" in event:
                    await self._handle_tool_use_event(event)
                    continue

                # 4. 工具结果事件（重要！）
                if "tool_result" in event:
                    await self._handle_tool_result_event(event)
                    continue

                # 5. 工具流事件
                if "tool_stream_event" in event:
                    await self._handle_tool_stream_event(event)
                    continue

                # 6. 文本流式输出（重要！）
                if "data" in event and "current_tool_use" not in event:
                    text_chunk = event.get("data", "")
                    final_text += text_chunk

                    logger.debug(
                        f"📝 [文本输出] 长度: {len(text_chunk)}, 累计: {len(final_text)}"
                    )

                    # 发送文本块到前端
                    await self.ws.content_delta(text_chunk)
                    continue

                # 7. 消息事件（可能包含工具结果）
                if "message" in event:
                    # logger.debug("📍 事件: 消息")  # 已静默
                    # 检查消息中是否包含工具结果
                    message_data = event.get("message", {})
                    if isinstance(message_data, dict):
                        content = message_data.get("content", [])
                        # 检查 content 中的 toolResult
                        for item in content:
                            if isinstance(item, dict) and "toolResult" in item:
                                await self._handle_tool_result_from_message(
                                    item["toolResult"]
                                )
                    continue

                # 8. 最终结果事件
                if "result" in event:
                    # logger.debug("📍 事件: 最终结果")  # 已静默
                    result = event.get("result")
                    if result:
                        logger.info("✅ Agent 执行完成")

                        # ⭐ 提取缓存指标（从 metrics.accumulated_usage）
                        if hasattr(result, "metrics") and result.metrics:
                            metrics = result.metrics
                            if hasattr(metrics, "accumulated_usage"):
                                usage = metrics.accumulated_usage
                                # Strands SDK 使用驼峰命名
                                cache_metrics["cache_read_tokens"] = usage.get(
                                    "cacheReadInputTokens", 0
                                )
                                cache_metrics["cache_write_tokens"] = usage.get(
                                    "cacheWriteInputTokens", 0
                                )
                                cache_metrics["input_tokens"] = usage.get(
                                    "inputTokens", 0
                                )
                                cache_metrics["output_tokens"] = usage.get(
                                    "outputTokens", 0
                                )
                                cache_metrics["cache_hit"] = (
                                    cache_metrics["cache_read_tokens"] > 0
                                )
                                logger.debug(f"📊 缓存指标提取成功: {cache_metrics}")
                            else:
                                logger.warning("⚠️  Metrics 对象没有 accumulated_usage")
                        else:
                            logger.warning("⚠️  Result 对象没有 metrics 属性")
                    continue

                # 9. 其他未知事件
                # logger.debug(f"📍 未处理的事件类型: {list(event.keys())}")  # 已静默 - 大量重复日志

            # ⭐ 记录 Prompt Caching 指标
            await self._log_cache_metrics(cache_metrics)

            logger.info(f"✅ 流式执行完成，最终响应长度: {len(final_text)}")
            return final_text

        except Exception as e:
            logger.error(f"❌ 流式执行失败: {e}", exc_info=True)
            raise

    async def _handle_tool_use_event(self, event: dict[str, Any]):
        """处理工具调用事件

        当 Agent 准备调用工具时触发。
        事件结构：
        {
            "current_tool_use": {
                "name": "get_cost_and_usage",
                "toolUseId": "tooluse_xxx",
                "input": {...}  # 工具参数（可能逐步更新）
            },
            "delta": {...}
        }

        Args:
            event: 工具调用事件
        """
        tool_use = event.get("current_tool_use", {})
        tool_use_id = tool_use.get("toolUseId")
        tool_name = tool_use.get("name")
        tool_input = tool_use.get("input", {})

        # 只在新工具调用时记录日志
        # logger.info(f"🔧 工具调用: {tool_name} (ID: {tool_use_id})")  # 已静默 - 重复日志

        # 检查是否是新的工具调用
        if tool_use_id not in self.active_tool_calls:
            # 新工具调用 - 先记录，但延迟发送到前端
            logger.info(f"🔧 工具调用: {tool_name}")
            # ⚠️ 性能优化：初始参数通常为空，降低为 DEBUG 级别
            if tool_input:  # 只在参数非空时输出
                logger.debug(f"  📋 [诊断] 初始参数: {tool_input}")

            # 提取工具描述（如果有）
            description = f"调用 {tool_name} 工具"

            # ✨ 修复：记录工具调用状态，但先不发送到前端
            self.active_tool_calls[tool_use_id] = {
                "name": tool_name,
                "description": description,
                "frontend_id": None,  # 暂不生成
                "start_time": time.time(),  # 使用 time.time() 而不是 asyncio.get_event_loop().time()
                "input": tool_input,
                "sent_to_frontend": False,  # 标记未发送
                "confirmation_required": False,  # AWS API 确认标记
                "confirmation_approved": None,  # 确认结果
            }
        else:
            # 工具调用更新（参数可能在流式更新）
            # ⚠️ 性能优化：降低日志级别，避免每次参数更新都输出 INFO 日志
            logger.debug(
                f"  🔄 [诊断] 工具调用参数更新: {tool_name}"
            )  # 🔍 诊断日志（DEBUG级别）
            logger.debug(
                f"  📋 [诊断] 更新后的参数: {tool_input}"
            )  # 🔍 诊断日志（DEBUG级别）

            # 更新参数
            self.active_tool_calls[tool_use_id]["input"] = tool_input

            # ✨ 修复：检查参数是否完整，如果完整且未发送，则发送到前端
            if not self.active_tool_calls[tool_use_id]["sent_to_frontend"]:
                # 判断参数是否完整（不为空字符串或空字典）
                is_complete = self._is_tool_input_complete(tool_input)

                if is_complete:
                    logger.info("  ✅ [修复] 参数已完整，准备发送到前端")

                    # 🔐 AWS API 安全检查
                    needs_confirmation = await self._check_aws_api_confirmation(
                        tool_name, tool_input, tool_use_id
                    )

                    if needs_confirmation:
                        # 需要确认，暂时不发送 tool_call_start
                        logger.info("  ⏸️  工具需要用户确认，等待响应...")
                        self.active_tool_calls[tool_use_id][
                            "confirmation_required"
                        ] = True
                        # 注意：不设置 sent_to_frontend = True，等确认后再发送
                    else:
                        # 不需要确认，正常发送
                        frontend_tool_id = await self.ws.tool_call_start(
                            tool_name=self.active_tool_calls[tool_use_id]["name"],
                            description=self.active_tool_calls[tool_use_id][
                                "description"
                            ],
                            args=tool_input,
                        )

                        # 更新状态
                        self.active_tool_calls[tool_use_id][
                            "frontend_id"
                        ] = frontend_tool_id
                        self.active_tool_calls[tool_use_id]["sent_to_frontend"] = True

    async def _handle_tool_result_event(self, event: dict[str, Any]):
        """处理工具结果事件

        当工具调用完成并返回结果时触发。
        事件结构：
        {
            "tool_result": {
                "toolUseId": "tooluse_xxx",
                "content": [
                    {"json": {...}} 或 {"text": "..."}
                ]
            }
        }

        Args:
            event: 工具结果事件
        """
        tool_result = event.get("tool_result", {})
        tool_use_id = tool_result.get("toolUseId")
        content = tool_result.get("content", [])

        logger.info(f"✅ 工具结果: {tool_use_id}")

        # 查找对应的工具调用
        if tool_use_id in self.active_tool_calls:
            tool_info = self.active_tool_calls[tool_use_id]
            frontend_id = tool_info.get("frontend_id")

            # ✨ 修复：如果工具还未发送到前端（参数不完整），先发送
            if frontend_id is None and not tool_info.get("sent_to_frontend", False):
                logger.warning(
                    f"  ⚠️  工具结果到达但工具未发送到前端，立即发送（参数: {tool_info['input']}）"
                )

                # 发送工具调用到前端（即使参数可能不完整）
                # ✨ 修复：传递真实的开始时间，确保 duration 计算正确
                frontend_id = await self.ws.tool_call_start(
                    tool_name=tool_info["name"],
                    description=tool_info.get(
                        "description", f"调用 {tool_info['name']} 工具"
                    ),
                    args=tool_info["input"],
                    start_time=tool_info.get("start_time"),  # 传递真实的开始时间
                )

                # 更新状态
                tool_info["frontend_id"] = frontend_id
                tool_info["sent_to_frontend"] = True

            # 提取结果数据
            result_data = self._extract_tool_result_data(content)

            logger.info(f"  📊 结果数据: {str(result_data)[:100]}...")

            # 发送到前端（只有在有 frontend_id 的情况下）
            if frontend_id:
                await self.ws.tool_call_result(frontend_id, result_data)
            else:
                logger.error("  ❌ 无法发送工具结果：frontend_id 为 None")

            # 清理已完成的工具调用
            del self.active_tool_calls[tool_use_id]
        else:
            logger.warning(f"⚠️  收到未知工具的结果: {tool_use_id}")

    async def _handle_tool_stream_event(self, event: dict[str, Any]):
        """处理工具流事件

        某些工具可能在执行过程中产生流式输出。

        Args:
            event: 工具流事件
        """
        tool_stream = event.get("tool_stream_event", {})
        tool_use = tool_stream.get("tool_use", {})
        stream_data = tool_stream.get("data")

        tool_use_id = tool_use.get("toolUseId")

        logger.debug(f"🌊 工具流事件: {tool_use_id} -> {str(stream_data)[:50]}...")

        # 可选：如果前端需要工具的流式输出，可以在这里转发
        # 目前大多数 MCP 工具不产生流式输出，所以暂时忽略

    def _extract_tool_result_data(self, content: list) -> dict[str, Any]:
        """从工具结果内容中提取数据

        Args:
            content: 工具结果内容列表

        Returns:
            Dict: 提取的结果数据
        """
        if not content:
            return {"status": "success", "data": None}

        # 工具结果可能是 JSON 或文本
        result_data = {}

        for item in content:
            if isinstance(item, dict):
                if "json" in item:
                    # JSON 结果
                    result_data = item["json"]
                    break
                elif "text" in item:
                    # 文本结果
                    result_data = {"text": item["text"]}
                    break

        return result_data

    async def _handle_tool_result_from_message(self, tool_result: dict[str, Any]):
        """从 message 事件中提取并处理工具结果

        Strands Agent 的工具结果包含在 message 事件中，而不是独立的 tool_result 事件。

        Args:
            tool_result: message.content 中的 toolResult 对象
        """
        tool_use_id = tool_result.get("toolUseId")
        content = tool_result.get("content", [])

        logger.info(f"✅ 工具结果（从消息中）: {tool_use_id}")

        # 查找对应的工具调用
        if tool_use_id in self.active_tool_calls:
            tool_info = self.active_tool_calls[tool_use_id]
            frontend_id = tool_info.get("frontend_id")

            # ✨ 修复：如果工具还未发送到前端（参数不完整），先发送
            if frontend_id is None and not tool_info.get("sent_to_frontend", False):
                logger.warning(
                    f"  ⚠️  工具结果到达但工具未发送到前端，立即发送（参数: {tool_info['input']}）"
                )

                # 发送工具调用到前端（即使参数可能不完整）
                # ✨ 修复：传递真实的开始时间，确保 duration 计算正确
                frontend_id = await self.ws.tool_call_start(
                    tool_name=tool_info["name"],
                    description=tool_info.get(
                        "description", f"调用 {tool_info['name']} 工具"
                    ),
                    args=tool_info["input"],
                    start_time=tool_info.get("start_time"),  # 传递真实的开始时间
                )

                # 更新状态
                tool_info["frontend_id"] = frontend_id
                tool_info["sent_to_frontend"] = True

            # 提取结果数据
            result_data = self._extract_tool_result_data(content)

            logger.info(f"  📊 结果数据: {str(result_data)[:100]}...")

            # 发送到前端（只有在有 frontend_id 的情况下）
            if frontend_id:
                await self.ws.tool_call_result(frontend_id, result_data)
            else:
                logger.error("  ❌ 无法发送工具结果：frontend_id 为 None")

            # 清理已完成的工具调用
            del self.active_tool_calls[tool_use_id]
        else:
            logger.warning(f"⚠️  收到未知工具的结果: {tool_use_id}")

    async def _check_aws_api_confirmation(
        self, tool_name: str, tool_input: dict, tool_use_id: str
    ) -> bool:
        """检查 AWS API 工具是否需要用户确认

        Args:
            tool_name: 工具名称
            tool_input: 工具参数
            tool_use_id: 工具调用 ID

        Returns:
            bool: 是否需要确认（True=需要确认并已发送请求，False=不需要确认）
        """
        # 检测是否是 AWS API 工具（工具名以 aws_ 开头）
        if not tool_name.startswith("aws_"):
            return False

        logger.info(f"  🔐 检测到 AWS API 工具: {tool_name}")

        # 导入安全检查器
        from ..services.aws_api_safety import get_safety_checker

        checker = get_safety_checker()

        # 检查是否需要确认
        if not checker.requires_confirmation(tool_name, tool_input):
            logger.info("  ✅ 只读操作，无需确认")
            return False

        # 需要确认 - 获取确认消息
        risk_level = checker.get_risk_level(tool_name, tool_input)
        title, description, warning = checker.get_confirmation_message(
            tool_name, tool_input
        )

        # 生成确认 ID
        import uuid

        confirmation_id = f"confirm_{uuid.uuid4().hex[:12]}"

        logger.info(f"  ⚠️  需要用户确认 - Risk: {risk_level}, ID: {confirmation_id}")

        # 发送确认请求到前端
        await self.ws.request_confirmation(
            tool_name=tool_name,
            arguments=tool_input,
            confirmation_id=confirmation_id,
            title=title,
            description=description,
            warning=warning,
            risk_level=risk_level,
            timeout_seconds=300,  # 5 分钟超时
        )

        # 标记需要确认
        return True

    def _is_tool_input_complete(self, tool_input: Any) -> bool:
        """判断工具输入参数是否完整

        ❌ 废弃策略：尝试智能判断参数完整性

        ✅ 新策略：永远返回 False，让参数在工具结果到达时才发送

        这样可以确保发送的是最终完整的参数，而不是中间状态。
        容错处理会在工具结果到达时强制发送工具调用。

        Args:
            tool_input: 工具输入参数

        Returns:
            bool: 始终返回 False，延迟到工具结果到达时再发送
        """
        # ✨ 新策略：永远返回 False
        # 让工具调用在结果到达时才发送，确保参数完整
        return False

    async def _log_cache_metrics(self, cache_metrics: dict[str, Any]):
        """记录并发送 Prompt Caching 指标

        Args:
            cache_metrics: 缓存指标数据
        """
        cache_read = cache_metrics["cache_read_tokens"]
        cache_write = cache_metrics["cache_write_tokens"]
        input_tokens = cache_metrics["input_tokens"]
        output_tokens = cache_metrics["output_tokens"]
        cache_hit = cache_metrics["cache_hit"]

        # 记录日志
        if cache_hit:
            logger.info(
                f"✅ Prompt Cache Hit: {cache_read} tokens | "
                f"输入: {input_tokens} | 输出: {output_tokens}"
            )
        elif cache_write > 0:
            logger.info(
                f"📝 Prompt Cache Write: {cache_write} tokens | "
                f"输入: {input_tokens} | 输出: {output_tokens}"
            )
        else:
            # 无缓存活动（可能是缓存未启用或提示词未达到最小长度）
            if input_tokens > 0:
                logger.warning(
                    f"⚠️  No Cache Activity | 输入: {input_tokens} | 输出: {output_tokens}"
                )

        # 发送到前端（可选）
        try:
            await self.ws.send_event({"type": "cache_metrics", "data": cache_metrics})
        except Exception as e:
            logger.debug(f"发送缓存指标到前端失败: {e}")


# ========== 辅助函数 ==========


async def create_streaming_agent(
    base_agent: Agent,
    websocket_handler: Any,
    chat_storage: ChatStoragePostgreSQL | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> StreamingAgentWrapper:
    """创建流式 Agent 包装器

    Args:
        base_agent: 基础 Strands Agent
        websocket_handler: WebSocket 事件处理器
        chat_storage: 聊天存储服务
        session_id: 会话ID
        user_id: 用户ID

    Returns:
        StreamingAgentWrapper: 流式 Agent 包装器
    """
    return StreamingAgentWrapper(
        base_agent,
        websocket_handler,
        chat_storage=chat_storage,
        session_id=session_id,
        user_id=user_id,
    )
