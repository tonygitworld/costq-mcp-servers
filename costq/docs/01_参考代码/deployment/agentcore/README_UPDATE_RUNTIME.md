# AgentCore Runtime 更新指南

## 📋 概述

`02-update_runtime.sh` 脚本用于优雅地更新 AgentCore Runtime，自动保留所有环境变量和配置。

## 🚀 使用方法

### 基本语法

```bash
./02-update_runtime.sh <image-tag> [runtime-id]
```

### 参数说明

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `image-tag` | ✅ 是 | 镜像标签（ECR 中的版本） | `v20251225-114227` |
| `runtime-id` | ❌ 否 | Runtime ID（默认：开发环境） | `cosq_agentcore_runtime_production-5x9j6eBjmZ` |

## 📖 使用示例

### 示例 1：更新开发环境（使用默认 Runtime ID）

```bash
# 构建并推送镜像
./01-build_and_push.sh

# 输出：镜像 URI: 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251225-114227

# 更新开发环境 Runtime（自动使用默认 ID）
./02-update_runtime.sh v20251225-114227
```

### 示例 2：更新生产环境（指定 Runtime ID）

```bash
# 构建并推送镜像
./01-build_and_push.sh

# 更新生产环境 Runtime
./02-update_runtime.sh v20251225-114227 cosq_agentcore_runtime_production-5x9j6eBjmZ
```

### 示例 3：同时更新多个环境

```bash
# 构建并推送镜像
./01-build_and_push.sh

IMAGE_TAG="v20251225-114227"

# 更新开发环境
./02-update_runtime.sh $IMAGE_TAG

# 更新生产环境
./02-update_runtime.sh $IMAGE_TAG cosq_agentcore_runtime_production-5x9j6eBjmZ
```

## 🔧 Runtime ID 配置

### 当前环境

| 环境 | Runtime ID |
|------|------------|
| 开发环境（默认） | `cosq_agentcore_runtime_development-49gbDzHm0G` |
| 生产环境 | `cosq_agentcore_runtime_production-5x9j6eBjmZ` |

### 查看 Runtime ID

```bash
# 列出所有 Runtime
aws bedrock-agentcore-control list-agent-runtimes \
  --region ap-northeast-1 \
  --profile 3532 \
  --output table

# 查看特定 Runtime 详情
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id "cosq_agentcore_runtime_development-49gbDzHm0G" \
  --region ap-northeast-1 \
  --profile 3532
```

## ✅ 脚本功能

脚本会自动执行以下步骤：

1. **📥 获取当前配置**
   - Runtime 版本
   - IAM 角色 ARN
   - 网络配置（VPC、子网、安全组）
   - 环境变量（全部 9 个）

2. **🔧 构建更新请求**
   - 保留所有现有配置
   - 仅更新镜像 URI

3. **⚙️ 执行更新**
   - 提交更新请求
   - 显示新版本号

4. **⏳ 等待完成**
   - 自动等待最多 60 秒
   - 5 秒轮询一次状态

5. **🔍 验证结果**
   - 确认镜像 URI 已更新
   - 确认环境变量完整保留
   - 显示更新摘要

## ⚠️ 注意事项

### 环境变量保留

✅ **脚本会自动保留以下配置**：
- AWS_DEFAULT_REGION
- AWS_REGION
- BEDROCK_ASSUME_ROLE_DURATION
- BEDROCK_CROSS_ACCOUNT_ROLE_ARN
- BEDROCK_MODEL_ID
- BEDROCK_REGION
- ENCRYPTION_KEY
- MEMORY_RESOURCE_ID
- RDS_SECRET_NAME

❌ **不要手动使用 `aws bedrock-agentcore-control update-agent-runtime` 命令**，否则环境变量会丢失！

### 新会话测试

Runtime 更新后，**必须新建会话**才能使用新容器：
1. 旧会话会继续使用旧容器（直到 session 过期）
2. 新会话会被路由到新容器

### 镜像标签格式

脚本期望的镜像标签格式：`vYYYYMMDD-HHMMSS`

示例：`v20251225-114227`

## 🐛 故障排查

### 问题 1：更新失败 - "InvalidParameterException"

**原因**：镜像不存在或 Runtime ID 错误

**解决**：
```bash
# 验证镜像存在
aws ecr describe-images \
  --repository-name costq-agentcore \
  --image-ids imageTag=v20251225-114227 \
  --region ap-northeast-1 \
  --profile 3532

# 验证 Runtime ID
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id "cosq_agentcore_runtime_development-49gbDzHm0G" \
  --region ap-northeast-1 \
  --profile 3532
```

### 问题 2：更新超时

**原因**：Runtime 更新需要时间拉取镜像

**解决**：
- 等待更多时间（可能需要 2-3 分钟）
- 手动检查状态：
  ```bash
  aws bedrock-agentcore-control get-agent-runtime \
    --agent-runtime-id "cosq_agentcore_runtime_development-49gbDzHm0G" \
    --region ap-northeast-1 \
    --profile 3532 \
    --output json | jq '.status'
  ```

### 问题 3：环境变量丢失

**原因**：手动使用 AWS CLI 更新时未包含 `--environment-variables`

**解决**：
- 使用 `02-update_runtime.sh` 脚本（自动保留环境变量）
- 或手动从备份恢复环境变量

## 📚 相关文档

- [01-build_and_push.sh](./01-build_and_push.sh) - 构建和推送镜像脚本
- [Dockerfile](./Dockerfile) - Runtime Docker 镜像定义
- [AWS AgentCore Runtime 文档](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-runtime.html)

## 🔗 快速链接

### AWS 控制台

- [开发环境 Runtime](https://console.aws.amazon.com/bedrock/home?region=ap-northeast-1#/agentcore/runtimes/cosq_agentcore_runtime_development-49gbDzHm0G)
- [生产环境 Runtime](https://console.aws.amazon.com/bedrock/home?region=ap-northeast-1#/agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ)
- [ECR 仓库](https://console.aws.amazon.com/ecr/repositories/private/000451883532/costq-agentcore?region=ap-northeast-1)

### CloudWatch 日志

- [开发环境 - Application Logs](https://console.aws.amazon.com/cloudwatch/home?region=ap-northeast-1#logsV2:log-groups/log-group/$252Faws$252Fvendedlogs$252Fbedrock-agentcore$252Fruntime$252FAPPLICATION_LOGS$252Fcosq_agentcore_runtime_development-49gbDzHm0G)
- [生产环境 - Application Logs](https://console.aws.amazon.com/cloudwatch/home?region=ap-northeast-1#logsV2:log-groups/log-group/$252Faws$252Fvendedlogs$252Fbedrock-agentcore$252Fruntime$252FAPPLICATION_LOGS$252Fcosq_agentcore_runtime_production-5x9j6eBjmZ)
