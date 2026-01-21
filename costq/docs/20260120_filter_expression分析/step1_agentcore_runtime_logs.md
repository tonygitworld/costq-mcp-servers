# AgentCore Runtime 日志分析

## 日志组
`/aws/bedrock-agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ-DEFAULT`

## 关键发现

### 1. 模型生成的参数（Claude Sonnet构造的）

在日志中可以看到，模型生成的 `filter_expression` 参数是一个**字符串**：

```json
{
  "name": "costq-risp-mcp-production___get_sp_coverage",
  "arguments": {
    "end_date": "2026-01-21",
    "granularity": "DAILY",
    "filter_expression": "{\"Dimensions\": {\"Key\": \"SERVICE\", \"Values\": [\"Amazon Elastic Compute Cloud - Compute\"]}}",
    "start_date": "2026-01-17",
    "target_account_id": "859082029538"
  }
}
```

**关键证据：`filter_expression` 是一个JSON字符串，不是对象**

### 2. 错误消息

```
JsonSchemaException - Parameter validation failed: Invalid request parameters:
- Field 'filter_expression' has invalid type: $.filter_expression: string found, object expected
- Field 'filter_expression' has invalid type: $.filter_expression: string found, null expected
```

### 3. 原始日志片段

#### 模型生成的工具调用（01:18:49 UTC）

```json
{
  "tool_calls": [
    {
      "type": "function",
      "id": "tooluse_SAvyjbFBGiDY9JY5FgKn7b",
      "function": {
        "name": "costq-risp-mcp-production___get_sp_coverage",
        "arguments": {
          "end_date": "2026-01-21",
          "granularity": "DAILY",
          "filter_expression": "{\"Dimensions\": {\"Key\": \"SERVICE\", \"Values\": [\"Amazon Elastic Compute Cloud - Compute\"]}}",
          "start_date": "2026-01-17",
          "target_account_id": "859082029538"
        }
      }
    }
  ]
}
```

#### 错误返回（01:18:50 UTC）

```json
{
  "content": [
    {
      "text": "JsonSchemaException - Parameter validation failed: Invalid request parameters:\n- Field 'filter_expression' has invalid type: $.filter_expression: string found, object expected\n- Field 'filter_expression' has invalid type: $.filter_expression: string found, null expected"
    }
  ],
  "id": "tooluse_SAvyjbFBGiDY9JY5FgKn7b"
}
```

## 结论

1. **模型（Claude Sonnet）生成的参数**：`filter_expression` 是一个JSON字符串
2. **验证器期望**：期望 `filter_expression` 是一个对象（object）或 null
3. **问题根源**：模型将复杂对象参数序列化成了字符串，而不是直接传递对象

## 下一步

需要查看：
1. Gateway 日志 - 确认 Gateway 如何处理和转发这个参数
2. RISP MCP Server 日志 - 确认服务端接收到的参数格式
3. RISP MCP Server 代码 - 确认参数类型定义
