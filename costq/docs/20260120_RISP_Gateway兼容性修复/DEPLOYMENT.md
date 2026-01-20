# RISP MCP Server - 部署指南

**日期**: 2026-01-20
**版本**: v20260120-184725
**状态**: ✅ 已构建并推送到 ECR

---

## 📦 镜像信息

| 项目 | 值 |
|------|-----|
| **MCP Server** | costq-risp-mcp-server |
| **ECR 仓库** | 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/costq-risp-mcp-server |
| **镜像标签** | latest, v20260120-184725 |
| **镜像 URI** | 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/costq-risp-mcp-server:latest |
| **平台** | linux/arm64 |
| **Digest** | sha256:53dcfee1bd8390fb921c4aab13bdd72e86cd4592c78fe31eae6b5b50bcb4660b |

---

## ✅ 本地测试结果

### 容器测试

```bash
$ bash costq/scripts/build_and_test_risp_mcp_local.sh

✅ 镜像构建成功
✅ 容器启动成功 (耗时: 9s)
✅ MCP Server 响应正常 (HTTP 200 OK)
✅ Gateway 兼容性测试通过
```

### 兼容性验证

在容器内运行的测试：

```bash
$ docker exec costq-risp-mcp-test python3 -c "..."

✅ 测试 1 通过: Gateway dict 对象
✅ 测试 2 通过: Stdio JSON 字符串
✅ 测试 3 通过: None 值

🎉 所有容器内测试通过！Gateway 兼容性修复成功！
```

---

## 🚀 部署步骤

### Step 1: 更新 AgentCore Runtime

**查找 Runtime ID**:
```bash
aws bedrock-agentcore-control list-runtimes \
  --profile 3532 \
  --region ap-northeast-1 \
  --query 'runtimeSummaries[?contains(runtimeName, `risp`)].runtimeIdentifier' \
  --output text
```

**更新 Runtime 镜像**:
```bash
# 替换 <runtime-id> 为实际的 Runtime ID
aws bedrock-agentcore-control update-runtime \
  --profile 3532 \
  --region ap-northeast-1 \
  --runtime-identifier <runtime-id> \
  --container-image 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/costq-risp-mcp-server:latest
```

**验证更新**:
```bash
aws bedrock-agentcore-control get-runtime \
  --profile 3532 \
  --region ap-northeast-1 \
  --runtime-identifier <runtime-id> \
  --query 'runtime.containerImage' \
  --output text
```

### Step 2: 刷新 Gateway

**⚠️ 关键步骤！必须执行！**

根据 DEEPV.md 中的说明刷新 Gateway，确保 Gateway 使用最新的 Runtime 镜像。

刷新方法：
1. 登录 AWS Console
2. 进入 Bedrock AgentCore Gateway 管理页面
3. 找到对应的 Gateway
4. 点击 "Refresh" 或 "Reload"

或者使用 CLI（如果有相应命令）：
```bash
# 参考 DEEPV.md 中的刷新命令
```

### Step 3: 验证部署

**检查 Runtime 日志**:
```bash
# 如果 Runtime 部署在 EKS
kubectl logs -f -n costq-fastapi deployment/costq-fastapi

# 或者通过 CloudWatch Logs
aws logs tail /aws/bedrock-agentcore/runtimes/<runtime-name> \
  --profile 3532 \
  --region ap-northeast-1 \
  --follow
```

**测试 MCP 工具调用**:

通过 Agent 测试一个简单的查询：
```
用户提示: "查询 2026-01-16 到 2026-01-20 的 EC2 RI 使用率"

期望结果:
- ✅ 工具调用成功（get_ri_utilization）
- ✅ filter_expression 参数正确处理
- ✅ 返回数据格式正确
```

---

## 🧪 测试用例

### 测试用例 1: 简单查询（无 filter）

**提示词**:
```
查询最近 7 天的 Reserved Instance 使用率
```

**预期工具调用**:
```json
{
  "tool": "get_ri_utilization",
  "parameters": {
    "start_date": "2026-01-13",
    "end_date": "2026-01-20",
    "granularity": "DAILY"
  }
}
```

**验证点**:
- ✅ 工具调用成功
- ✅ 返回使用率数据
- ✅ 日志无异常

### 测试用例 2: 带 filter 的查询（关键测试）

**提示词**:
```
查询 EC2 服务在 2026-01-16 到 2026-01-20 的 RI 使用率
```

**预期工具调用**:
```json
{
  "tool": "get_ri_utilization",
  "parameters": {
    "start_date": "2026-01-16",
    "end_date": "2026-01-20",
    "granularity": "DAILY",
    "filter_expression": {
      "Dimensions": {
        "Key": "SERVICE",
        "Values": ["Amazon Elastic Compute Cloud - Compute"]
      }
    }
  }
}
```

