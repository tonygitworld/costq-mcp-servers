# 更新 AgentCore Runtime 镜像

## 📦 新镜像信息

**构建时间:** 2024-12-24 16:17:33
**镜像标签:** `v20251224-161733`
**镜像 URI:** `000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251224-161733`
**更新内容:** 集成 Calculator 工具（strands_tools.calculator）

---

## 🎯 更新步骤

### 方式 1: AWS 控制台（推荐）

1. **打开 AgentCore Runtime 控制台**
   - Region: `ap-northeast-1` (Tokyo)
   - 服务: Amazon Bedrock → AgentCore → Runtimes
   - 或直接访问: https://ap-northeast-1.console.aws.amazon.com/bedrock/home?region=ap-northeast-1#/agentcore/runtimes

2. **选择 Runtime**
   - 生产环境: `cosq_agentcore_runtime_production`
   - 开发环境: `cosq_agentcore_runtime_development`

3. **更新镜像配置**
   - 点击 "Edit" 或 "Update"
   - 找到 "Container image URI" 字段
   - 替换为新的镜像 URI:
     ```
     000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251224-161733
     ```
   - 点击 "Save" 或 "Update"

4. **等待更新完成**
   - 状态会从 "Updating" 变为 "Active"
   - 通常需要 1-2 分钟

5. **验证更新**
   - 查看 Runtime 详情，确认镜像 URI 已更新
   - 检查状态为 "Active"

---

### 方式 2: AWS CLI

```bash
# 设置变量
export AWS_PROFILE=3532
export RUNTIME_NAME="cosq_agentcore_runtime_production"  # 或 cosq_agentcore_runtime_development
export NEW_IMAGE_URI="000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251224-161733"
export REGION="ap-northeast-1"

# 更新 Runtime 镜像
aws bedrock-agentcore update-runtime \
  --runtime-name $RUNTIME_NAME \
  --container-image-uri $NEW_IMAGE_URI \
  --region $REGION \
  --profile $AWS_PROFILE

# 查看更新状态
aws bedrock-agentcore get-runtime \
  --runtime-name $RUNTIME_NAME \
  --region $REGION \
  --profile $AWS_PROFILE
```

---

## 🧪 测试 Calculator 工具

### 测试用例 1: 简单算术

**查询:**
```
请帮我计算 2 + 2
```

**预期行为:**
- Agent 调用 calculator 工具
- 返回 "4"

---

### 测试用例 2: 成本增长率计算

**查询:**
```
我的 EC2 成本上个月从 $980 增长到 $1250，增长了多少百分比？
```

**预期行为:**
- Agent 调用 calculator 工具
- 计算表达式: `((1250 - 980) / 980) * 100`
- 返回 "约 27.55%" 或类似结果

---

### 测试用例 3: RI 节省计算

**查询:**
```
如果我购买 1 年期 Standard RI（折扣率 72%），On-Demand 价格是 $1500/月，能节省多少钱？
```

**预期行为:**
- Agent 调用 calculator 工具
- 计算表达式: `1500 * (1 - 0.72)`
- 返回 "$420/月" 或类似结果

---

### 测试用例 4: 多服务成本汇总

**查询:**
```
计算 EC2 ($450.20)、S3 ($320.10)、Lambda ($89.50) 和 RDS ($120) 的总成本
```

**预期行为:**
- Agent 调用 calculator 工具
- 计算表达式: `450.20 + 320.10 + 89.50 + 120`
- 返回 "$979.80"

---

## 🔍 验证 Calculator 集成

### 检查点 1: 查看 CloudWatch 日志

**日志组:**
- 生产环境 Runtime:
  - `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/cosq_agentcore_runtime_production-5x9j6eBjmZ`
- 开发环境 Runtime:
  - `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/cosq_agentcore_runtime_development-49gbDzHm0G`

**查找关键日志:**
```
# Agent 创建成功日志
✅ Agent创建完成 - Tools: X (含Calculator)

# 或生产环境日志
"has_calculator": true, "tool_count": X
```

