# SP 覆盖率查询失败 - 最终诊断报告

**日期**: 2026-01-19
**问题**: `costq-risp-mcp-dev___get_sp_coverage` 工具持续失败
**状态**: 🔴 **未解决** - 已排除多个可能原因，但问题依然存在

---

## 📊 问题现象

用户查询"本月至今的sp覆盖率"时：

1. ✅ Agent 正常调用 `costq-risp-mcp-dev___get_sp_coverage` 工具
2. ❌ Gateway 调用 target `D23VGQCN2A` (RISP MCP Runtime) **6ms 后失败**
3. ❌ 返回通用错误: `InternalServerException - An internal error occurred. Please retry later.`
4. ✅ Agent 自动降级到备用工具 `aws-billing-cost-management-mcp-server___sp-performance` 成功

---

## 🔍 已排除的原因

### ❌ 1. Gateway Target 同步问题

**测试**: 手动触发同步
```bash
aws bedrock-agentcore-control synchronize-gateway-targets \
  --gateway-identifier costq-aws-mcp-servers-gateway-lyg-gfqjxiflzv \
  --target-id-list D23VGQCN2A
```

**结果**:
- ✅ 同步成功完成
- ✅ `lastSynchronizedAt` 更新到 `12:57:02`
- ✅ Target 状态: `READY`
- ❌ **问题依然存在** (12:59 再次测试仍失败)

---

### ❌ 2. Gateway Target 配置错误

**对比分析**: 成功 target (ZYMHB09DFM) vs 失败 target (D23VGQCN2A)

| 配置项 | 失败 Target | 成功 Target | 结论 |
|--------|-------------|-------------|------|
| 状态 | READY | READY | ✅ 相同 |
| Runtime ARN | 正确格式 | 正确格式 | ✅ 相同 |
| OAuth 配置 | 完全一致 | 完全一致 | ✅ 相同 |
| Endpoint | 标准 HTTPS | 标准 HTTPS | ✅ 相同 |

**结论**: 配置结构完全正确，无差异

---

### ❌ 3. OAuth 认证失败

**测试**: 检查 workload-identity-directory 日志

**结果**: 所有 OAuth 操作全部成功
```json
// Gateway 获取 OAuth Token
{
  "operation_name": "GetResourceOauth2Token",
  "response_type": "Success",
  "response_payload": {
    "AccessToken": "REDACTED",
    "TokenFetched": true,
    "TokenJti": "94d3cdd0-b8c7-45d1-bb2b-1a6227cde504"
  }
}

// RISP MCP Runtime 获取访问 Token
{
  "workload_identity_id": "costq_risp_mcp_dev_lyg-gdDA9aAoEP",
  "operation_name": "GetWorkloadAccessTokenForJWT",
  "response_type": "Success",
  "response_payload": {
    "WorkloadAccessToken": "REDACTED",
    "expires_in": 899
  }
}
```

**结论**: OAuth 认证完全正常

---

### ❌ 4. Runtime 状态异常

**测试**: 检查 Runtime 和 Endpoint 状态

```bash
# Runtime 状态
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id costq_risp_mcp_dev_lyg-gdDA9aAoEP
```

**结果**:
- ✅ Runtime 状态: `READY`
- ✅ Runtime 版本: `3`
- ✅ Network mode: `PUBLIC`
- ✅ Endpoint 状态: `READY`
- ✅ 最后更新: `12:27:57`

**结论**: Runtime 完全健康

---

### ❌ 5. RISP MCP Runtime 未收到请求

**证据**: RISP MCP Runtime 日志组完全没有工具调用记录

```bash
# 查询 RISP MCP Runtime 日志
aws logs tail /aws/bedrock-agentcore/runtimes/costq_risp_mcp_dev_lyg-gdDA9aAoEP-DEFAULT \
  --since 30m --profile 3532 --region ap-northeast-1
```

**结果**:
- ✅ 健康检查 (Ping) 正常 (每 2 秒一次)
- ❌ **无任何 `tools/call` 或 `get_sp_coverage` 日志**
- ❌ **无任何 ERROR 或 Exception 日志**

