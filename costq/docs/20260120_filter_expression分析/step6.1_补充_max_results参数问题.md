# Step 6.1: 补充 - max_results 参数类型问题

## 问题发现时间
2026-01-19 (昨天发现的历史问题,作为类型定义对比参考)

## 问题现象

### 错误信息
调用 `billing-cost-management-mcp-production___sp-performance` 工具时报错:

```
JsonSchemaException - Parameter validation failed: Invalid request parameters:
- Field 'max_results' has invalid type: $.max_results: string found, integer expected
- Field 'max_results' has invalid type: $.max_results: string found, null expected
```

### 调用参数
```json
{
  "end_date": "2026-01-19",
  "operation": "get_savings_plans_utilization_details",
  "start_date": "2026-01-01",
  "target_account_id": "859082029538",
  "max_results": "100"
}
```

**关键点:** `max_results` 的值是字符串 `"100"`,而不是整数 `100`

## 代码定义分析

### billing-cost-management-mcp-server 的定义

在 `sp_performance_tools.py` (第68行):
```python
max_results: Optional[int] = None,
```

**类型定义:** `Optional[int]` - 整数类型

### 预期的 Schema 生成

对于 `int` 类型,FastMCP 应该生成:
```json
{
  "max_results": {
    "type": "integer",
    "description": "Maximum number of results to return per page."
  }
}
```

## 问题对比分析

### 与 filter_expression 问题的对比

| 参数 | Python类型 | 传入值 | Schema期望 | 实际传入 | 错误 |
|------|-----------|--------|-----------|---------|------|
| `filter_expression` (costq-risp) | `Optional[dict]` | 字典对象 | `object` | `string` | ❌ string found, object expected |
| `max_results` (billing-cost) | `Optional[int]` | 整数 | `integer` | `string` "100" | ❌ string found, integer expected |

### 共同点

1. **Schema定义正确:** 两个工具的Schema定义都应该是正确的
   - `dict` → `type: object`
   - `int` → `type: integer`

2. **传入值类型错误:** 实际调用时传入的值类型与Schema不匹配
   - `filter_expression`: 传入了JSON字符串,而不是对象
   - `max_results`: 传入了字符串 "100",而不是整数 100

3. **AgentCore Schema验证失败:** Bedrock AgentCore 在验证阶段拒绝了请求

### 关键差异

| 问题 | filter_expression | max_results |
|------|------------------|-------------|
| **根本原因** | Schema生成缺少 `type: object` | 调用方传值错误(字符串而非整数) |
| **是否代码问题** | ✅ 是,定义为dict导致Schema生成有问题 | ❌ 否,代码定义正确 |
| **是否调用问题** | ❌ 否,按照预期传递了字典 | ✅ 是,应传整数却传了字符串 |
| **解决方案** | 修改代码:dict→str,内部解析 | 修正调用参数:"100"→100 |

## 结论

### filter_expression 问题
- **性质:** 代码设计问题
- **原因:** FastMCP对`dict`类型的Schema生成存在缺陷,缺少`type: object`
- **解决:** 改用`str`类型接收JSON字符串,内部解析(遵循billing-cost-management的模式)

### max_results 问题
- **性质:** 调用参数格式问题
- **原因:** 调用方错误地将整数转为字符串传递
- **解决:** 调用时直接传递整数值 `100`,而不是字符串 `"100"`

## 启示

这两个问题说明了不同层面的类型问题:

1. **Schema生成问题** (`filter_expression`):
   - FastMCP框架对复杂类型(如`dict`)的Schema生成可能不完整
   - 需要使用简单类型(`str`)并在内部转换来规避

2. **参数传递问题** (`max_results`):
   - 即使代码定义正确、Schema正确,调用方也可能传错类型
   - JSON中整数不应该加引号: `100` ✅,  `"100"` ❌

3. **最佳实践:**
   - 对于基础类型(`int`, `str`, `bool`): 直接使用,确保调用方传递正确类型
   - 对于复杂类型(`dict`, `list`): 使用`str`接收JSON字符串,内部解析

## 补充证据

- **错误截图:** 用户提供的错误信息显示 `max_results: "100"` (字符串形式)
- **代码定义:** `sp_performance_tools.py` 第68行明确定义为 `Optional[int]`
- **错误信息:** `string found, integer expected` - 清晰表明类型不匹配

## 对Step 6根本原因分析的补充

这个案例进一步证实了我们的分析:

1. **基础类型的Schema生成是正常的:** `int` → `type: integer` 生成正确
2. **复杂类型的Schema生成存在问题:** `dict` → 缺少 `type: object`
3. **推荐方案的合理性:** 使用`str`类型是最安全、最兼容的方式

因此,对于 `filter_expression` 的解决方案(改为`str`类型)是正确的选择。
