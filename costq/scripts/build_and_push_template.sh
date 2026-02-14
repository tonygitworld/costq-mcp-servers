#!/bin/bash
#
# 构建 Docker 镜像并推送到 ECR（通用模板）
#
# 用途：将 MCP Server 打包成 ARM64 镜像并上传到 AWS ECR
#
# 使用方法（两种方式）：
#
#   方式 1 - 作为可重用脚本（推荐）：
#     bash costq/scripts/build_and_push_template.sh <mcp-server-name>
#     示例：bash costq/scripts/build_and_push_template.sh cloudtrail-mcp-server
#
#   方式 2 - 复制并创建专用脚本：
#     1. cp build_and_push_template.sh 01-build_and_push_<mcp-server-name>.sh
#     2. 修改 MCP_SERVER_NAME 变量
#     3. bash costq/scripts/01-build_and_push_<mcp-server-name>.sh
#

set -e  # 遇到错误立即退出

# =============================================================================
# 参数解析
# =============================================================================
# 如果提供了命令行参数，使用参数作为 MCP_SERVER_NAME
if [ -n "$1" ]; then
    MCP_SERVER_NAME="$1"
    echo "📦 使用命令行参数: MCP_SERVER_NAME=${MCP_SERVER_NAME}"
else
    # 否则使用脚本中的默认值（用于方式 2）
    MCP_SERVER_NAME="${MCP_SERVER_NAME:-<mcp-server-name>}"
fi

# 验证 MCP_SERVER_NAME 不是占位符
if [ "$MCP_SERVER_NAME" = "<mcp-server-name>" ]; then
    echo "❌ 错误：未提供 MCP Server 名称"
    echo ""
    echo "用法："
    echo "  bash $0 <mcp-server-name>"
    echo ""
    echo "示例："
    echo "  bash $0 cloudtrail-mcp-server"
    echo "  bash $0 billing-cost-management-mcp-server"
    echo ""
    exit 1
fi

# =============================================================================
# 配置
# =============================================================================
AWS_PROFILE="3532"                         # AWS CLI Profile
AWS_REGION="ap-northeast-1"                # AWS 区域
AWS_ACCOUNT="000451883532"                 # AWS 账号 ID
ECR_REPO="awslabs-mcp/${MCP_SERVER_NAME}"  # ECR 仓库路径
IMAGE_TAG="v$(date +%Y%m%d-%H%M%S)"        # 镜像标签（自动生成时间戳）

# 计算完整的 ECR URI
ECR_URI="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
FULL_IMAGE="${ECR_URI}:${IMAGE_TAG}"

# =============================================================================
# 输出横幅
# =============================================================================
echo "============================================================"
echo "🚀 构建并推送 MCP Server 镜像"
echo "============================================================"
echo "MCP Server: ${MCP_SERVER_NAME}"
echo "ECR 仓库: ${ECR_URI}"
echo "镜像标签: latest, ${IMAGE_TAG}"
echo "平台: linux/arm64"
echo "============================================================"
echo ""

# =============================================================================
# Step 1: 登录 ECR
# =============================================================================
echo "🔐 Step 1: 登录 ECR..."
AWS_PROFILE=${AWS_PROFILE} aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com

if [ $? -eq 0 ]; then
    echo "✅ ECR 登录成功"
    echo ""
else
    echo "❌ ECR 登录失败"
    exit 1
fi

# =============================================================================
# Step 1.5: 检查并创建 ECR 仓库
# =============================================================================
echo "📦 Step 1.5: 检查 ECR 仓库是否存在..."

# 尝试获取仓库信息
if AWS_PROFILE=${AWS_PROFILE} aws ecr describe-repositories \
  --repository-names ${ECR_REPO} \
  --region ${AWS_REGION} \
  > /dev/null 2>&1; then
    echo "✅ ECR 仓库已存在: ${ECR_REPO}"
    echo ""
else
    echo "⚠️  ECR 仓库不存在，正在创建..."

    if AWS_PROFILE=${AWS_PROFILE} aws ecr create-repository \
      --repository-name ${ECR_REPO} \
      --region ${AWS_REGION} \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256 \
      --tags Key=Project,Value=CostQ Key=MCP,Value=${MCP_SERVER_NAME} \
      > /dev/null 2>&1; then
        echo "✅ ECR 仓库创建成功: ${ECR_REPO}"
        echo ""
    else
        echo "❌ ECR 仓库创建失败"
        exit 1
    fi
fi