**预期结果:**
- `has_calculator: true`
- `tool_count` 比之前多 1（多了 calculator）

---

### 检查点 2: 测试工具调用

**方法 1: 通过前端 UI**
1. 登录 CostQ 前端
2. 发送测试查询（如上述测试用例）
3. 查看响应是否包含精确的数值计算

**方法 2: 通过 Python SDK**

```python
import boto3
import json

client = boto3.client('bedrock-agentcore-runtime', region_name='ap-northeast-1')

response = client.invoke_agent(
    runtimeArn='arn:aws:bedrock-agentcore:ap-northeast-1:000451883532:runtime/cosq_agentcore_runtime_production-5x9j6eBjmZ',
    inputText='请帮我计算 2 + 2',
    sessionId='test-calculator-session',
    sessionState={
        'memoryId': 'CostQ_Pro-77Jh0OAr3A'  # 生产环境 Memory ID
    }
)

# 解析流式响应
for event in response['completion']:
    if 'chunk' in event:
        chunk = event['chunk']
        print(json.loads(chunk['bytes'].decode()))
```

**预期输出:**
- 响应中包含 "4"
- 工具调用日志中显示 `calculator` 工具被调用

---

## 📊 更新前后对比

### 更新前
- 工具数量: N（仅 MCP 工具）
- 数学计算: Agent 自己估算（可能不准确）
- 适用场景: 成本查询、优化建议

### 更新后
- 工具数量: N+1（MCP 工具 + calculator）
- 数学计算: 精确计算（SymPy 底层）
- 适用场景: 成本查询 + 精确计算 + 优化建议

---

## ⚠️ 注意事项

### 1. Runtime 更新影响
- **不影响现有会话**: 正在进行的对话会继续使用旧容器
- **新会话使用新镜像**: 新创建的会话会使用更新后的镜像
- **无需重启**: AgentCore 自动管理容器生命周期

### 2. Calculator 工具特性
- **自带工具描述**: 无需修改 System Prompt
- **SymPy 底层**: 支持符号数学、方程求解
- **精度可控**: 默认 10 位小数精度

### 3. 回滚方案
如果新镜像出现问题，可以回滚到之前的版本：

```bash
# 查看历史镜像版本
aws ecr describe-images \
  --repository-name costq-agentcore \
  --region ap-northeast-1 \
  --profile 3532 \
  --query 'sort_by(imageDetails,&imagePushedAt)[-5:]' \
  --output table

# 回滚到之前的版本（替换为实际的镜像 URI）
aws bedrock-agentcore update-runtime \
  --runtime-name cosq_agentcore_runtime_production \
  --container-image-uri 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251203-XXXXXX \
  --region ap-northeast-1 \
  --profile 3532
```

---

## 📝 更新记录

| 日期 | 镜像版本 | 更新内容 | 负责人 |
|------|---------|---------|--------|
| 2024-12-24 | v20251224-161733 | 集成 Calculator 工具 | - |

---

## 🆘 故障排查

### 问题 1: Runtime 状态卡在 "Updating"

**原因:** 镜像拉取失败或容器启动超时

**解决方案:**
1. 检查镜像 URI 是否正确
2. 确认 ECR 权限配置正确
3. 查看 CloudWatch 日志中的错误信息
4. 等待超时后自动回滚（约 10 分钟）

---

### 问题 2: Calculator 工具未被调用

**原因:** Agent 未识别到计算需求

**解决方案:**
1. 使用更明确的查询（如"请计算..."、"帮我算一下..."）
2. 检查日志确认 calculator 工具已加载
3. 验证工具数量是否增加

---

### 问题 3: 计算结果不准确

**原因:** Calculator 表达式解析错误

**解决方案:**
1. 简化表达式，分步计算
2. 检查 CloudWatch 日志中的 calculator 调用参数
3. 验证 Agent 是否正确提取了数值

---

## 📞 支持

如有问题，请查看：
- CloudWatch 日志组（见上方）
- Git 提交: `b1bcf1b`
- 文档: `docs/calculator_integration_changes.md`
