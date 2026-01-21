# RISP MCP Server 日志分析

## 日志组
`/aws/bedrock-agentcore/runtimes/costq_risp_mcp_production-6ypFN96HS4-DEFAULT`

## 关键发现

### 1. 没有接收到工具调用请求

在RISP MCP Server的日志中：
- ❌ 没有找到 `get_sp_coverage` 相关日志
- ❌ 没有找到 `get_ri_utilization` 相关日志
- ❌ 没有找到 `filter_expression` 相关日志
- ❌ 没有找到 `Parameter validation` 错误
- ❌ 没有找到 `tools/call` MCP请求
- ❌ 没有找到 `jsonrpc` 协议相关日志

### 2. 只有无效HTTP请求警告

日志中只有重复的无效HTTP请求警告：
```
WARNING:  Invalid HTTP request received.
```

## 重要结论

**参数验证错误发生在 Gateway 层，请求根本没有到达 RISP MCP Server！**

这个发现非常关键，说明：

1. **错误位置**：Gateway 在转发请求到 RISP MCP Server 之前就进行了参数验证
2. **验证失败**：Gateway 的参数验证逻辑发现 `filter_expression` 类型不匹配
3. **请求被拦截**：由于验证失败，请求没有被转发到 RISP MCP Server

## 调用链分析

```
模型(Claude)
  ↓ 生成参数: filter_expression = "{\"Dimensions\": ...}" (字符串)

AgentCore Runtime
  ↓ 转发参数: filter_expression = "{\"Dimensions\": ...}" (字符串)

Gateway
  ↓ 参数验证: ❌ 发现类型错误！
  |   期望: object 或 null
  |   实际: string
  ↓ 返回错误，请求被拦截

RISP MCP Server
  ✗ 从未收到请求
```

## 下一步分析重点

需要确认 Gateway 使用的 schema 定义来源：
1. Gateway 如何获取 RISP MCP Server 的工具 schema？
2. schema 中 `filter_expression` 的类型定义是什么？
3. 为什么模型会将对象参数序列化成字符串？
