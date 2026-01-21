# Phase 4: 部署问题分析

## 📋 部署信息

**部署时间:** 2026-01-21 10:20 AM
**测试时间:** 2026-01-21 10:24 AM
**问题:** 模型仍然传递 dict 而非 JSON 字符串

---

## ❌ 错误现象

**用户提问时间:** 10:24 AM

**调用参数:**
```json
{
  "start_date": "2026-01-17",
  "end_date": "2026-01-21",
  "granularity": "DAILY",
  "filter_expression": {
    "Dimensions": {
      "Key": "SERVICE",
      "Values": ["Amazon Elastic Compute Cloud - Compute"]
    }
  },
  "target_account_id": "859082029538"
}
```

**错误信息:**
```
Error executing tool get_sp_utilization: 1 validation error for get_savings_plans_utilization
Arguments
filter_expression
  Input should be a valid string [type=string_type, input_value={'Dimensions': {'Key': 'S...pute Cloud - Compute']}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
```

---

## 🔍 问题分析

### 1. ✅ 代码修改正确

**证据:**
- 本地测试通过 (Phase 3)
- 容器测试通过
- 参数类型已改为 `Optional[str]`
- JSON 解析逻辑已添加
- Pydantic 验证正在工作 (检测到 dict 不是 string)

### 2. ✅ 镜像构建和推送成功

**镜像信息:**
- 镜像 URI: `000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/costq-risp-mcp-server:latest`
- 镜像标签: `v20260121-102056`
- 构建时间: 2026-01-21 10:20:56 AM
- 镜像大小: 258MB
- 镜像摘要: `sha256:f9d6ff5252fb084195f8148cab78768e5ff82fb311cc21661578201368c87da9`

### 3. ✅ Runtime 已更新

**Runtime 信息:**
```json
{
  "agentRuntimeId": "costq_risp_mcp_production-6ypFN96HS4",
  "agentRuntimeName": "costq_risp_mcp_production",
  "agentRuntimeVersion": "2",
  "status": "READY",
  "lastUpdatedAt": "2026-01-21T02:23:12.851280+00:00",  // UTC
  "containerImage": "000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/costq-risp-mcp-server:v20260121-102056"
}
```

**时间转换:**
- UTC: 2026-01-21 02:23:12
- 东京时间 (UTC+9): 2026-01-21 11:23:12

**结论:** Runtime 在 11:23 AM 更新,使用的是最新镜像 `v20260121-102056`

### 4. ❌ Gateway 可能未刷新

**问题根源:**

虽然 Runtime 已经更新到最新镜像,但 **Gateway 缓存了旧的 OpenAPI Schema**,导致:

1. **Gateway 的 Schema 还是旧的:**
   - `filter_expression` 类型: `object` (旧)
   - 应该是: `string` (新)

2. **模型基于 Gateway Schema 构造参数:**
   - 模型看到的Schema说 `filter_expression` 是 `object`
   - 所以模型传递了 dict 对象
   - 但 Runtime 期望 string,导致 Pydantic 验证失败

**问题链:**
```
Gateway (旧Schema: object)
    ↓
模型读取 Schema,认为参数是 object
    ↓
模型构造参数: filter_expression = {...}  (dict)
    ↓
请求发送到 Runtime
    ↓
Runtime (新代码: string)
    ↓
Pydantic 验证: ❌ dict is not string
    ↓
返回错误给用户
```

---

## 🔧 解决方案

### 方案1: 刷新 Gateway (推荐)

Gateway 需要重新从 Runtime 读取 OpenAPI Schema。

**可能的刷新方法:**

#### 方法A: 通过 AWS CLI (首选)

根据 AWS Bedrock AgentCore 架构,Gateway 应该有刷新命令:

```bash
# 尝试1: update-gateway
aws bedrock-agentcore-control update-gateway \
  --profile 3532 \
  --region ap-northeast-1 \
  --gateway-identifier costq-aws-mcp-gateway-production-c3svyct5ay

# 尝试2: restart-gateway
aws bedrock-agentcore-control restart-gateway \
  --profile 3532 \
  --region ap-northeast-1 \
  --gateway-identifier costq-aws-mcp-gateway-production-c3svyct5ay

# 尝试3: refresh-tools
aws bedrock-agentcore-control refresh-tools \
  --profile 3532 \
  --region ap-northeast-1 \
  --gateway-identifier costq-aws-mcp-gateway-production-c3svyct5ay
```

**状态:** ❌ 这些命令都不存在

**建议:** 需要联系 AWS 支持或查看最新的 bedrock-agentcore-control 文档。

#### 方法B: 通过 EKS 重启 Gateway Pod

根据 DEEPV.md,Gateway 可能部署在 EKS 上:

