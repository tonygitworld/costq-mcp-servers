# filter_expression 参数类型问题完整调研报告

## 📋 调研概述

**问题:** `costq-risp-mcp-server` 的 `filter_expression` 参数在调用时报 `JsonSchemaException`,提示类型不匹配。

**调研时间:** 2026-01-20

**调研范围:** 从AgentCore Runtime、Gateway、RISP MCP Server的日志分析,到代码定义、Schema生成、最佳实践研究。

## 🎯 核心发现

### 根本原因

`costq-risp-mcp-server` 将 `filter_expression` 定义为 `Optional[dict]` 类型,导致FastMCP生成的OpenAPI Schema中**缺少 `type: object` 定义**。Bedrock AgentCore在Schema验证时将输入错误地解释为 `string` 类型,触发验证失败。

### 正确做法 (参考 billing-cost-management-mcp-server)

1. **参数定义:** `Optional[str]` (字符串类型)
2. **调用时:** 传递JSON字符串,如 `"{\"Dimensions\": {...}}"`
3. **内部处理:** 使用 `json.loads()` 将字符串解析为dict
4. **传递给AWS API:** 解析后的dict对象

## 📂 文档结构

```
20260120_filter_expression分析/
├── README.md                              # 本文档 - 调研总览
├── step1_agentcore_runtime_logs.md        # AgentCore日志分析
├── step2_gateway_logs.md                  # Gateway日志分析
├── step3_risp_mcp_server_logs.md          # RISP MCP日志分析
├── step3.5_aws_spans.md                   # AWS X-Ray追踪分析
├── step4_sp_handler_code_analysis.md      # sp_handler.py代码分析
├── step5_schema_comparison.md             # Schema定义对比分析
├── step6_根本原因分析.md                   # 根本原因和解决方案 ⭐
└── step6.1_补充_max_results参数问题.md     # 补充案例对比
```

## 🔍 调研步骤总结

### Step 1: AgentCore Runtime 日志分析
- **发现:** 确认 `JsonSchemaException` 错误存在
- **证据:** `$.filter_expression: string found, object expected`
- **结论:** 错误发生在Bedrock AgentCore的Schema验证阶段

### Step 2: Gateway 日志分析
- **发现:** Gateway接收到的 `filter_expression` 是字典的字符串表示
- **证据:** `filter_expression={"Dimensions": {"Key": "SERVICE", ...}}`
- **结论:** 参数格式符合预期,但Schema验证失败

### Step 3: RISP MCP Server 日志分析
- **发现:** 无相关错误日志
- **结论:** 请求在到达RISP MCP Server之前就被AgentCore/Gateway拒绝了

### Step 3.5: AWS Spans 追踪分析
- **发现:** X-Ray trace确认错误源于AgentCore的Schema验证
- **证据:** 完整的调用链和错误堆栈
- **结论:** 验证了错误发生的准确位置和调用流程

### Step 4: sp_handler.py 代码分析
- **发现:** `filter_expression` 定义为 `Optional[dict]`
- **证据:** 第605行左右的参数定义
- **结论:** Python代码明确期望接收字典对象

### Step 5: Schema 定义对比分析
- **关键发现:** Gateway的Schema中 `filter_expression` **缺少 `type: object` 定义**
- **对比:** 其他参数如 `granularity` 正确包含 `"type": "string"`
- **结论:** Schema生成存在缺陷,导致验证失败

### Step 6: 根本原因分析和解决方案 ⭐
- **研究对象:** `billing-cost-management-mcp-server` 的实现模式
- **关键发现:** 所有Cost Explorer的filter参数都定义为 `str` 类型
- **处理方式:** 使用 `parse_json()` 在内部将字符串解析为dict
- **推荐方案:** 遵循相同模式,将 `filter_expression` 改为 `str` 类型

### Step 6.1: 补充案例对比
- **案例:** `max_results` 参数的类型错误 (2026-01-19发现)
- **对比分析:**
  - `filter_expression`: Schema生成缺陷 (代码问题)
  - `max_results`: 调用参数格式错误 (调用问题)
- **启示:** 验证了基础类型Schema生成正常,复杂类型存在问题

## 💡 解决方案

### 推荐方案: 修改为 str 类型并内部解析

#### 1. 修改参数定义
```python
# 修改前
filter_expression: Annotated[
    Optional[dict],
    Field(description="Filter expression for Cost Explorer API. ...")
] = None

# 修改后
filter_expression: Annotated[
    Optional[str],
    Field(
        description="Filter expression for Cost Explorer API as a JSON string. "
        "Example: '{\"Dimensions\": {\"Key\": \"SERVICE\", \"Values\": [\"Amazon Elastic Compute Cloud - Compute\"]}}'"
    )
] = None
```