**结论**: Gateway 的 HTTP 请求根本未到达 RISP MCP Runtime

---

## 🎯 当前诊断

### 问题定位

**Gateway 在调用 RISP MCP Runtime 时，HTTP 请求在 Gateway 内部失败，未发送到 Runtime。**

### 证据链

| 时间点 | 组件 | 事件 | 日志来源 |
|--------|------|------|----------|
| 12:59:06.703 | Gateway | 接收工具调用请求 | Gateway 日志 ✅ |
| 12:59:06.788 | Gateway | 开始执行 `from target D23VGQCN2A` | Gateway 日志 ✅ |
| 12:59:06.788 | Gateway | OAuth Token 获取成功 | workload-identity 日志 ✅ |
| 12:59:06.795 | Gateway | **调用失败 (ERROR)** | Gateway 日志 ❌ |
| 12:59:06.795 | Gateway | 返回 `InternalServerException` | Gateway 日志 ❌ |
| 12:59:06 | RISP MCP Runtime | **未收到任何请求** | RISP MCP 日志 ⚠️ |

**关键观察**:
- ⚠️ **仅耗时 7ms** (12:59:06.788 → 12:59:06.795)
- ⚠️ OAuth Token 已成功获取
- ⚠️ Gateway 未发起实际的 HTTP 调用

---

## 💡 可能的原因（待验证）

### 1. **Gateway 内部路由失败** ⭐（最有可能）

**假设**: Gateway 在内部路由表中查找 target `D23VGQCN2A` 时失败

**可能原因**:
- Gateway 缓存了错误的路由映射
- Target endpoint URL 格式有问题（虽然配置看起来正确）
- Gateway 内部的 service mesh 或 load balancer 配置错误

**验证方法**:
```bash
# 1. 重启 Gateway（如果支持）
# 2. 删除并重建 Target
# 3. 联系 AWS Support 检查 Gateway 内部状态
```

---

### 2. **Runtime Endpoint URL 问题**

**假设**: Endpoint URL 虽然格式正确，但 Gateway 解析或访问时失败

**当前 Endpoint**:
```
https://bedrock-agentcore.ap-northeast-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aap-northeast-1%3A000451883532%3Aruntime%2Fcostq_risp_mcp_dev_lyg-gdDA9aAoEP/invocations?qualifier=DEFAULT
```

**可能问题**:
- URL 编码的 ARN 解析失败
- `qualifier=DEFAULT` 参数处理错误
- Runtime endpoint 的 DNS 解析失败（但网络是 PUBLIC）

---

### 3. **Gateway 到 Runtime 的网络连接问题**

**假设**: Gateway 无法建立到 Runtime 的 HTTPS 连接

**可能原因**:
- Runtime 的安全组或网络配置阻止 Gateway 访问
- Runtime 的 VPC 配置问题（但 Runtime 是 PUBLIC 模式）
- TLS 握手失败

**矛盾点**:
- ✅ 成功的 target (ZYMHB09DFM) 使用相同的网络配置
- ✅ Runtime healthcheck 正常（说明 Runtime 可访问）

---

### 4. **Gateway 的 HTTP Client 配置问题**

**假设**: Gateway 调用不同 targets 时使用的 HTTP client 配置不同

**可能原因**:
- RISP MCP Runtime 的超时配置过短（7ms 就超时？）
- 连接池耗尽
- HTTP/2 vs HTTP/1.1 协议冲突

---

## 🛠️ 建议的后续操作

### 立即执行 🔴

#### 1. 删除并重建 Gateway Target