```bash
# 1. 配置 kubectl
aws eks update-kubeconfig \
  --profile 3532 \
  --region ap-northeast-1 \
  --name costq-eks-cluster

# 2. 查找 Gateway Pod
kubectl get pods -A | grep gateway

# 3. 重启 Gateway Pod
kubectl rollout restart deployment/<gateway-deployment-name> -n <namespace>

# 或者直接删除 Pod (会自动重建)
kubectl delete pod <gateway-pod-name> -n <namespace>
```

**状态:** ⏳ 待确认

#### 方法C: 等待 Gateway 自动刷新

Gateway 可能有自动刷新机制(如每小时或每天):

**预估时间:** 未知 (可能 1-24 小时)

**优点:** 不需要手动操作
**缺点:** 时间不可控

---

### 方案2: 临时使用旧的参数类型 (不推荐)

**回滚到 dict 类型:**
- 将 `filter_expression: Optional[str]` 改回 `Optional[dict]`
- 移除 JSON 解析逻辑

**问题:**
- ❌ 不解决根本问题
- ❌ 依然会有 Schema 生成问题
- ❌ 与最佳实践不符

**结论:** **不推荐**,我们应该坚持修复而不是回滚。

---

### 方案3: 修改 Gateway 绑定的 Runtime (实验性)

**思路:** 创建新的 Runtime,让 Gateway 重新绑定

```bash
# 1. 创建新的 Runtime (新 ID)
aws bedrock-agentcore-control create-agent-runtime \
  --agent-runtime-name costq_risp_mcp_production_v2 \
  ...

# 2. 更新 Gateway 绑定
aws bedrock-agentcore-control update-gateway \
  --gateway-identifier costq-aws-mcp-gateway-production-c3svyct5ay \
  --runtime-id <new-runtime-id>
```

**状态:** ⏳ 需要测试

---

## 📊 时间线

| 时间 (北京时间) | 事件 | 状态 |
|-----------------|------|------|
| 10:20:56 | 构建镜像 v20260121-102056 | ✅ 完成 |
| 10:21:30 | 推送镜像到 ECR | ✅ 完成 |
| 11:23:12 | Runtime 更新到最新镜像 | ✅ 完成 |
| 10:24:00 | 用户测试,报错 | ❌ 失败 |
| 11:30:00 | 本地容器测试 | ✅ 通过 |

**分析:** Runtime 更新时间(11:23)比用户测试时间(10:24)晚,说明用户测试时 Runtime 还是旧版本。

**等等!时间不对!**

让我重新检查时间:
- **lastUpdatedAt:** `2026-01-21T02:23:12` (这是 UTC 时间)
- **UTC+8 (北京时间):** 2026-01-21 10:23:12
- **用户测试时间:** 10:24

所以 **Runtime 在 10:23 AM 更新,用户在 10:24 AM 测试**。

Runtime 已经是最新的了!

---

## 🎯 核心结论

### 问题不在 Runtime,而在 Gateway!

**证据:**
1. ✅ Runtime 已在 10:23 更新到最新镜像
2. ✅ 用户在 10:24 测试 (Runtime 已是最新)
3. ❌ 仍然报错: dict 不是 string
4. ✅ Pydantic 验证工作正常 (说明新代码在运行)

**矛盾点:**
- 新代码期望 `string`
- 模型传递 `dict`
- **说明模型读取的 Schema 还是旧的 (type: object)**

**结论:**
**Gateway 缓存了旧的 OpenAPI Schema,没有重新从 Runtime 读取!**

---

## ⏭️ 下一步操作

### 立即行动 (高优先级)

1. **刷新 Gateway** - 这是唯一的解决方案

2. **验证 Schema** - 刷新后检查 Gateway 返回的 Schema 是否正确

3. **重新测试** - 用相同的参数再次测试

### 长期改进

1. **添加自动刷新机制** - Gateway 应该在 Runtime 更新后自动刷新

2. **添加 Schema 版本控制** - 避免 Schema 不一致问题

3. **添加监控和告警** - Runtime 和 Gateway Schema 不一致时告警

---

## 📝 刷新 Gateway 的方法 (待实施)

### 需要确认的问题

1. ❓ Gateway 的刷新命令是什么?
2. ❓ Gateway 部署在哪里? (EKS? Lambda? Fargate?)
3. ❓ Gateway 的自动刷新周期是多久?
4. ❓ 如何手动触发 Gateway 重新加载 Schema?

### 推荐咨询

**建议:** 向熟悉 Bedrock AgentCore Gateway 的团队成员咨询正确的刷新方法。

---

**分析完成时间:** 2026-01-21 11:30 AM
**分析人员:** DeepV Code AI Assistant
**结论:** 代码修改正确,问题在于 Gateway Schema 缓存未刷新
