"""
统一配置管理模块
基于 Pydantic Settings，支持环境变量自动注入和类型验证
"""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """
    应用配置类

    优先级（从高到低）：
    1. 环境变量
    2. .env 文件
    3. 代码中的默认值
    """

    # ==================== 环境标识 ====================
    ENVIRONMENT: Literal["local", "development", "staging", "production"] = Field(
        default="local", description="当前运行环境"
    )
    DEBUG: bool = Field(default=False, description="调试模式")

    # ==================== 应用配置 ====================
    APP_NAME: str = "Strands Agent Demo"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # ==================== 安全配置 ====================
    JWT_SECRET_KEY: str = Field(
        default="dev-jwt-key-change-in-production",  # 仅用于本地开发
        description="JWT签名密钥",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,  # 24小时
        description="JWT Token过期时间（分钟）",
    )

    # 加密密钥（Fernet格式，44字节Base64编码）
    ENCRYPTION_KEY: str | None = Field(
        default=None, description="Fernet加密密钥，用于加密云账号凭证"
    )

    # ==================== 数据库配置 ====================
    DATABASE_URL: str | None = Field(default=None, description="数据库连接字符串 (PostgreSQL)")

    # ==================== AWS配置 ====================
    # 资源区域（RDS, EKS等）
    # 在本地开发时，这通常是目标云环境的区域
    AWS_REGION: str = Field(default="ap-northeast-1", description="AWS资源区域")

    # AWS Profile（仅本地使用）
    # 生产环境使用 IAM Role，此字段应为 None 或被忽略
    AWS_PROFILE: str | None = Field(default=None, description="AWS CLI配置文件名称")

    # Bedrock 模型配置
    BEDROCK_MODEL_ID: str = Field(
        default="us.anthropic.claude-sonnet-4-20250514-v1:0",
        description="Bedrock 模型 ID (使用 inference profile)",
    )

    # Bedrock 服务区域（inference profile 所在区域）
    BEDROCK_REGION: str = Field(
        default="us-west-2", description="Bedrock 服务区域（inference profile 在 us-west-2）"
    )

    # 兼容性字段
    @property
    def AWS_DEFAULT_REGION(self) -> str:
        return self.BEDROCK_REGION

    # Bedrock 跨账号访问 Role ARN（生产环境使用）
    BEDROCK_CROSS_ACCOUNT_ROLE_ARN: str | None = Field(
        default=None,
        description="Bedrock 跨账号访问 Role ARN（如 arn:aws:iam::905418431228:role/CrossAccountBedrockRole）",
    )

    # Bedrock AssumeRole 临时凭证有效期（秒）
    BEDROCK_ASSUME_ROLE_DURATION: int = Field(
        default=3600,  # 1 小时（role chaining 的最大限制）
        description="Bedrock AssumeRole 临时凭证有效期（秒），使用 role chaining 时最大 3600 秒",
    )

    # ==================== Bedrock Prompt Caching 配置 ====================
    BEDROCK_ENABLE_PROMPT_CACHING: bool = Field(
        default=True, description="是否启用 Bedrock Prompt Caching 功能"
    )
    BEDROCK_CACHE_PROMPT: str | None = Field(
        default="default", description="System Prompt 缓存类型（default 或 None）"
    )
    BEDROCK_CACHE_TOOLS: str | None = Field(
        default="default", description="工具定义缓存类型（default 或 None）"
    )

    # MCP AWS 配置（用于 MCP 服务器）
    MCP_AWS_PROFILE: str | None = Field(default=None, description="MCP服务器使用的AWS配置文件")
    MCP_AWS_DEFAULT_REGION: str | None = Field(default=None, description="MCP服务器使用的AWS区域")

    # ==================== MCP服务器配置 ====================
    # AWS MCP服务器列表（本地 stdio 模式）
    # 注意：billing-cost-management 已迁移到 Gateway MCP，避免重复加载
    AWS_MCP_SERVERS: list[str] = Field(
        default=[
            "common-tools",  # 通用工具集（时间日期等基础功能）
            # "cost-explorer",  # AWS Cost Explorer (官方) - 已被 common-tools 替代 get_today_date 功能
            # "risp",  # RI/SP分析 (自定义) - ⚠️ 已迁移到 Gateway MCP，避免重复
            # "billing-cost-management",  # ⚠️ 已迁移到 Gateway MCP，避免重复
            # "cloudtrail",  # CloudTrail 日志查询 (官方) - ⚠️ 已迁移到 Gateway MCP，避免重复
            "pricing",  # AWS Pricing API (官方Python包)
            "documentation",  # AWS Documentation (官方Python包)
            # "knowledge",  # AWS Knowledge (官方远程托管服务) - 临时禁用：网络超时问题
            "alert",  # 告警管理 (平台级)
            "send-email",  # 邮件发送服务 (平台级)
        ],
        description="AWS账号启用的MCP服务器列表（本地 stdio 模式）",
    )

    # Gateway MCP 服务器列表（远程 HTTP 模式，使用 SigV4 认证）
    # 这些 MCP 通过 Gateway URL 连接，无需本地启动子进程
    AWS_GATEWAY_MCP_SERVERS: list[str] = Field(
        default=[
            "billing-cost-management",  # 成本优化和管理 (官方 - 通过 Gateway 连接)
            "risp",  # RI/SP分析 (自定义 - 通过 Gateway 连接)
        ],
        description="通过 Gateway 连接的 MCP 服务器列表",
    )

    # GCP MCP服务器列表（固定为一个集成MCP）
    GCP_MCP_SERVERS: list[str] = Field(
        default=["gcp-cost"],  # 包含所有GCP功能：成本分析、CUD、优化建议、预算管理
        description="GCP账号启用的MCP服务器列表",
    )

    # ==================== 云资源配置 ====================
    # AWS Secrets Manager 密钥名称
    # 本地开发时指向 Dev 密钥，生产环境指向 Prod 密钥
    RDS_SECRET_NAME: str = Field(
        default="costq/rds/postgresql", description="RDS PostgreSQL 密钥名称"
    )

    # AgentCore Memory Resource ID
    # 必须通过环境变量设置：
    # - 本地开发: MEMORY_RESOURCE_ID=CostQ_Dev-Su0pSXBOca (通过 .env 或 Dockerfile ENV)
    # - 生产环境: MEMORY_RESOURCE_ID=CostQ_Pro-77Jh0OAr3A (通过 Runtime Dockerfile/环境变量)
    MEMORY_RESOURCE_ID: str | None = Field(
        default=None,
        description="AgentCore Memory Resource ID（预先在 AWS Console 创建，必须通过环境变量设置）",
    )

    # AgentCore Runtime 配置
    AGENTCORE_RUNTIME_ARN: str = Field(
        default="arn:aws:bedrock-agentcore:ap-northeast-1:000451883532:runtime/cosq_agentcore_runtime_private_subnet-TPI6pUDi9R",
        description="AgentCore Runtime ARN",
    )
    AGENTCORE_REGION: str = Field(
        default="ap-northeast-1", description="AgentCore Runtime 所在区域"
    )

    # ==================== Gateway MCP 配置 ====================
    # Gateway MCP URL（远程 MCP Server 端点）
    # 使用 IAM SigV4 认证，无需明文凭证
    COSTQ_AWS_MCP_SERVERS_GATEWAY_URL: str | None = Field(
        default=None,
        description="Gateway MCP HTTP 端点 URL（如 https://xxx.gateway.bedrock-agentcore.ap-northeast-1.amazonaws.com/mcp）",
    )

    # Gateway MCP 服务名（用于 SigV4 签名）
    GATEWAY_SERVICE: str = Field(
        default="bedrock-agentcore",
        description="Gateway MCP 服务名（用于 SigV4 签名）",
    )

    # Gateway MCP 区域（用于 SigV4 签名）
    AWS_REGION: str = Field(
        default="ap-northeast-1",
        description="Gateway MCP 区域（用于 SigV4 签名）",
    )

    # S3 存储桶
    S3_BUCKET_NAME: str = Field(default="costq-storage", description="S3 存储桶名称")

    # EKS 集群
    EKS_CLUSTER_NAME: str = Field(default="costq-eks-cluster", description="EKS 集群名称")

    # ECR 仓库
    ECR_REPOSITORY: str = Field(
        default="000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq",
        description="ECR 镜像仓库地址",
    )

    # ==================== GCP配置 ====================
    GCP_ACCOUNT_ID: str | None = Field(default=None, description="GCP账号ID（用于成本分析）")
    GCP_PROJECT_ID: str | None = Field(default=None, description="GCP项目ID")

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    FASTMCP_LOG_LEVEL: str = Field(default="WARNING", description="MCP框架日志级别")

    # ==================== CORS配置 ====================
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
        description="允许的跨域来源（逗号分隔）",
    )

    # ==================== 前端配置 ====================
    FRONTEND_URL: str = Field(
        default="http://localhost:5173", description="前端应用的URL（用于生成邮件激活链接等）"
    )

    # ==================== 模型配置 ====================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # 忽略额外的环境变量
    )

    # ==================== 验证器 ====================
    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """验证JWT密钥在生产环境必须提供且足够长"""
        # 获取环境信息
        env = os.getenv("ENVIRONMENT", "local")

        # 禁止的弱密钥列表
        FORBIDDEN_KEYS = {
            "your-secret-key-change-in-production-2024",
            "dev-jwt-key-change-in-production",
            "secret",
            "secret-key",
            "jwt-secret",
            "change-me",
        }

        if env == "production":
            if not v:
                raise ValueError(
                    "生产环境必须设置 JWT_SECRET_KEY！\n"
                    "生成方法: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            if v in FORBIDDEN_KEYS or v.lower() in FORBIDDEN_KEYS:
                raise ValueError(
                    "生产环境禁止使用默认或弱JWT密钥！\n"
                    "生成强密钥: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            if len(v) < 32:
                raise ValueError("生产环境 JWT_SECRET_KEY 必须至少32个字符")
        else:
            # 非生产环境警告使用默认密钥
            if v in FORBIDDEN_KEYS:
                import warnings

                warnings.warn(f"使用默认JWT密钥（仅{env}环境）。生产环境必须更换！", UserWarning)

        return v

    @field_validator("ENCRYPTION_KEY", mode="before")
    @classmethod
    def validate_encryption_key(cls, v: str | None, info) -> str | None:
        """验证加密密钥在生产环境必须配置且格式正确"""
        # 在before模式下，需要从环境变量直接读取ENVIRONMENT
        env = os.getenv("ENVIRONMENT", "local")

        if env == "production":
            if not v:
                raise ValueError(
                    "生产环境必须设置 ENCRYPTION_KEY！\n"
                    "生成方法: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )

            # 验证Fernet密钥格式
            try:
                from cryptography.fernet import Fernet

                Fernet(v.encode() if isinstance(v, str) else v)
            except Exception as e:
                raise ValueError(f"ENCRYPTION_KEY 格式错误，必须是有效的Fernet密钥: {e}")

        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str | None, info) -> str | None:
        """验证数据库配置"""
        return v

    # ==================== 辅助方法 ====================
    @property
    def is_production(self) -> bool:
        """是否是生产环境"""
        return self.ENVIRONMENT == "production"

    @property
    def is_local(self) -> bool:
        """是否是本地开发环境"""
        return self.ENVIRONMENT == "local"

    @property
    def is_cloud_environment(self) -> bool:
        """
        是否运行在云环境（EC2/容器）

        检测逻辑:
        - 检查 DOCKER_CONTAINER 环境变量（Runtime 容器）
        - 检查是否存在 EC2 实例元数据服务
        - 生产环境默认认为是云环境
        """
        if self.is_production:
            return True

        # 检查是否在 Docker 容器中（AgentCore Runtime）
        import os

        if os.getenv("DOCKER_CONTAINER") == "1":
            return True

        # 检查 EC2 元数据服务
        try:
            import requests

            # EC2 元数据服务地址（IMDSv2）
            response = requests.get(
                "http://169.254.169.254/latest/meta-data/instance-id", timeout=0.1
            )
            return response.status_code == 200
        except:
            return False

    @property
    def use_iam_role(self) -> bool:
        """
        是否使用 IAM Role（而非 profile/AKSK）

        Returns:
            True: 云环境，使用 IAM Role
            False: 本地环境，使用 profile/AKSK
        """
        return self.is_cloud_environment

    @property
    def aws_region(self) -> str:
        """
        获取当前应使用的 AWS 区域 (资源区域)
        """
        return self.AWS_REGION

    @property
    def bedrock_profile(self) -> str | None:
        """
        获取 Bedrock 使用的 AWS Profile

        在生产环境/云环境中，应该使用 IAM Role 而不是 profile。

        Returns:
            生产环境/云环境: None (使用 IAM Role)
            本地环境: AWS_PROFILE (如 "1228")
        """
        if self.use_iam_role:
            return None
        else:
            return self.AWS_PROFILE

    @property
    def bedrock_region(self) -> str:
        """
        获取 Bedrock 服务使用的 AWS 区域
        """
        return self.BEDROCK_REGION

    def get_cors_origins_list(self) -> list[str]:
        """获取CORS允许的来源列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    def get_mcp_aws_profile(self) -> str:
        """获取MCP使用的AWS配置文件（带回退）"""
        return self.MCP_AWS_PROFILE or self.AWS_PROFILE

    def get_mcp_aws_region(self) -> str:
        """获取MCP使用的AWS区域（带回退）"""
        return self.MCP_AWS_DEFAULT_REGION or self.AWS_DEFAULT_REGION

    def get_database_url(self) -> str:
        """
        动态获取数据库连接字符串

        逻辑：
        1. 确定目标区域 (AWS_REGION)
        2. 确定认证方式 (IAM Role vs Profile)
        3. 读取 Secrets Manager (RDS_SECRET_NAME)

        ✅ AgentCore Runtime 支持：
        - Runtime 在 invoke() 中会通过 payload 接收 rds_secret_name
        - 并设置到环境变量 os.environ["RDS_SECRET_NAME"]
        - 这里优先从环境变量读取，支持动态切换 dev/prod 数据库
        """
        try:
            import os

            from backend.config.aws_secrets import get_secrets_manager

            # ✅ 优先从环境变量读取 RDS_SECRET_NAME（支持 Runtime 动态传递）
            # AgentCore Runtime: payload → os.environ → 这里读取
            # FastAPI 本地/生产: .env/ConfigMap → self.RDS_SECRET_NAME
            rds_secret_name = os.getenv("RDS_SECRET_NAME") or self.RDS_SECRET_NAME

            # 确定 Profile: 如果使用 IAM Role，则为 None；否则使用配置的 Profile
            # AgentCore Runtime 永远使用 IAM Role (profile_name=None)
            profile_name = None if self.use_iam_role else self.AWS_PROFILE

            secrets_manager = get_secrets_manager(
                region_name=self.AWS_REGION, profile_name=profile_name
            )

            # ✅ 使用动态读取的密钥名称
            database_url = secrets_manager.build_database_url(rds_secret_name)

            # 日志记录（仅本地）
            if self.is_local:
                import logging

                logger = logging.getLogger(__name__)
                logger.info(f"✅ 本地开发环境连接云端数据库: {rds_secret_name}")

            return database_url
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"❌ 获取数据库连接失败: {e}")
            raise RuntimeError(f"无法连接到数据库: {e}")


# ==================== 全局配置实例 ====================
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    获取配置实例（单例模式）
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# 导出默认实例
settings = get_settings()
