"""
AgentCore Runtime 客户端

使用 AWS 官方文档推荐的 boto3 方式调用 Runtime
参考: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html

实现方式:
1. 使用 boto3.client('bedrock-agentcore') 创建客户端
2. 使用 invoke_agent_runtime() 调用 Runtime
3. 使用 iter_chunks() 迭代流式响应 (SSE 格式) - 避免 iter_lines() 的 IncompleteRead Bug
4. 通过 asyncio.Queue + threading.Thread 实现异步包装
"""

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator
from http.client import IncompleteRead

import boto3

logger = logging.getLogger(__name__)


class AgentCoreClient:
    """AgentCore Runtime 客户端（使用 AWS 官方 boto3 方式）"""

    def __init__(self, runtime_arn: str, region: str = "ap-northeast-1"):
        """
        初始化客户端

        Args:
            runtime_arn: Runtime ARN
            region: AWS 区域
        """
        self.runtime_arn = runtime_arn
        self.region = region
        # AWS 官方推荐：创建 boto3 客户端（增加超时配置）
        from botocore.config import Config

        config = Config(
            read_timeout=900,  # 900 秒读取超时（15 分钟，支持复杂查询）
            connect_timeout=30,  # 30 秒连接超时（增加稳定性）
        )
        self.client = boto3.client(
            "bedrock-agentcore", region_name=region, config=config
        )
        logger.info(f"AgentCoreClient 初始化完成: {runtime_arn}")

    async def invoke_streaming(
        self,
        prompt: str,
        account_id: str,
        session_id: str | None = None,
        user_id: str | None = None,
        org_id: str | None = None,
        prompt_type: str = "dialog",
        account_type: str = "aws",
    ) -> AsyncIterator[dict]:
        """
        异步流式调用 Runtime

        使用独立线程执行 boto3 同步调用，通过 asyncio.Queue 传递事件

        Args:
            prompt: 用户查询
            account_id: AWS/GCP 账号 ID
            session_id: 会话 ID（可选，对话场景使用）
            user_id: 用户 ID（可选，对话场景使用）
            org_id: 组织 ID（可选，对话场景使用）
            prompt_type: 提示词类型（默认: "dialog"）
                - "dialog": 对话场景，使用对话提示词 + Memory
                - "alert": 告警场景，使用告警提示词，无 Memory
            account_type: 账号类型（默认: "aws"）
                - "aws": AWS 账号
                - "gcp": GCP 账号

        Yields:
            dict: SSE 事件数据（已解析的 JSON 对象）

        Raises:
            Exception: Runtime 调用失败时抛出异常

        Note:
            RDS_SECRET_NAME 和 ENCRYPTION_KEY 不再通过 payload 传递，
            Runtime 容器直接从环境变量读取（在 Runtime 配置中设置）

        Examples:
            >>> # 对话场景（默认）
            >>> async for event in client.invoke_streaming(
            ...     prompt="查询成本",
            ...     account_id="123456789012",
            ...     session_id="sess-123",
            ... ):
            ...     process_event(event)

            >>> # 告警场景
            >>> async for event in client.invoke_streaming(
            ...     prompt="当日 EC2 成本超过 $1000",
            ...     account_id="123456789012",
            ...     prompt_type="alert",  # ✅ 关键
            ... ):
            ...     process_event(event)
        """
        event_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _invoke_in_thread():
            """在线程中执行 AWS 官方文档推荐的同步调用"""
            event_count = 0
            bytes_read = 0
            chunk_count = 0

            try:
                # 构建 payload
                payload = {
                    "prompt": prompt,
                    "account_id": account_id,
                    "prompt_type": prompt_type,  # ✅ 传递提示词类型
                    "account_type": account_type,  # ✅ 传递账号类型
                }
                if session_id:
                    payload["session_id"] = session_id
                if user_id:
                    payload["user_id"] = user_id
                if org_id:
                    payload["org_id"] = org_id

                logger.info(f"调用 Runtime: {self.runtime_arn}")
                logger.info(
                    f"Payload: prompt_type={prompt_type}, account_type={account_type}, "
                    f"session_id={session_id}, account_id={account_id}"
                )

                # AWS 官方方式：调用 invoke_agent_runtime
                # 参数说明：
                # - agentRuntimeArn: Runtime ARN（必需）
                # - payload: 请求数据（必需）
                #   * session_id 在 payload 中传递（应用层会话 ID，用于 Memory 和聊天历史）
                # - runtimeSessionId: Runtime 级别的会话 ID（可选，让 AWS 自动生成）
                #   * 注意：这不是我们应用的 session_id！
                #   * 用于 Runtime 内部状态管理，与我们的聊天会话无关
                # - contentType/accept: 可选，默认值通常就够用

                logger.info(f"📤 [Client] 发送请求到Runtime: {self.runtime_arn}")
                logger.info(f"📤 [Client] Payload键: {list(payload.keys())}")

                # ✅ 构建 invoke_agent_runtime 参数
                invoke_params = {
                    "agentRuntimeArn": self.runtime_arn,
                    "payload": json.dumps(payload).encode("utf-8"),
                }

                # ✅ P0 修复：如果有 session_id，作为 runtimeSessionId 传递
                # 这样可以：
                # 1. 复用 microVM（15分钟空闲超时，8小时最大生命周期）
                # 2. AgentCore Memory 自动关联对话历史
                # 3. 节省资源（不会每次查询都创建新的 microVM）
                if session_id:
                    # 确保 session_id 是字符串（可能是 UUID 对象）
                    invoke_params["runtimeSessionId"] = str(session_id)
                    logger.info(f"✅ 使用 runtimeSessionId: {session_id}")
                else:
                    logger.info(
                        "📌 未指定 session_id，AWS 将自动生成临时 runtimeSessionId"
                    )

                response = self.client.invoke_agent_runtime(**invoke_params)

                content_type = response.get("contentType", "")
                logger.info(f"📥 [Client] Runtime 响应类型: {content_type}")
                logger.info(f"📥 [Client] Runtime 响应键: {list(response.keys())}")

                # ✅ 修复：使用 iter_chunks() 替代 iter_lines()，避免 IncompleteRead Bug
                if "text/event-stream" in content_type:
                    logger.info("📥 [Client] 开始迭代流式响应（使用 iter_chunks）...")

                    # ✅ 手动处理行分割，避免 boto3 iter_lines 的 Bug
                    # chunk_size=4096 是平衡性能和稳定性的推荐值
                    buffer = b""

                    for chunk in response["response"].iter_chunks(chunk_size=4096):
                        chunk_count += 1
                        bytes_read += len(chunk)
                        buffer += chunk

                        # 每 20 个 chunk 记录一次进度
                        if chunk_count % 20 == 0:
                            logger.debug(
                                f"📊 进度: {bytes_read} 字节, {chunk_count} chunk, {event_count} 事件"
                            )

                        # 手动处理行分割
                        while b"\n" in buffer:
                            line_bytes, buffer = buffer.split(b"\n", 1)

                            if not line_bytes.strip():
                                continue

                            line_str = line_bytes.decode("utf-8").strip()

                            # 解析 SSE 格式: "data: {...}"
                            if line_str.startswith("data: "):
                                data_str = line_str[6:]  # 去掉 "data: " 前缀
                                try:
                                    event_data = json.loads(data_str)
                                    event_count += 1

                                    # ✅ 详细日志：显示接收到的事件类型
                                    if event_count <= 5 or event_count % 50 == 0:
                                        event_keys = (
                                            list(event_data.keys())
                                            if isinstance(event_data, dict)
                                            else "not-dict"
                                        )
                                        logger.info(
                                            f"📥 [Runtime] 收到事件 #{event_count}, 键: {event_keys}"
                                        )

                                    # ⭐ 专门检测 token_usage 事件
                                    if isinstance(event_data, dict) and event_data.get("type") == "token_usage":
                                        usage = event_data.get('usage', {})
                                        logger.info(
                                            "收到 token_usage 事件",
                                            extra={
                                                "input_tokens": usage.get('input_tokens'),
                                                "output_tokens": usage.get('output_tokens'),
                                                "cache_read_tokens": usage.get('cache_read_tokens'),
                                                "cache_write_tokens": usage.get('cache_write_tokens'),
                                            }
                                        )

                                    # 放入异步队列（已解析的字典）
                                    asyncio.run_coroutine_threadsafe(
                                        event_queue.put(event_data), loop
                                    )
                                except json.JSONDecodeError as e:
                                    logger.warning(
                                        f"无法解析 SSE 数据: {data_str[:100]}, 错误: {e}"
                                    )

                    # ✅ 处理剩余缓冲区（最后一行可能没有 \n）
                    if buffer.strip():
                        line_str = buffer.decode("utf-8").strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            try:
                                event_data = json.loads(data_str)
                                event_count += 1
                                asyncio.run_coroutine_threadsafe(
                                    event_queue.put(event_data), loop
                                )
                                logger.debug("✅ 处理了缓冲区中的最后一行")
                            except json.JSONDecodeError:
                                logger.warning(f"无法解析最后一行: {data_str[:100]}")

                    logger.info(
                        f"✅ Runtime 返回 {event_count} 个事件 "
                        f"({bytes_read} 字节, {chunk_count} chunk)"
                    )
                else:
                    logger.warning(f"非流式响应: {content_type}")

                # 发送结束标记
                asyncio.run_coroutine_threadsafe(event_queue.put(None), loop)

                logger.info("Runtime 调用完成")

            except IncompleteRead as e:
                # ✅ 捕获 IncompleteRead，优雅降级
                logger.warning(
                    f"⚠️ SSE 流提前结束（IncompleteRead）！"
                    f"已读取 {len(e.partial)} 字节（期望更多），"
                    f"总共接收了 {event_count} 个事件，"
                    f"{bytes_read} 总字节，{chunk_count} chunk"
                )
                logger.warning(
                    f"⚠️ 这可能不是错误，boto3 在某些情况下会误报 IncompleteRead。"
                    f"已接收的 {event_count} 个事件将正常返回给前端。"
                )

                # 不抛出异常，发送结束标记（让前端收到已有的数据）
                asyncio.run_coroutine_threadsafe(event_queue.put(None), loop)

                logger.info("Runtime 调用完成（IncompleteRead 已处理）")

            except Exception as e:
                logger.error(
                    f"Runtime 调用失败: {e}（event_count={event_count}, "
                    f"bytes_read={bytes_read}, chunk_count={chunk_count}）",
                    exc_info=True,
                )
                # 发送异常
                asyncio.run_coroutine_threadsafe(event_queue.put(e), loop)

        # 启动线程
        thread = threading.Thread(target=_invoke_in_thread, daemon=True)
        thread.start()
        logger.debug("后台线程已启动")

        # 异步消费队列
        while True:
            event = await event_queue.get()

            if event is None:
                # 结束
                logger.debug("流式输出结束")
                break

            if isinstance(event, Exception):
                # 抛出异常
                logger.error(f"收到异常: {event}")
                raise event

            yield event
