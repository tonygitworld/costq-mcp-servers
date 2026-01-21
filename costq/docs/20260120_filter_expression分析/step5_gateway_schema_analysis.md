# Gateway Schema 分析 - 关键发现！

## 从 Gateway tools/list 响应中提取的 Schema

### 对比：有type字段 vs 无type字段

#### ✅ 正常参数（有type字段）

```
granularity={type=string}
```

#### ❌ 问题参数（**无type字段**）

```
filter_expression={description=Filter expression for Cost Explorer API}
```

## 关键发现

**`filter_expression` 参数在 Gateway 返回的 schema 中没有 type 字段！**

这意味着：
1. FastMCP 生成的 schema 可能缺失了 type 信息
2. Gateway 在传递 schema 时丢失了 type 信息
3. 或者 FastMCP 对于 `Optional[dict]` 类型没有正确生成 schema

## 问题根源推测

### Python 代码中的定义
```python
filter_expression: Annotated[
    Optional[dict],  # ← Python 类型
    Field(description="Filter expression for Cost Explorer API")
] = None
```

### FastMCP 应该生成的 Schema
```json
{
  "filter_expression": {
    "type": "object",  # ← 应该有这个！
    "description": "Filter expression for Cost Explorer API",
    "nullable": true
  }
}
```

### Gateway 实际收到的 Schema
```
filter_expression={description=Filter expression for Cost Explorer API}
```
**← type 字段丢失了！**

## 为什么会导致错误？

1. **模型行为**: Claude Sonnet 看到没有 type 字段的参数，可能选择将复杂对象序列化成 JSON 字符串
2. **Gateway 验证**: Gateway 在转发请求时，会根据 schema 验证参数类型
3. **类型推断**: 由于 schema 中没有 type 字段，Gateway 可能有默认的类型验证逻辑
4. **验证失败**: Gateway 期望 object 类型，但收到了 string

## 验证错误消息再次确认

```
Parameter validation failed: Invalid request parameters:
- Field 'filter_expression' has invalid type: $.filter_expression: string found, object expected
- Field 'filter_expression' has invalid type: $.filter_expression: string found, null expected
```

这说明 Gateway **知道** filter_expression 应该是 object 或 null，但它是从哪里知道的？

## 可能的原因

### 1. FastMCP Schema 生成问题

FastMCP 在将 Python 的 `Optional[dict]` 转换为 JSON Schema 时，可能存在 bug，导致：
- 只生成了 description
- 没有生成 type 字段

### 2. Gateway Schema 处理问题

Gateway 在接收或处理 MCP Server 返回的 schema 时，可能：
- 丢失了某些 type 信息
- 对某些类型的 schema 处理不当

### 3. MCP Protocol 限制

MCP 协议本身可能对复杂类型（如 dict/object）的 schema 定义有特殊要求

## 下一步分析

需要确认：
1. FastMCP 是如何将 `Optional[dict]` 转换为 JSON Schema 的
2. 是否有其他 MCP Server 成功使用了 dict 类型参数
3. Gateway 是如何验证参数类型的（明明 schema 里没有 type，它怎么知道要 object？）