#### 2. 添加 JSON 解析逻辑
```python
# Parse filter_expression if provided
filter_dict = None
if filter_expression:
    try:
        filter_dict = json.loads(filter_expression)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format for filter_expression: {e}")

# 使用 filter_dict 构建请求
if filter_dict:
    request_params['Filter'] = filter_dict
```

#### 3. 更新文档和示例
在函数文档字符串中明确说明要传递JSON字符串,并提供正确的调用示例。

### 方案优势

✅ **与Bedrock AgentCore完全兼容** - 使用基础的`string`类型
✅ **与AWS官方MCP模式一致** - 遵循`billing-cost-management-mcp-server`的实现
✅ **避免Schema验证问题** - 不会触发type mismatch错误
✅ **向后兼容性强** - 字符串类型支持性最好
✅ **可扩展性好** - 可以处理各种复杂的Filter结构

## 📊 问题对比总结

| 问题 | filter_expression | max_results |
|------|------------------|-------------|
| **发生时间** | 2026-01-20 | 2026-01-19 |
| **Python类型** | `Optional[dict]` | `Optional[int]` |
| **Schema应生成** | `type: object` | `type: integer` |
| **Schema实际** | 缺少type定义 ❌ | 正确 ✅ |
| **传入值** | 字典字符串 | 字符串 "100" |
| **错误原因** | Schema生成缺陷 | 调用参数格式错误 |
| **问题层面** | 代码设计问题 | 参数传递问题 |
| **解决方案** | 改用str类型+内部解析 | 传递整数而非字符串 |

## 🎓 最佳实践总结

### 1. 参数类型选择原则
- **基础类型** (`int`, `str`, `bool`, `float`): 直接使用,Schema生成正确
- **复杂类型** (`dict`, `list`): 使用 `str` 接收JSON字符串,内部解析

### 2. Bedrock AgentCore 限制
- ❌ **不支持:** `oneOf`, `anyOf`, `allOf` 等高级Schema关键字
- ✅ **支持良好:** `string`, `integer`, `number`, `boolean` 等基础类型
- ⚠️ **支持有限:** `object`, `array` 等复杂类型 (Schema生成可能不完整)

### 3. 实施建议
1. 对于需要传递复杂JSON结构的参数,统一使用 `str` 类型定义
2. 在函数文档中明确说明要传递JSON字符串,并提供示例
3. 在函数内部使用 `json.loads()` 或统一的 `parse_json()` 工具函数解析
4. 添加适当的错误处理,捕获JSON解析异常

## 📝 实施步骤

1. ✅ 完成问题调研和根本原因分析
2. ⏳ 修改 `sp_handler.py` 中所有相关函数的参数定义
3. ⏳ 添加JSON解析逻辑和错误处理
4. ⏳ 更新函数文档字符串和使用示例
5. ⏳ 本地测试验证修改后的功能
6. ⏳ 部署到开发环境测试
7. ⏳ 部署到生产环境
8. ⏳ 验证生产环境功能正常

## 🔗 相关资源

- **参考代码:** `billing-cost-management-mcp-server/tools/sp_performance_tools.py`
- **工具函数:** `billing-cost-management-mcp-server/utilities/aws_service_base.py` - `parse_json()`
- **AWS Cost Explorer API文档:** Filter参数的完整定义
- **Bedrock AgentCore限制文档:** Schema支持和限制说明

## 📌 关键证据索引

### 代码文件
- `src/costq-risp-mcp-server/handlers/sp_handler.py` (第605行): 当前的dict定义
- `src/billing-cost-management-mcp-server/awslabs/billing_cost_management_mcp_server/tools/sp_performance_tools.py` (第66行): 正确的str定义
- `src/billing-cost-management-mcp-server/awslabs/billing_cost_management_mcp_server/utilities/aws_service_base.py` (第140行): parse_json函数

### 日志证据
- `/aws/bedrock-agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ-DEFAULT`: JsonSchemaException错误
- `/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/costq-aws-mcp-gateway-production-c3svyct5ay`: 参数传递和Schema验证失败
- AWS X-Ray Traces: 完整的调用链和错误堆栈

### 用户提供
- 错误信息截图 (filter_expression 问题)
- 错误信息截图 (max_results 问题, 2026-01-19)

---

**调研完成时间:** 2026-01-20
**调研人员:** DeepV Code AI Assistant
**结论:** 已找到根本原因并提供完整解决方案,准备实施修复。
