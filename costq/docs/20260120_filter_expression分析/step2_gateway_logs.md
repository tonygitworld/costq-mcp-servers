# Gateway 日志分析

## 日志组
`/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/costq-aws-mcp-gateway-production-c3svyct5ay`

## 关键发现

### 1. Gateway 传递的参数格式

从Gateway日志中可以看到，请求体的格式是（注意这里被截断了）：

```
{
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "costq-risp-mcp-production___get_sp_coverage",
    "_meta": {...},
    "arguments": {
      "end_date": "2026-01-21",
      "granularity": "DAILY",
      "filter_expression": "{\"Dimensions\": {\"Key\": \"SERVICE\", \"Values\": [\"Amazon Elastic Compute Cloud - Com...
      ...
    }
  }
}
```

**关键证据：在Gateway的请求体中，`filter_expression` 已经显示为字符串格式**

虽然日志被截断，但可以清楚看到 `filter_expression` 的值是一个字符串（注意引号）：
```
filter_expression={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon ElastiCache"]}}
```

### 2. Gateway 错误消息

```
Parameter validation failed: Invalid request parameters:
- Field 'filter_expression' has invalid type: $.filter_expression: string found, object expected
- Field 'filter_expression' has invalid type: $.filter_expression: string found, null expected
```

### 3. 两种情况对比

#### 成功的调用（没有filter_expression）:
```json
{
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "costq-risp-mcp-production___get_sp_utilization",
    "arguments": {
      "end_date": "2026-01-21",
      "granularity": "DAILY",
      "start_date": "2026-01-01",
      "target_account_id": "859082029538"
    }
  }
}
```

#### 失败的调用（有filter_expression）:
```json
{
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "costq-risp-mcp-production___get_sp_coverage",
    "arguments": {
      "end_date": "2026-01-21",
      "granularity": "DAILY",
      "filter_expression": "{\"Dimensions\": {\"Key\": \"SERVICE\", ...}}",  // ❌ 字符串
      "start_date": "2026-01-17",
      "target_account_id": "859082029538"
    }
  }
}
```

## 初步结论

1. **模型生成的参数**：`filter_expression` 是一个JSON字符串（来自AgentCore Runtime日志）
2. **Gateway传递的参数**：`filter_expression` 仍然是字符串（来自Gateway日志）
3. **错误位置**：错误发生在 Gateway → RISP MCP Server 的参数验证阶段
4. **问题根源**：Gateway 在验证参数时发现 `filter_expression` 是字符串，但 schema 期望是对象

## 下一步

需要确认：
1. RISP MCP Server 的 schema 定义 - `filter_expression` 应该是什么类型？
2. RISP MCP Server 的日志 - 服务端是否收到了这个请求？
3. 是 Gateway 的参数验证逻辑有问题，还是 RISP Server 的 schema 定义有问题？