**验证点**:
- ✅ **filter_expression 作为 dict 对象传递（Gateway 模式）**
- ✅ **parse_json_parameter 正确处理 dict 对象**
- ✅ **无 JsonSchemaException 错误**
- ✅ 返回正确的过滤结果

### 测试用例 3: 复杂 filter（嵌套 And/Or）

**提示词**:
```
查询 us-east-1 或 us-west-2 区域的 EC2 RI 覆盖率
```

**预期工具调用**:
```json
{
  "tool": "get_ri_coverage",
  "parameters": {
    "start_date": "2026-01-16",
    "end_date": "2026-01-20",
    "granularity": "DAILY",
    "filter_expression": {
      "And": [
        {
          "Dimensions": {
            "Key": "SERVICE",
            "Values": ["Amazon Elastic Compute Cloud - Compute"]
          }
        },
        {
          "Or": [
            {"Dimensions": {"Key": "REGION", "Values": ["us-east-1"]}},
            {"Dimensions": {"Key": "REGION", "Values": ["us-west-2"]}}
          ]
        }
      ]
    }
  }
}
```

**验证点**:
- ✅ 复杂嵌套结构正确处理
- ✅ 无解析错误
- ✅ 返回正确的多区域数据

---

## 📊 性能指标

### 构建性能

| 阶段 | 耗时 |
|------|------|
| ECR 登录 | ~2s |
| 镜像构建（缓存） | ~14s |
| 镜像推送 | ~5s |
| **总计** | **~21s** |

### 运行时性能

| 指标 | 值 |
|------|-----|
| 容器启动时间 | ~9s |
| MCP Server 就绪 | ~2s |
| 内存占用 | ~150MB |
| CPU 占用 | <5% |

---

## 🔍 故障排查

### 问题 1: JsonSchemaException 仍然出现

**原因**: Gateway 未刷新

**解决方案**:
1. 确认 Runtime 已更新到 latest 镜像
2. **刷新 Gateway**（关键步骤）
3. 清除浏览器缓存（如果通过 Web UI 访问）
4. 重新测试

### 问题 2: 工具调用超时

**原因**: Runtime 冷启动或数据库连接问题

**解决方案**:
1. 检查 Runtime 日志是否有错误
2. 验证数据库连接配置（RDS_SECRET_NAME）
3. 确认 IAM Role 权限正确
4. 增加超时时间（如果需要）

### 问题 3: filter_expression 解析错误

**原因**: 参数类型不匹配

**解决方案**:
1. 检查容器内 utils/json_parser.py 是否存在
2. 验证代码是否正确部署（检查镜像 SHA）
3. 查看详细错误日志
4. 运行容器内测试验证

---

## 📝 回滚计划

如果部署后发现问题，按以下步骤回滚：

### Step 1: 查找上一个版本

```bash
aws ecr describe-images \
  --profile 3532 \
  --region ap-northeast-1 \
  --repository-name awslabs-mcp/costq-risp-mcp-server \
  --query 'imageDetails[*].[imageTags[0],imagePushedAt]' \
  --output table
```

### Step 2: 回滚 Runtime

```bash
aws bedrock-agentcore-control update-runtime \
  --profile 3532 \
  --region ap-northeast-1 \
  --runtime-identifier <runtime-id> \
  --container-image 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/costq-risp-mcp-server:<previous-version>
```

### Step 3: 刷新 Gateway

重复部署步骤中的 Gateway 刷新操作。

### Step 4: 验证回滚

确认工具调用正常，无新的错误。

---

## 📞 支持信息

**问题反馈**: GitHub Issues
**技术支持**: @tonygitworld
**文档维护**: DeepV AI Assistant

**相关文档**:
- [README.md](./README.md) - 问题分析与解决方案
- [CHANGES.md](./CHANGES.md) - 详细变更清单
- [DEEPV.md](../../../DEEPV.md) - 执行规范

---

## ✅ 部署检查清单

部署前确认：
- [x] 代码修改已完成（json_parser.py + handlers）
- [x] 本地测试通过（容器 + Gateway 兼容性）
- [x] 镜像已构建并推送到 ECR
- [ ] Runtime 已更新到 latest 镜像
- [ ] Gateway 已刷新
- [ ] 功能测试通过（3 个测试用例）
- [ ] 日志监控正常（无异常）
- [ ] 文档已更新（README + CHANGES + DEPLOYMENT）

部署后验证：
- [ ] 简单查询正常（无 filter）
- [ ] 带 filter 查询正常（关键）
- [ ] 复杂 filter 查询正常（嵌套）
- [ ] 性能指标符合预期
- [ ] 无错误日志
- [ ] 无内存/CPU 异常

---

**部署状态**: 🟡 待部署
**下一步**: 更新 Runtime 并刷新 Gateway
