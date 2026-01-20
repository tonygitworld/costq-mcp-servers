# Runtime 镜像构建和部署指南

**构建时间**: 2025-12-14
**镜像仓库**: `000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore`
**目标平台**: `linux/arm64`

---

## 🚀 快速开始

### 前置条件检查

```bash
# 1. 检查 Docker Desktop 是否运行
docker info

# 如果报错 "Cannot connect to the Docker daemon"，需要启动 Docker Desktop
# macOS: 打开 "应用程序" -> "Docker.app"
# 或使用 Spotlight: Cmd+Space -> 输入 "Docker"

# 2. 确认 AWS CLI 配置
aws sts get-caller-identity --profile 3532

# 3. 确认当前目录
pwd
# 应该在: /Users/liyuguang/data/gitworld/tonygithub/strands-agent-demo/deployment/agentcore
```

---

## 📦 步骤1: 启动 Docker Desktop

### macOS 启动方式

**方式A: Spotlight 搜索**
```
1. 按 Cmd+Space
2. 输入 "Docker"
3. 按 Enter 启动
4. 等待菜单栏显示 Docker 图标（鲸鱼图标）
5. 图标稳定后（不再跳动）即可使用
```

**方式B: 应用程序文件夹**
```
1. 打开 "访达" (Finder)
2. 前往 "应用程序"
3. 找到 "Docker.app"
4. 双击启动
```

**验证 Docker 已启动**:
```bash
# 等待 30-60 秒后执行
docker info

# 应该看到类似输出:
# Server:
#  Containers: 5
#  Running: 2
#  ...
```

---

## 🔨 步骤2: 构建镜像

### 自动构建（推荐）

```bash
# 切换到 agentcore 目录
cd /Users/liyuguang/data/gitworld/tonygithub/strands-agent-demo/deployment/agentcore

# 执行构建脚本
./01-build_and_push.sh
```

**预期输出**:
```
============================================================
🚀 构建并推送 CostQ Agent 镜像
============================================================
ECR 仓库: 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore
镜像标签: latest, v20251214-XXXXXX
平台: linux/arm64
============================================================

🔐 Step 1: 登录 ECR...
Login Succeeded
✅ ECR 登录成功

🔨 Step 2: 构建 ARM64 Docker 镜像（使用缓存）...
[+] Building 120.5s (15/15) FINISHED
...

🚀 Step 3: 推送镜像到 ECR...
The push refers to repository [000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore]
...
v20251214-131630: digest: sha256:abc123... size: 1234

✅ 镜像推送成功！

============================================================
📦 镜像信息
============================================================
仓库: 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore
标签:
  - latest
  - v20251214-131630

🎯 下一步: 更新 AgentCore Runtime
============================================================
AWS Console:
  https://console.aws.amazon.com/bedrock/home?region=ap-northeast-1#/agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ

CLI 命令:
  aws bedrock-agentcore update-runtime \
    --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
    --image-uri 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251214-131630 \
    --region ap-northeast-1 \
    --profile 3532
============================================================
```

**构建时间**:
- 首次构建: ~5-10 分钟（下载依赖）
- 后续构建: ~2-3 分钟（使用缓存）

---

### 手动构建（故障排查）

如果自动脚本失败，可以手动执行：

```bash
# 1. 设置变量
export AWS_PROFILE=3532
export ECR_REPO=000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore
export IMAGE_TAG=v$(date +%Y%m%d-%H%M%S)

# 2. 登录 ECR
aws ecr get-login-password --region ap-northeast-1 --profile 3532 | \
  docker login --username AWS --password-stdin $ECR_REPO

# 3. 构建镜像
docker buildx build \
  --platform linux/arm64 \
  -t $ECR_REPO:latest \
  -t $ECR_REPO:$IMAGE_TAG \
  --load \
  .

# 4. 推送镜像
docker push $ECR_REPO:latest
docker push $ECR_REPO:$IMAGE_TAG

# 5. 记录镜像 URI
echo "新镜像 URI: $ECR_REPO:$IMAGE_TAG"
```

---

## 🧪 步骤3: 本地验证（可选）

在部署到生产前，可以本地测试镜像：

