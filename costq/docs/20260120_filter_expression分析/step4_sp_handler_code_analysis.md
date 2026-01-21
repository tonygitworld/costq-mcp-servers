# sp_handler.py 代码分析

## filter_expression 类型定义

### 1. Savings Plans 工具中的定义

在 `src/costq-risp-mcp-server/handlers/sp_handler.py` 中，所有工具函数都使用相同的类型定义：

#### get_savings_plans_utilization (第 61-67 行)
```python
filter_expression: Annotated[
    Optional[dict],  # ← dict 类型
    Field(
        description="Filter expression for Cost Explorer API. "
        "Supported dimensions: LINKED_ACCOUNT, SAVINGS_PLAN_ARN, SAVINGS_PLANS_TYPE, REGION, PAYMENT_OPTION, INSTANCE_TYPE_FAMILY"
    ),
] = None,
```

#### get_savings_plans_coverage (第 296-302 行)
```python
filter_expression: Annotated[
    Optional[dict],  # ← dict 类型
    Field(
        description="Filter expression for Cost Explorer API. "
        "Supported dimensions: LINKED_ACCOUNT, REGION, SERVICE, INSTANCE_FAMILY"
    ),
] = None,
```

#### get_savings_plans_purchase_recommendation (第 550-553 行)
```python
filter_expression: Annotated[
    Optional[dict],  # ← dict 类型
    Field(description="Filter expression for Cost Explorer API"),
] = None,
```

#### get_savings_plans_utilization_details (第 885-888 行)
```python
filter_expression: Annotated[
    Optional[dict],  # ← dict 类型
    Field(description="Filter expression for Cost Explorer API"),
] = None,
```

### 2. Reserved Instance 工具中的定义

在 `src/costq-risp-mcp-server/handlers/ri_handler.py` 中，也使用相同的类型定义：

```python
filter_expression: Annotated[
    Optional[dict],  # ← dict 类型
    Field(description="Filter expression for Cost Explorer API"),
] = None,
```

## 关键发现

### 1. 类型定义一致
**所有 RISP MCP Server 的工具函数都定义 `filter_expression` 为 `Optional[dict]` 类型**

这意味着：
- ✅ MCP Server 期望接收 `dict` 对象
- ✅ MCP Server 不接受 `string` 类型
- ✅ 代码定义是正确的，符合 AWS Cost Explorer API 的要求

### 2. 使用方式
当 `filter_expression` 不为 None 时，直接赋值给 AWS API 请求参数：

```python
if filter_expression:
    request_params["Filter"] = filter_expression
```

这说明 MCP Server 期望接收的是一个已经构造好的 dict 对象，例如：

```python
{
    "Dimensions": {
        "Key": "SERVICE",
        "Values": ["Amazon Elastic Compute Cloud - Compute"]
    }
}
```

### 3. MCP Schema 生成

FastMCP 会根据 Python 类型注解自动生成 MCP Tool Schema：

```python
Annotated[Optional[dict], Field(...)]
    ↓ FastMCP 自动转换
{
    "type": "object",  # ← dict 对应 object
    "description": "...",
    "nullable": true   # ← Optional 对应 nullable
}
```

## 问题根源确认

**代码层面没有问题！**

问题出在调用链的其他环节：

1. ✅ **RISP MCP Server 代码**: 正确定义为 `Optional[dict]`
2. ✅ **MCP Schema**: FastMCP 应该正确生成 `type: "object"`
3. ❌ **模型行为**: Claude Sonnet 将 dict 序列化成了 string
4. ❌ **Gateway验证**: 发现类型不匹配，拒绝请求

## 下一步分析

需要确认：
1. FastMCP 生成的 Schema 是否正确（是 object 还是别的）
2. Gateway 从哪里获取的 Schema
3. 为什么模型会将 dict 参数序列化成 string
