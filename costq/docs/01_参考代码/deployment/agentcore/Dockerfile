FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

# All environment variables in one layer
# 注意：以下环境变量可以在 AgentCore Runtime 的 ConfigMap 中覆盖
# - Dev 环境: MEMORY_RESOURCE_ID=CostQ_Dev-Su0pSXBOca
# - Prod 环境: MEMORY_RESOURCE_ID=CostQ_Pro-77Jh0OAr3A
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1

# ========== 安装系统依赖 ==========
# 注意：uvx 已经包含在基础镜像 ghcr.io/astral-sh/uv 中，无需单独安装
# 只需安装编译工具和系统库用于构建 Python 包
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 编译工具（用于某些 Python 包的 C 扩展）
    build-essential \
    gcc \
    g++ \
    # 系统库（用于 cryptography, psycopg2 等包）
    libssl-dev \
    libffi-dev \
    libpq-dev \
    # 工具包
    curl \
    ca-certificates \
    # 清理 apt 缓存减小镜像大小
    && rm -rf /var/lib/apt/lists/* \
    # 验证 uvx 可用（基础镜像自带）
    && uvx --version

# ========== 安装 Python 依赖 ==========
# 先复制 requirements.txt
COPY requirements.txt .

# 安装项目依赖
RUN uv pip install -r requirements.txt

# 安装 OpenTelemetry
RUN uv pip install aws-opentelemetry-distro==0.12.2

# ========== 预下载 MCP Server 包（性能优化）==========
# ⚠️ 根本问题：Runtime 以 root 用户运行，但工具安装在 bedrock_agentcore 用户目录
#
# 诊断日志确认：
# - 当前用户: root, HOME: /root
# - 传递 UV_TOOL_DIR=/home/bedrock_agentcore/.local/share/uv/tools
# - 结果：uvx 无法访问或不信任其他用户的工具，重新下载 botocore
#
# ✅ 解决方案：使用 root 用户安装工具
# - uv tool install 会将包安装到 /root/.local/share/uv/tools/
# - Runtime 以 root 运行时能直接访问这些预装工具
# - uvx 识别预装工具，跳过下载阶段
# - 避免每次都重新下载 botocore (13.9MB) 等大依赖
#
# 预期效果：MCP 加载从 8+ 秒降低到 2-3 秒（性能提升 60%+）
USER root
ENV UV_TOOL_BIN_DIR=/root/.local/bin \
    UV_TOOL_DIR=/root/.local/share/uv/tools
RUN uv tool install awslabs.cost-explorer-mcp-server==0.0.14 && \
    uv tool install awslabs.aws-pricing-mcp-server==1.0.20 && \
    uv tool install awslabs.aws-documentation-mcp-server==1.1.13 && \
    uv tool install awslabs.billing-cost-management-mcp-server==0.0.7 && \
    uv tool install awslabs.cloudtrail-mcp-server==0.0.6 && \
    uv tool install fastmcp && \
    echo "✅ MCP 工具安装完成（版本已锁定，root 用户，缓存在 /root/.local/share/uv/tools/）"

# ========== OpenTelemetry 可观测性配置 ==========
# ⚠️ 重要：AgentCore Runtime 会自动注入 OpenTelemetry 配置
#
# 根据 AWS 官方文档和工程师指导：
# - Runtime-hosted agents 不需要在 Dockerfile 中设置 OTEL_* 环境变量
# - Runtime 会在平台层面自动配置 OpenTelemetry
# - ADOT 的 aws_configurator 会自动处理 traces、logs、metrics 导出
#
# 参考文档：
# - https://aws.amazon.com/blogs/machine-learning/build-trustworthy-ai-agents-with-amazon-bedrock-agentcore-observability/
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html
#
# 依赖说明：
# - requirements.txt 中已包含 aws-opentelemetry-distro==0.12.2
# - 这是唯一需要的 OpenTelemetry 依赖
# - opentelemetry-instrument 命令会自动使用 Runtime 注入的配置
#
# 自动配置内容（由 Runtime 平台提供）：
# - Traces：自动导出到 AWS X-Ray
# - Logs：自动导出到 CloudWatch Logs
# - Metrics：由 Runtime 平台管理
# - Session Tracking：自动关联
# - Resource Attributes：自动生成
#
# ❌ 不要手动设置以下环境变量（会被 Runtime 覆盖或导致冲突）：
# - OTEL_PYTHON_DISTRO
# - OTEL_PYTHON_CONFIGURATOR
# - OTEL_TRACES_SAMPLER
# - OTEL_RESOURCE_ATTRIBUTES
# - OTEL_SERVICE_NAME
# - OTEL_PROPAGATORS
# - OTEL_LOG_LEVEL
# - OTEL_METRICS_EXPORTER
# - OTEL_EXPORTER_OTLP_*
#
# ========== 结束 OpenTelemetry 配置 ==========

# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# ========== uvx 缓存环境变量（Runtime 运行时必须）==========
# ⚠️ 关键：uvx 需要知道预安装工具的位置
# - UV_TOOL_BIN_DIR: 工具符号链接目录
# - UV_TOOL_DIR: 工具虚拟环境目录（等同于 ~/.local/share/uv/tools）
#
# 不设置这些变量时，uvx 会：
# 1. 在临时目录创建新的虚拟环境
# 2. 重新下载 botocore 等依赖（13.9MB）
# 3. 导致 MCP 加载耗时 7+ 秒
#
# 设置后，uvx 会：
# 1. 直接使用 /root/.local/share/uv/tools/ 中的预装工具
# 2. 无需下载任何依赖
# 3. MCP 加载耗时降低到 2-3 秒
#
# 注意：这些环境变量已在前面设置，此处保留注释说明
# ENV UV_TOOL_BIN_DIR=/root/.local/bin \
#     UV_TOOL_DIR=/root/.local/share/uv/tools

# ========== 保持 root 用户运行 ==========
# Runtime 以 root 用户运行，与预装工具的用户一致
USER root

EXPOSE 9000
EXPOSE 8000
EXPOSE 8080

# Copy only necessary files for AgentCore Runtime
COPY backend/ ./backend/
COPY config/ ./config/
COPY run.py ./run.py

# Use the full module path (agent_runtime.py 在 backend/agent/ 目录下)

CMD ["opentelemetry-instrument", "python", "-m", "backend.agent.agent_runtime"]