# =============================================================================
# Step 2: 构建 ARM64 镜像
# =============================================================================
echo "🔨 Step 2: 构建 ARM64 Docker 镜像（使用缓存）..."
echo "   ⚠️  首次构建可能需要 5-10 分钟，后续构建会更快..."
echo ""

# 获取脚本所在目录，然后切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MCP_SERVER_DIR="${PROJECT_ROOT}/src/${MCP_SERVER_NAME}"

echo "   📁 项目根目录: ${PROJECT_ROOT}"
echo "   📁 MCP Server 目录: ${MCP_SERVER_DIR}"
echo ""

# 检查目录是否存在
if [ ! -d "${MCP_SERVER_DIR}" ]; then
    echo "❌ 错误：MCP Server 目录不存在: ${MCP_SERVER_DIR}"
    echo "   请检查 MCP_SERVER_NAME 配置是否正确"
    exit 1
fi

# 检查 Dockerfile 是否存在
if [ ! -f "${MCP_SERVER_DIR}/Dockerfile-AgentCore-Runtime" ]; then
    echo "❌ 错误：Dockerfile-AgentCore-Runtime 不存在"
    echo "   请先创建 Dockerfile-AgentCore-Runtime 文件"
    exit 1
fi

# 拷贝 cred_extract_services 到 MCP Server 目录（仅当不存在时）
SHARED_CRED_DIR="${PROJECT_ROOT}/costq/shared/cred_extract_services"
TARGET_CRED_DIR="${MCP_SERVER_DIR}/cred_extract_services"
CRED_COPIED=false  # 标记是否进行了拷贝

if [ -d "${TARGET_CRED_DIR}" ]; then
    echo "ℹ️  使用 MCP Server 自带的 cred_extract_services"
    echo ""
elif [ -d "${SHARED_CRED_DIR}" ]; then
    echo "📋 从 shared 目录拷贝 cred_extract_services..."
    cp -r "${SHARED_CRED_DIR}" "${TARGET_CRED_DIR}"
    CRED_COPIED=true
    echo "✅ cred_extract_services 拷贝完成（构建后将自动清理）"
    echo ""
else
    echo "⚠️  警告：MCP Server 和 shared 目录都没有 cred_extract_services"
    echo ""
fi

# 在 MCP Server 目录下构建（Dockerfile 的 COPY 命令需要相对路径）
cd "${MCP_SERVER_DIR}"

docker buildx build \
  --platform linux/arm64 \
  -f Dockerfile-AgentCore-Runtime \
  -t ${FULL_IMAGE} \
  --load \
  .

BUILD_STATUS=$?

# 构建完成后清理临时拷贝的 cred_extract_services（不污染源码目录）
if [ "${CRED_COPIED}" = true ] && [ -d "${TARGET_CRED_DIR}" ]; then
    echo "🧹 清理临时拷贝的 cred_extract_services..."
    rm -rf "${TARGET_CRED_DIR}"
    echo "✅ 清理完成"
    echo ""
fi

if [ $BUILD_STATUS -eq 0 ]; then
    echo ""
    echo "✅ 镜像构建成功"
    echo ""
else
    echo ""
    echo "❌ 镜像构建失败"
    exit 1
fi

# =============================================================================
# Step 3: 打标签并推送到 ECR
# =============================================================================
echo "🏷️  Step 3: 打标签..."
docker tag ${FULL_IMAGE} ${ECR_URI}:latest
echo "✅ 标签已创建: latest, ${IMAGE_TAG}"
echo ""

echo "📤 Step 4: 推送镜像到 ECR..."
docker push ${FULL_IMAGE}
docker push ${ECR_URI}:latest

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 镜像推送成功"
    echo ""
else
    echo ""
    echo "❌ 镜像推送失败"
    exit 1
fi

# =============================================================================
# 完成
# =============================================================================
echo "============================================================"
echo "✅ 镜像部署完成!"
echo "============================================================"
echo "MCP Server: ${MCP_SERVER_NAME}"
echo "镜像标签: latest, ${IMAGE_TAG}"
echo "镜像 URI: ${FULL_IMAGE}"
echo ""
echo "⚠️  下一步操作："
echo "   1. 更新 Runtime:"
echo "      aws bedrock-agentcore-control update-runtime \\"
echo "        --profile ${AWS_PROFILE} \\"
echo "        --region ${AWS_REGION} \\"
echo "        --runtime-identifier <runtime-id> \\"
echo "        --container-image ${ECR_URI}:latest"
echo ""
echo "   2. 刷新 Gateway（参考 DEEPV.md）"
echo ""
echo "   3. 验证部署:"
echo "      kubectl logs -f -n costq-fastapi deployment/costq-fastapi"
echo ""
