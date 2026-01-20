"""Agent管理器 - 简化版（无缓存）

完全对齐AgentCore Runtime部署标准，移除复杂的TTL缓存和并发控制逻辑。
"""

import logging
import os
from typing import Any

from strands import Agent
from strands.models import BedrockModel
from strands_tools.calculator import calculator  # 计算器工具（SymPy 底层）

from backend.config.settings import settings

# 初始化标准 logger
logger = logging.getLogger(__name__)

# 环境判断（用于日志风格）
IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"


class AgentManager:
    """Agent管理器（简化版）

    设计理念：
        1. 单例BedrockModel（复用LLM连接，减少内存占用）
        2. 无状态Agent创建（每次创建新实例，AgentCore Runtime在microVM内复用）
        3. 无TTL缓存（避免内存泄漏，简化生命周期管理）

    Attributes:
        system_prompt: 系统提示词
        model_id: Bedrock模型ID
        bedrock_model: 单例BedrockModel实例

    Examples:
        >>> manager = AgentManager(
        ...     system_prompt="You are a helpful assistant",
        ...     model_id="anthropic.claude-3-haiku-20240307-v1:0"
        ... )
        >>> tools = [tool1, tool2]
        >>> agent = manager.create_agent(tools)
    """

    def __init__(self, system_prompt: str, model_id: str | None = None) -> None:
        """初始化Agent管理器

        Args:
            system_prompt: 系统提示词
            model_id: Bedrock模型ID（默认从配置读取）

        Raises:
            ValueError: 如果system_prompt为空
        """
        if not system_prompt:
            raise ValueError("system_prompt不能为空")

        self.system_prompt = system_prompt
        self.model_id = model_id or settings.BEDROCK_MODEL_ID

        # 单例BedrockModel
        self.bedrock_model = self._create_bedrock_model()

        if IS_PRODUCTION:
            logger.info("AgentManager初始化完成", extra={"model_id": self.model_id})
        else:
            logger.info(f"✅ AgentManager初始化 - Model: {self.model_id}")

    def _create_bedrock_model(self) -> BedrockModel:
        """创建BedrockModel实例

        根据环境自动选择凭证方式：
            - 生产环境（EKS/AgentCore）: 使用IAM Role
            - 本地环境: 使用AWS_PROFILE

        Returns:
            BedrockModel: Bedrock模型实例

        Raises:
            ValueError: 如果Bedrock配置无效

        Notes:
            - Prompt Caching可通过环境变量BEDROCK_ENABLE_PROMPT_CACHING控制
            - 本地环境需要配置AWS_PROFILE环境变量
        """
        # Prompt Caching配置
        cache_config: dict[str, Any] = {}
        if settings.BEDROCK_ENABLE_PROMPT_CACHING:
            cache_config = {
                "cache_prompt": settings.BEDROCK_CACHE_PROMPT,
                "cache_tools": settings.BEDROCK_CACHE_TOOLS,
            }
            if not IS_PRODUCTION:
                logger.info(f"✅ Bedrock Prompt Caching已启用: {cache_config}")

        # 根据环境选择凭证
        boto_session = None
        if not settings.use_iam_role and settings.bedrock_profile:
            # 本地环境：使用Profile
            import boto3

            boto_session = boto3.Session(
                profile_name=settings.bedrock_profile,
                region_name=settings.bedrock_region,
            )
            logger.info(
                "BedrockModel使用Profile",
                extra={
                    "profile": settings.bedrock_profile,
                    "region": settings.bedrock_region,
                },
            )
        else:
            # 生产环境：使用IAM Role或跨账号Role
            import boto3

            # 如果配置了跨账号 Role，使用 AWSSessionFactory
            if settings.BEDROCK_CROSS_ACCOUNT_ROLE_ARN:
                logger.info(
                    "BedrockModel使用跨账号Role",
                    extra={
                        "role_arn": settings.BEDROCK_CROSS_ACCOUNT_ROLE_ARN,
                        "region": settings.bedrock_region,
                    },
                )

                # ✅ P1修复：添加异常处理，防止AssumeRole失败导致启动失败
                try:
                    # ⚠️ 关键：使用 AWSSessionFactory 来避免环境变量污染
                    # AWSSessionFactory 内部会正确处理凭证链，使用 Runtime IAM Role
                    from backend.utils.aws_session_factory import AWSSessionFactory

                    # 创建 SessionFactory（用于 Bedrock 跨账号访问）
                    bedrock_factory = AWSSessionFactory.get_instance(
                        role_arn=settings.BEDROCK_CROSS_ACCOUNT_ROLE_ARN,
                        region=settings.bedrock_region,
                        role_session_name="CostQBedrockSession",
                        duration_seconds=settings.BEDROCK_ASSUME_ROLE_DURATION,
                    )

                    # 获取带自动刷新凭证的 boto3 Session
                    boto_session = bedrock_factory.get_session()

                    logger.info("✅ Bedrock Session 创建成功（使用 AWSSessionFactory）")

                except Exception as e:
                    # ✅ 捕获AssumeRole失败（权限问题、网络超时、IAM配置错误等）
                    error_msg = f"跨账号AssumeRole失败: {type(e).__name__} - {str(e)}"
                    logger.error(
                        error_msg,
                        extra={
                            "role_arn": settings.BEDROCK_CROSS_ACCOUNT_ROLE_ARN,
                            "error_type": type(e).__name__,
                            "error": str(e),
                        },
                        exc_info=True
                    )
                    # ✅ 抛出 ValueError，让调用方知道配置有问题
                    raise ValueError(error_msg) from e
            else:
                # 使用当前环境的 IAM Role
                logger.info("BedrockModel使用IAM Role", extra={"region": settings.bedrock_region})

        return BedrockModel(
            model_id=self.model_id,
            boto_session=boto_session,
            temperature=0.3,
            **cache_config,
        )

    def create_agent(self, tools: list[Any]) -> Agent:
        """创建Agent实例（无状态）

        Args:
            tools: 工具列表（来自MCP客户端）

        Returns:
            Agent: 新创建的Agent实例

        Raises:
            ValueError: 如果tools为空列表

        Examples:
            >>> tools = [tool1, tool2, tool3]
            >>> agent = manager.create_agent(tools)
            >>> print(type(agent))
            <class 'strands.Agent'>

        Notes:
            - 每次调用都创建新Agent实例
            - 复用单例BedrockModel以节省内存和启动时间
            - 工具列表应该从MCPManager.create_all_clients()获取
            - 自动添加 calculator 工具用于数学计算（成本分析、百分比计算等）
            - 即使 MCP 工具列表为空，也会包含 calculator 工具
        """
        # ✅ 将 calculator 工具添加到工具列表（用于成本计算、增长率等数学运算）
        # 注意：即使 tools 为空列表，all_tools 也至少包含 calculator
        all_tools = [calculator] + (tools if tools else [])

        agent = Agent(
            model=self.bedrock_model,
            system_prompt=self.system_prompt,
            tools=all_tools,
        )

        if IS_PRODUCTION:
            logger.info(
                "Agent创建完成",
                extra={
                    "tool_count": len(all_tools),
                    "has_calculator": True,
                    "model_id": self.model_id
                },
            )
        else:
            logger.info(f"✅ Agent创建完成 - Tools: {len(all_tools)} (含Calculator)")

        return agent

    def create_agent_with_memory(
        self,
        tools: list[Any],
        memory_client: Any = None,
        memory_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        window_size: int = 40,
    ) -> Agent:
        """创建Agent（Memory可选）

        根据是否提供完整的Memory参数，自动选择创建带或不带Memory的Agent。

        Args:
            tools: 工具列表（必需）
            memory_client: MemoryClient实例（可选）
            memory_id: Memory资源ID（可选）
            user_id: 用户ID，作为actor_id（可选）
            session_id: 会话ID（可选）
            window_size: 上下文窗口大小（默认40条消息，约10轮对话）

        Returns:
            Agent: Agent实例
                - 如果提供完整Memory参数：带SessionManager和ConversationManager
                - 如果未提供Memory参数：无Memory的Agent

        Raises:
            ValueError: 如果tools为空
            ImportError: 如果需要Memory但bedrock_agentcore模块不存在

        Examples:
            >>> # 对话场景（需要 Memory）
            >>> from bedrock_agentcore.memory import MemoryClient
            >>> memory_client = MemoryClient(region_name="us-east-1")
            >>> agent = manager.create_agent_with_memory(
            ...     tools=tools,
            ...     memory_client=memory_client,
            ...     memory_id="mem-123",
            ...     user_id="user-456",
            ...     session_id="sess-789",
            ... )

            >>> # 告警场景（不需要 Memory）
            >>> agent = manager.create_agent_with_memory(tools=tools)

        Notes:
            - Memory参数必须全部提供或全部不提供
            - 如果未提供完整Memory参数，自动回退到create_agent（无Memory）
            - 使用AWS官方AgentCoreMemorySessionManager管理Memory
            - 使用SlidingWindowConversationManager管理上下文窗口
        """
        if not tools:
            raise ValueError("工具列表不能为空")

        # 检查是否提供了完整的 Memory 配置
        has_memory_config = all([memory_client, memory_id, user_id, session_id])

        if not has_memory_config:
            # 回退到无 Memory 模式
            if IS_PRODUCTION:
                logger.info(
                    "创建无Memory的Agent",
                    extra={"reason": "部分或全部Memory参数未提供"}
                )
            else:
                logger.info("✅ 创建无Memory的Agent（部分或全部Memory参数未提供）")

            return self.create_agent(tools)

        try:
            from bedrock_agentcore.memory.integrations.strands.config import (
                AgentCoreMemoryConfig,
                RetrievalConfig,
            )
            from bedrock_agentcore.memory.integrations.strands.session_manager import (
                AgentCoreMemorySessionManager,
            )
            from strands.agent.conversation_manager import SlidingWindowConversationManager
        except ImportError as e:
            logger.error("无法导入bedrock_agentcore模块", extra={"error": str(e)})
            raise

        # 1. Memory配置（完整历史持久化 + 长期记忆检索）
        agentcore_memory_config = AgentCoreMemoryConfig(
            memory_id=memory_id,
            session_id=session_id,
            actor_id=user_id,  # 使用user_id作为actor_id
            # 长期记忆检索配置
            # 注意：字典 key 必须是完整的 namespace 模板（包含 strategy_id）
            retrieval_config={
                # 用户偏好记忆（成本偏好、告警配置等）
                "/strategies/preference_builtin_t6jp9-AaHcsvCuJL/actors/{actorId}": RetrievalConfig(
                    top_k=5,  # 推荐值：覆盖多个维度的偏好
                ),
                # 语义记忆（历史成本事实和知识）
                "/strategies/semantic_builtin_t6jp9-0I3QsXFhRf/actors/{actorId}": RetrievalConfig(
                    top_k=3,  # 推荐值：聚焦高相关事实
                ),
            }
        )

        # 2. SessionManager（负责Memory持久化）
        # 注意：Memory 资源在 AWS_REGION (ap-northeast-1)，不是 bedrock_region (us-west-2)

        # 检查当前 AWS credentials
        import boto3
        try:
            sts_client = boto3.client('sts', region_name=settings.AWS_REGION)
            caller_identity = sts_client.get_caller_identity()
            current_role_arn = caller_identity.get('Arn', 'Unknown')
            current_account = caller_identity.get('Account', 'Unknown')
        except Exception as e:
            current_role_arn = f"Failed to get: {e}"
            current_account = "Unknown"

        logger.info(
            "🔧 创建 AgentCoreMemorySessionManager",
            extra={
                "memory_id": memory_id,
                "session_id": session_id,
                "actor_id": user_id,
                "region_name": settings.AWS_REGION,
                "aws_profile": settings.AWS_PROFILE,
                "current_role_arn": current_role_arn,
                "current_account": current_account,
                "has_retrieval_config": agentcore_memory_config.retrieval_config is not None,
                "retrieval_namespace_count": len(agentcore_memory_config.retrieval_config) if agentcore_memory_config.retrieval_config else 0,
                "retrieval_namespaces": list(agentcore_memory_config.retrieval_config.keys()) if agentcore_memory_config.retrieval_config else [],
            }
        )

        # ✅ P0修复：添加异常处理，防止Memory初始化失败导致容器崩溃
        try:
            session_manager = AgentCoreMemorySessionManager(
                agentcore_memory_config=agentcore_memory_config,
                region_name=settings.AWS_REGION,
            )

            logger.info(
                "✅ AgentCoreMemorySessionManager 创建成功",
                extra={
                    "long_term_memory_enabled": agentcore_memory_config.retrieval_config is not None,
                    "user_preferences_top_k": 5,
                    "semantic_memories_top_k": 3,
                }
            )

        except Exception as e:
            # ✅ 捕获所有异常（包括boto3 client创建失败、网络超时、权限错误等）
            logger.error(
                "❌ AgentCoreMemorySessionManager 创建失败，回退到无Memory模式",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "memory_id": memory_id,
                    "session_id": session_id,
                },
                exc_info=True  # 记录完整堆栈
            )

            # ✅ 回退到无Memory模式（保证Agent仍可工作）
            if IS_PRODUCTION:
                logger.info(
                    "回退到无Memory模式",
                    extra={"reason": "Memory初始化失败"}
                )
            else:
                logger.info("⚠️ 回退到无Memory模式（Memory初始化失败）")

            return self.create_agent(tools)

        # 3. ConversationManager（负责上下文窗口管理）
        conversation_manager = SlidingWindowConversationManager(
            window_size=window_size,
            should_truncate_results=True,  # 工具结果过大时自动截断
        )

        # 4. 创建Agent（添加 calculator 工具）
        # ✅ 将 calculator 工具添加到工具列表（用于成本计算、增长率等数学运算）
        all_tools = [calculator] + tools

        agent = Agent(
            model=self.bedrock_model,
            system_prompt=self.system_prompt,
            tools=all_tools,
            session_manager=session_manager,  # 持久化
            conversation_manager=conversation_manager,  # 上下文管理
        )

        if IS_PRODUCTION:
            logger.info(
                "Agent创建完成（带Memory）",
                extra={
                    "tool_count": len(all_tools),
                    "has_calculator": True,
                    "user_id": user_id,
                    "session_id": session_id,
                    "window_size": window_size,
                    "has_memory": True,
                },
            )
        else:
            logger.info(
                f"✅ Agent创建完成（带Memory） - "
                f"Tools: {len(all_tools)} (含Calculator), "
                f"User: {user_id}, Session: {session_id}, "
                f"Window: {window_size} messages"
            )

        return agent