```bash
# 1. 运行容器
docker run --rm \
  -e AWS_PROFILE=3532 \
  -e AWS_REGION=ap-northeast-1 \
  -e BEDROCK_REGION=us-west-2 \
  -e DATABASE_URL="postgresql://..." \
  -v ~/.aws:/root/.aws:ro \
  -p 8080:8080 \
  $ECR_REPO:latest

# 2. 新开终端测试
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "列出所有成本优化工具",
    "user_id": "test-user",
    "session_id": "test-session"
  }'

# 3. 检查输出
# 应该包含 billing-cost-management 相关工具
```

---

## 🚀 步骤4: 部署到生产环境

### 方式A: AWS Console（推荐，可视化）

1. **登录 AWS Console**
   - 账号: 000451883532
   - 区域: ap-northeast-1 (Tokyo)
   - Profile: 3532

2. **前往 Bedrock AgentCore**
   ```
   服务 -> Amazon Bedrock -> AgentCore -> Runtimes
   ```

3. **选择 Runtime**
   - 找到: `cosq_agentcore_runtime_production-5x9j6eBjmZ`
   - 或: `costq_agent-sgOtcqG1zS`（根据实际名称）

4. **更新镜像**
   - 点击 "Edit" 或 "Update Runtime"
   - 找到 "Container Image URI" 字段
   - 粘贴新镜像 URI（从构建输出复制）:
     ```
     000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251214-XXXXXX
     ```
   - 点击 "Save" 或 "Update"

5. **等待部署完成**
   - 状态变为 "Available" (~2-5 分钟)
   - 刷新页面确认状态

---

### 方式B: AWS CLI（快速）

```bash
# 从构建输出复制镜像 URI
NEW_IMAGE_URI="000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251214-XXXXXX"

# 更新 Runtime
aws bedrock-agentcore update-runtime \
  --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
  --image-uri $NEW_IMAGE_URI \
  --region ap-northeast-1 \
  --profile 3532

# 检查状态
aws bedrock-agentcore get-runtime \
  --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
  --region ap-northeast-1 \
  --profile 3532 \
  --query 'runtime.status'
```

---

## ✅ 步骤5: 验证部署

### 5.1 运行测试脚本

```bash
cd /Users/liyuguang/data/gitworld/tonygithub/strands-agent-demo/deployment/agentcore

# 简单调用测试
python test_simple.py

# 完整 Agent 测试
python test_agent.py

# Memory 功能测试（如果启用）
python test_memory.py
```

**预期输出**:
```
✅ Simple invocation: SUCCESS
✅ Agent test: SUCCESS (tools loaded: ~67)
✅ Memory test: SUCCESS
```

---

### 5.2 检查 Runtime 日志

```bash
# 查看最新日志
aws logs tail /aws/bedrock-agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ-DEFAULT \
  --follow \
  --region ap-northeast-1 \
  --profile 3532
```

**关键检查点**:
1. ✅ 工具加载成功: `"billing-cost-management MCP client created"`
2. ✅ 无 OpenTelemetry 警告: 无 `"Attempting to instrument while already instrumented"`
3. ✅ 无崩溃重启: 无 `"Runtime starting"` 在查询期间
4. ✅ 工具数量正确: `"All tools loaded: XX个"`

---

### 5.3 更新 EKS Pod（如需要）

如果也在 EKS 上运行，需要重启 Pod：

```bash
# 重启 FastAPI Pod
kubectl rollout restart deployment/costq-fastapi -n costq-fastapi

# 等待新 Pod 启动
kubectl get pods -n costq-fastapi -w

# 检查日志
kubectl logs -n costq-fastapi -l app=costq-fastapi -c app --tail=50
```

---

## 🧪 步骤6: 功能验证

### 快速验证清单

通过 Web UI 或 API 测试：

| 测试场景 | 测试查询 | 预期结果 | 状态 |
|---------|---------|---------|------|
| 工具加载 | "列出所有成本优化工具" | 包含 billing-cost-management 工具 | ⬜ |
| 基本优化 | "帮我找出成本优化机会" | 返回优化建议列表 | ⬜ |
| 性能评估 | "EC2 实例性能如何优化？" | 返回推荐 + 性能指标 | ⬜ |
| 新功能 | "我的预算使用情况如何？" | 返回预算状态（新功能） | ⬜ |

### Web UI 测试

1. 登录 CostQ Web UI
2. 在聊天界面输入测试查询
3. 验证响应内容
4. 确认无错误提示

