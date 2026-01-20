#!/bin/bash

# AgentCore Runtime 部署验证脚本
# 用途：快速验证 Runtime 部署状态

set -e

RUNTIME_ID="${1:-cosq_agentcore_runtime_development-49gbDzHm0G}"
REGION="ap-northeast-1"
PROFILE="3532"

echo "============================================================"
echo "🔍 AgentCore Runtime 部署验证"
echo "============================================================"
echo "Runtime ID: $RUNTIME_ID"
echo "Region: $REGION"
echo ""

# 1. 检查 Runtime 状态
echo "📊 Step 1: 检查 Runtime 状态..."
RUNTIME_INFO=$(aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id "$RUNTIME_ID" \
  --region "$REGION" \
  --profile "$PROFILE" \
  --output json)

STATUS=$(echo "$RUNTIME_INFO" | jq -r '.status')
VERSION=$(echo "$RUNTIME_INFO" | jq -r '.agentRuntimeVersion')
IMAGE=$(echo "$RUNTIME_INFO" | jq -r '.agentRuntimeArtifact.containerConfiguration.containerUri')

echo "  状态: $STATUS"
echo "  版本: $VERSION"
echo "  镜像: $IMAGE"
echo ""

if [ "$STATUS" != "READY" ]; then
  echo "❌ Runtime 状态异常: $STATUS"
  exit 1
fi

echo "✅ Runtime 状态正常"
echo ""

# 2. 检查最近的调用日志
echo "📝 Step 2: 检查最近的调用日志（最近 5 分钟）..."
LOG_GROUP="/aws/bedrock-agentcore/runtimes/${RUNTIME_ID}-DEFAULT"

RECENT_LOGS=$(aws logs tail "$LOG_GROUP" \
  --since 5m \
  --region "$REGION" \
  --profile "$PROFILE" \
  --format short 2>/dev/null | head -20)

if [ -z "$RECENT_LOGS" ]; then
  echo "⚠️  最近 5 分钟没有新日志（可能没有新请求）"
else
  echo "✅ 发现最近的日志："
  echo "$RECENT_LOGS" | head -10
fi
echo ""

# 3. 检查错误日志
echo "🔍 Step 3: 检查最近的错误日志..."
ERROR_LOGS=$(aws logs tail "$LOG_GROUP" \
  --since 10m \
  --filter-pattern "ERROR" \
  --region "$REGION" \
  --profile "$PROFILE" \
  --format short 2>/dev/null | head -10)

if [ -z "$ERROR_LOGS" ]; then
  echo "✅ 最近 10 分钟没有错误日志"
else
  echo "⚠️  发现错误日志："
  echo "$ERROR_LOGS"
fi
echo ""

# 4. 验证关键配置
echo "🔧 Step 4: 验证关键配置..."
ENCRYPTION_KEY=$(echo "$RUNTIME_INFO" | jq -r '.environmentVariables.ENCRYPTION_KEY')
MEMORY_ID=$(echo "$RUNTIME_INFO" | jq -r '.environmentVariables.MEMORY_RESOURCE_ID')
RDS_SECRET=$(echo "$RUNTIME_INFO" | jq -r '.environmentVariables.RDS_SECRET_NAME')

if [ -z "$ENCRYPTION_KEY" ] || [ "$ENCRYPTION_KEY" == "null" ]; then
  echo "❌ ENCRYPTION_KEY 缺失"
  exit 1
fi

if [ -z "$MEMORY_ID" ] || [ "$MEMORY_ID" == "null" ]; then
  echo "⚠️  MEMORY_RESOURCE_ID 缺失（Memory 功能将被禁用）"
else
  echo "✅ Memory 配置正常: $MEMORY_ID"
fi

if [ -z "$RDS_SECRET" ] || [ "$RDS_SECRET" == "null" ]; then
  echo "❌ RDS_SECRET_NAME 缺失"
  exit 1
fi

echo "✅ 所有关键配置完整"
echo ""

# 5. 总结
echo "============================================================"
echo "✅ 部署验证完成！"
echo "============================================================"
echo "Runtime 状态: $STATUS"
echo "版本: $VERSION"
echo "镜像: $(basename $IMAGE)"
echo ""
echo "📝 下一步："
echo "  1. 访问前端界面创建新会话"
echo "  2. 发送测试查询"
echo "  3. 观察日志输出格式"
echo "============================================================"