```bash
# 删除旧 Target
aws bedrock-agentcore-control delete-gateway-target \
  --gateway-identifier costq-aws-mcp-servers-gateway-lyg-gfqjxiflzv \
  --target-id D23VGQCN2A \
  --profile 3532 \
  --region ap-northeast-1

# 等待删除完成
sleep 30

# 重新创建 Target
aws bedrock-agentcore-control create-gateway-target \
  --gateway-identifier costq-aws-mcp-servers-gateway-lyg-gfqjxiflzv \
  --name costq-risp-mcp-dev-v2 \
  --target-configuration '{
    "mcp": {
      "mcpServer": {
        "endpoint": "https://bedrock-agentcore.ap-northeast-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aap-northeast-1%3A000451883532%3Aruntime%2Fcostq_risp_mcp_dev_lyg-gdDA9aAoEP/invocations?qualifier=DEFAULT"
      }
    }
  }' \
  --credential-provider-configurations '[
    {
      "credentialProviderType": "OAUTH",
      "credentialProvider": {
        "oauthCredentialProvider": {
          "providerArn": "arn:aws:bedrock-agentcore:ap-northeast-1:000451883532:token-vault/default/oauth2credentialprovider/costq-runtime-resource-provider-oauth-client",
          "scopes": [],
          "grantType": "CLIENT_CREDENTIALS"
        }
      }
    }
  ]' \
  --profile 3532 \
  --region ap-northeast-1

# 同步 Target
aws bedrock-agentcore-control synchronize-gateway-targets \
  --gateway-identifier costq-aws-mcp-servers-gateway-lyg-gfqjxiflzv \
  --target-id-list <NEW_TARGET_ID> \
  --profile 3532 \
  --region ap-northeast-1
```

---

#### 2. 联系 AWS Support

**问题描述模板**:

```
Subject: Gateway 调用 AgentCore Runtime 失败 (InternalServerException)

问题详情:
- Gateway ARN: arn:aws:bedrock-agentcore:ap-northeast-1:000451883532:gateway/costq-aws-mcp-servers-gateway-lyg-gfqjxiflzv
- Target ID: D23VGQCN2A
- Runtime ARN: arn:aws:bedrock-agentcore:ap-northeast-1:000451883532:runtime/costq_risp_mcp_dev_lyg-gdDA9aAoEP

现象:
1. Gateway 调用 target D23VGQCN2A 时始终失败（7ms 内返回 InternalServerException）
2. OAuth 认证成功
3. Target 配置正确且状态为 READY
4. Runtime 健康且状态为 READY
5. Runtime 完全未收到请求

对比:
- 同一 Gateway 的其他 targets (如 ZYMHB09DFM) 工作正常
- 配置结构完全一致

请求:
1. 检查 Gateway 内部日志中的详细错误信息
2. 检查 Gateway 到 Runtime 的网络连接状态
3. 检查是否有内部路由或配置缓存问题

相关 Trace IDs:
- 696e2a8447a3d40f4503f88779e8ba28 (12:59:06 失败的调用)
- 696e26d3636e41fe6db672c77e53b0b8 (12:43:49 失败的调用)
```

---

### 短期内 🟡

#### 3. 使用备用工具作为主要方案

**当前状态**: Agent 已自动降级到 `aws-billing-cost-management-mcp-server___sp-performance`，功能完全正常。

**建议**:
- 暂时将备用工具作为主要方案
- 在系统提示词中明确引导 Agent 优先使用备用工具
- 继续调查 RISP MCP 问题，但不影响用户使用

---

## 📊 总结

### 已确认的事实

| 组件 | 状态 | 证据 |
|------|------|------|
| Gateway 配置 | ✅ 正确 | 配置对比完全一致 |
| OAuth 认证 | ✅ 成功 | workload-identity 日志全部 Success |
| Target 同步 | ✅ 完成 | lastSynchronizedAt 已更新 |
| Runtime 状态 | ✅ 健康 | status=READY, healthcheck 正常 |
| Runtime Endpoint | ✅ 正常 | status=READY |
| Gateway → Runtime 调用 | ❌ **失败** | 7ms 内失败，未发起实际请求 |

### 问题核心

**Gateway 内部在调用 RISP MCP Runtime 时失败，具体原因未知（可能是内部路由、网络连接或 HTTP client 配置问题）。**

### 影响范围

- ✅ **功能未受影响**: Agent 自动降级机制生效
- ⚠️ **用户体验稍差**: 首次工具调用失败，额外 5-7 秒延迟
- 🔍 **需要深入调查**: 可能需要 AWS Support 协助

---

**报告生成时间**: 2026-01-19 21:30
**分析人**: DeepV Code AI Assistant
**下一步**: 联系 AWS Support 或重建 Gateway Target