### API 测试

```bash
# 测试基本功能
curl -X POST https://your-api-endpoint/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "获取成本优化建议",
    "user_id": "your-user-id"
  }'
```

---

## 📊 步骤7: 监控（48小时）

### 监控清单

| 监控项 | 工具 | 阈值 | 频率 |
|--------|------|------|------|
| Runtime 崩溃 | CloudWatch Logs | 0 崩溃 | 每小时 |
| OpenTelemetry 警告 | CloudWatch Logs | 0 警告 | 每小时 |
| 查询成功率 | Application Metrics | > 95% | 每小时 |
| 响应时间 | Application Metrics | < 5秒 | 每小时 |

### 监控命令

```bash
# 实时监控错误
aws logs tail /aws/bedrock-agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ-DEFAULT \
  --follow --filter-pattern "ERROR|崩溃|crash|timeout" \
  --region ap-northeast-1 --profile 3532

# 检查 OpenTelemetry 警告
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ-DEFAULT \
  --filter-pattern "Attempting to instrument" \
  --start-time $(date -u -v-1H +%s)000 \
  --region ap-northeast-1 \
  --profile 3532
```

---

## 🆘 故障排查

### 问题1: Docker daemon 未运行

**现象**: `Cannot connect to the Docker daemon`

**解决**:
```bash
# macOS
1. 打开 Docker Desktop 应用
2. 等待 Docker 图标出现在菜单栏
3. 重新运行构建脚本
```

---

### 问题2: ECR 登录失败

**现象**: `Error: Cannot perform an interactive login from a non TTY device`

**解决**:
```bash
# 检查 AWS 凭证
aws sts get-caller-identity --profile 3532

# 手动登录
aws ecr get-login-password --region ap-northeast-1 --profile 3532 | \
  docker login --username AWS --password-stdin 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com
```

---

### 问题3: 构建缓慢

**现象**: 构建超过 15 分钟

**解决**:
```bash
# 检查网络连接
ping pypi.org

# 清理 Docker 缓存（谨慎使用）
docker builder prune -a

# 重新构建（无缓存）
docker buildx build --no-cache --platform linux/arm64 -t ... .
```

---

### 问题4: Runtime 更新后仍使用旧镜像

**现象**: 验证时发现仍是旧功能

**解决**:
```bash
# 1. 确认镜像 URI 正确
aws bedrock-agentcore get-runtime \
  --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
  --region ap-northeast-1 \
  --profile 3532 \
  --query 'runtime.imageUri'

# 2. 检查 Runtime 状态
aws bedrock-agentcore get-runtime \
  --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
  --region ap-northeast-1 \
  --profile 3532 \
  --query 'runtime.status'

# 3. 如果状态异常，重新更新
aws bedrock-agentcore update-runtime \
  --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
  --image-uri $NEW_IMAGE_URI \
  --region ap-northeast-1 \
  --profile 3532
```

---

## 📋 完整检查清单

### 构建前
- [ ] Docker Desktop 已启动
- [ ] AWS CLI 配置正确（profile 3532）
- [ ] 当前目录正确（deployment/agentcore）

### 构建中
- [ ] ECR 登录成功
- [ ] 镜像构建成功（ARM64）
- [ ] 镜像推送成功
- [ ] 记录新镜像 URI

### 部署后
- [ ] Runtime 更新成功
- [ ] Runtime 状态为 Available
- [ ] 测试脚本通过
- [ ] CloudWatch 日志正常
- [ ] 无 OpenTelemetry 警告
- [ ] EKS Pod 重启（如需要）

### 验证后
- [ ] 4项功能测试通过
- [ ] 48小时监控正常
- [ ] 用户反馈正常

---

## 🎯 成功标准

部署成功的标志：

1. ✅ 新镜像成功推送到 ECR
2. ✅ Runtime 状态为 "Available"
3. ✅ 测试脚本全部通过
4. ✅ CloudWatch 日志无错误
5. ✅ OpenTelemetry 警告清零
6. ✅ 用户查询功能正常
7. ✅ 48小时无崩溃

---

**祝部署顺利！** 🚀

如有问题，请查看：
- 完整迁移计划: `docs/问题分析/20251214_migration_execution_plan_v2.md`
- 代码审查修复: `docs/问题分析/20251214_code_review_fixes.md`
