# AWS Spans 追踪分析

## Trace 分析

找到2个错误相关的 Trace ID:
- `69702bae01cfdc8a06bea2f96423a1f8` (09:28:23 - 09:29:00，共64个事件)
- `697029612ed1091e0ee553ed13b0a667` (09:18:33 - 09:19:22，共65个事件)

## 关键时间线分析 (Trace: 697029612ed1091e0ee553ed13b0a667)

### 阶段1: 初始化 (09:18:33)
```
[1-3] Initialize MCP连接
[4-5] notifications/initialized
[6-8] tools/list (获取工具列表)
[9-11] tools/list (再次获取)
```

### 阶段2: 第一轮失败的调用 (09:18:49-50)

```
[12-23] 6个并发的 tools/call 请求启动
[24] ✓ get_sp_coverage - 开始执行
[25] ❌ get_sp_coverage - 执行失败
[26] ❌ 错误: filter_expression 类型错误 (string vs object)

[27] ✓ get_ri_utilization - 开始执行
[28] ❌ get_ri_utilization - 执行失败
[29] ❌ 错误: filter_expression 类型错误

[30-32] get_ri_utilization - 同样的错误
[33-38] get_ri_coverage - 同样的错误
[39-41] get_sp_utilization - 同样的错误
```

**所有6个调用都在Gateway层失败，耗时仅 2-4ms！**

### 阶段3: 第二轮成功的调用 (09:18:57 - 09:19:08)

```
[42-49] 4个新的 tools/call 请求启动
        注意：这次请求中 filter_expression 参数消失了！

[50] ✓ get_sp_utilization - 开始执行 (无filter)
[54] ✓ get_sp_utilization - 成功! (耗时 3.5秒)

[51] ✓ get_ri_utilization - 开始执行 (无filter)
[57] ✓ get_ri_utilization - 成功! (耗时 11秒)

[52] ✓ get_ri_coverage - 开始执行 (无filter)
[55] ✓ get_ri_coverage - 成功! (耗时 3.6秒)

[53] ✓ get_sp_coverage - 开始执行 (无filter)
[56] ✓ get_sp_coverage - 成功! (耗时 4.2秒)
```

**所有4个调用都成功，因为没有 filter_expression 参数！**

## 关键发现

### 1. 错误发生极快 (2-4ms)

```
09:18:50.022 - 开始执行 get_sp_coverage
09:18:50.025 - 失败 (仅3ms!)
09:18:50.025 - 返回参数验证错误
```

这说明：
- ✅ Gateway 在接收请求后立即进行参数验证
- ✅ 验证失败后立即返回错误，不会转发到后端
- ✅ RISP MCP Server 根本没有机会收到这些请求

### 2. 成功vs失败的对比

#### 失败的请求（有 filter_expression）
- 执行时间: 2-4ms
- 结果: Parameter validation failed
- 错误: `string found, object expected`

#### 成功的请求（无 filter_expression）
- 执行时间: 3.5-11秒
- 结果: 成功返回数据
- 说明: 请求被正确转发到 RISP MCP Server 并执行

### 3. 并发调用模式

模型会并发发起多个工具调用：
- 第一轮: 6个并发请求（全部失败）
- 第二轮: 4个并发请求（全部成功，因为移除了 filter_expression）

### 4. Span层级结构

每个工具调用都有自己的独立 Span：
```
Trace: 697029612ed1091e0ee553ed13b0a667
  ├─ Span: b8ab31c0... (get_sp_coverage - 失败)
  ├─ Span: 651f5306... (get_ri_utilization - 失败)
  ├─ Span: 04860984... (get_ri_utilization - 失败)
  ├─ Span: 6d3e0400... (get_sp_utilization - 失败)
  ├─ Span: 9891f29a... (get_ri_coverage - 失败)
  ├─ Span: c304650e... (get_ri_coverage - 失败)
  └─ ... (后续成功的调用)
```

## 调用链完整流程

```
模型 (Claude Sonnet)
  ↓ 生成6个工具调用，包含 filter_expression (字符串)

AgentCore Runtime
  ↓ 转发到 Gateway (字符串格式保持不变)

Gateway (参数验证层)
  ↓ 检查 inputSchema
  ↓ 发现: filter_expression 是 string
  ↓ 期望: filter_expression 是 object 或 null
  ✗ 验证失败! (仅2-4ms)
  ↓ 返回错误给 AgentCore Runtime

RISP MCP Server
  ✗ 从未收到请求
```

## 后续分析重点

1. Gateway 从哪里获取的 inputSchema？
2. RISP MCP Server 定义的 filter_expression 类型是什么？
3. 为什么模型会把对象参数序列化成字符串？
