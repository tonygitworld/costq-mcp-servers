# Step 6: 根本原因分析和解决方案

## 分析时间
2026-01-20 根据网络搜索和billing-cost-management-mcp-server代码分析

## 关键发现

### 1. billing-cost-management-mcp-server 的正确做法

#### 参数定义方式
在 `sp_performance_tools.py` (第66行):
```python
filter: Optional[str] = None
```

在 `ri_performance_tools.py` (第82行):
```python
filter: Optional[str] = None
```

在 `cost_explorer_tools.py` (第150行):
```python
filter: Optional[str] = None
```

**关键点:** 所有Cost Explorer相关的filter参数都定义为 `str` 类型,而不是 `dict` 类型!

#### 运行时处理方式
在 `sp_performance_tools.py` (第185-186行):
```python
if filter_expr:
    request_params['Filter'] = parse_json(filter_expr, 'filter')
```

`parse_json` 函数定义 (在 `utilities/aws_service_base.py` 第140行):
```python
def parse_json(json_str: Optional[str], parameter_name: str) -> Any:
    """Parse a JSON string into a Python object.

    Args:
        json_str: JSON string to parse
        parameter_name: Name of the parameter (for error messages)

    Returns:
        Parsed JSON object

    Raises:
        ValueError: If the JSON string is invalid
    """
    if not json_str:
        return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        raise ValueError(f'Invalid JSON format for {parameter_name} parameter: {json_str}')
```

**处理流程:**
1. 工具调用时传递JSON字符串:`"filter": "{\"Dimensions\": {\"Key\": \"SERVICE\", \"Values\": [\"Amazon Elastic Compute Cloud - Compute\"]}}"`
2. 参数类型为`str`,Bedrock AgentCore Schema生成时自动添加 `"type": "string"`
3. Schema验证通过(string类型匹配)
4. 在函数内部使用`parse_json()`将字符串解析为dict对象
5. 将解析后的dict传递给AWS Cost Explorer API

#### 文档说明
在 `cost_explorer_tools.py` 的文档中明确说明了filter的使用方式(第79行):
```python
Example: {"operation": "getCostAndUsageWithResources", "start_date": "2025-08-07", "end_date": "2025-08-21", "granularity": "DAILY", "filter": "{\"Dimensions\": {\"Key\": \"SERVICE\", \"Values\": [\"Amazon Elastic Compute Cloud - Compute\"]}}", "group_by": "[{\"Type\": \"DIMENSION\", \"Key\": \"RESOURCE_ID\"}]"}
```

注意:`filter`的值是一个**转义的JSON字符串**。

### 2. costq-risp-mcp-server 的问题做法

#### 参数定义方式
在 `sp_handler.py` (第605行左右):
```python
filter_expression: Annotated[
    Optional[dict],
    Field(
        description="Filter expression for Cost Explorer API. ..."
    ),
] = None,
```

**问题点:** 定义为 `dict` 类型,期望直接接收字典对象。

#### Schema生成结果
根据Step 5的分析,生成的Schema中:
```json
"filter_expression": {
    "description": "Filter expression for Cost Explorer API."
}
```

**关键问题:** 缺少 `"type": "object"` 字段!

#### 导致的后果
1. Bedrock AgentCore在验证Schema时,由于缺少明确的type定义,将输入解释为`string`或`null`
2. 当工具调用传递字典对象(或字典的字符串表示)时,触发Schema验证错误
3. 错误信息:`Field 'filter_expression' has invalid type: $.filter_expression: string found, object expected`

### 3. 为什么 billing-cost-management-mcp-server 能正常工作?

1. **Schema正确生成:** `str`类型自动生成 `"type": "string"` 在Schema中
2. **输入格式匹配:** 调用时传递JSON字符串,符合Schema的string类型预期
3. **内部转换处理:** 通过`parse_json()`在函数内部将字符串转换为dict后再传给AWS API
4. **与Bedrock AgentCore兼容:** 字符串类型是Bedrock AgentCore完全支持的基础类型

### 4. Bedrock AgentCore的限制

根据网络搜索发现,Bedrock AgentCore对JSON Schema的支持有限制:
- **不支持:** `oneOf`, `anyOf`, `allOf` 等高级Schema关键字
- **基础类型支持良好:** `string`, `number`, `boolean`, `integer`
- **复杂对象支持存在问题:** 如本案例中的`dict`/`object`类型

AWS Cost Explorer的原生`Filter`参数在完整定义中使用了`oneOf`来表示复杂的过滤逻辑,但这无法在Bedrock AgentCore中直接表示。

## 解决方案

### 推荐方案: 遵循 billing-cost-management-mcp-server 的模式

#### 1. 修改参数类型定义
将 `filter_expression` 从 `dict` 改为 `str`:

```python
filter_expression: Annotated[
    Optional[str],
    Field(
        description="Filter expression for Cost Explorer API as a JSON string. "
        "Example: '{\"Dimensions\": {\"Key\": \"SERVICE\", \"Values\": [\"Amazon Elastic Compute Cloud - Compute\"]}}'"
    ),
] = None,
```

#### 2. 在函数内部添加JSON解析
在使用`filter_expression`之前添加解析逻辑:

```python
# Parse filter_expression if provided
filter_dict = None
if filter_expression:
    try:
        filter_dict = json.loads(filter_expression)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format for filter_expression: {e}")

# 然后在API调用中使用 filter_dict
if filter_dict:
    request_params['Filter'] = filter_dict
```

#### 3. 更新文档和示例
在函数文档字符串中明确说明filter_expression应该传递JSON字符串,并提供正确的示例。

### 方案优势

1. **与Bedrock AgentCore完全兼容:** 使用基础的`string`类型,Schema生成正确
2. **与现有AWS MCP模式一致:** 与`billing-cost-management-mcp-server`保持一致
3. **避免Schema验证问题:** 不会触发type mismatch错误
4. **向后兼容性强:** 字符串类型在各种MCP实现中都有良好支持

## 实施步骤

1. 修改 `sp_handler.py` 中所有相关函数的 `filter_expression` 参数定义
2. 添加 `parse_json` 工具函数或直接使用 `json.loads()`
3. 在每个使用 `filter_expression` 的地方添加JSON解析逻辑
4. 更新函数文档字符串和示例
5. 测试验证修改后的工具是否能正常工作
6. 提交代码并部署到生产环境

## 补充案例: max_results 参数问题对比

### 问题现象 (2026-01-19发现)
调用 `billing-cost-management-mcp-production___sp-performance` 时报错:
```
JsonSchemaException - Parameter validation failed: Invalid request parameters:
- Field 'max_results' has invalid type: $.max_results: string found, integer expected
```

调用参数中: `"max_results": "100"` (字符串形式)

### 代码定义
在 `sp_performance_tools.py` (第68行):
```python
max_results: Optional[int] = None,
```

### 问题对比分析

| 参数 | Python类型 | Schema应生成 | 实际传入 | 问题性质 |
|------|-----------|-------------|---------|---------|
| `filter_expression` (costq-risp) | `Optional[dict]` | `type: object` | string | ❌ **Schema生成缺陷** - 缺少type定义 |
| `max_results` (billing-cost) | `Optional[int]` | `type: integer` | string "100" | ❌ **调用参数错误** - 应传整数而非字符串 |

### 关键差异

1. **filter_expression 问题:**
   - **根本原因:** FastMCP对`dict`类型的Schema生成存在缺陷,缺少`type: object`
   - **问题层面:** 代码设计问题
   - **解决方案:** 修改代码定义,改用`str`类型并内部解析

2. **max_results 问题:**
   - **根本原因:** 调用方错误地将整数转为字符串传递
   - **问题层面:** 参数传递格式问题
   - **解决方案:** 调用时传递整数 `100`,而非字符串 `"100"`

### 启示

这两个案例说明了不同层面的类型问题:

1. **Schema生成层面** (`filter_expression`):
   - FastMCP对复杂类型(`dict`)的Schema生成不完整
   - 需要使用简单类型(`str`)规避,并在内部转换

2. **参数传递层面** (`max_results`):
   - 即使Schema正确,调用方也可能传错类型
   - JSON中整数不应加引号: `100` ✅, `"100"` ❌

3. **最佳实践验证:**
   - 基础类型(`int`, `bool`): 直接使用,确保调用方传正确类型
   - 复杂类型(`dict`, `list`): 使用`str`接收JSON字符串,内部解析 ✅

**结论:** `max_results`案例进一步证实了我们的分析 - 基础类型的Schema生成是正常的(`int`→`type: integer`),而复杂类型(`dict`)存在问题。因此,对`filter_expression`使用`str`类型的解决方案是正确的。

详细对比分析见: `step6.1_补充_max_results参数问题.md`

## 证据文件

- `billing-cost-management-mcp-server/tools/sp_performance_tools.py`: 第66行(filter定义), 第68行(max_results定义), 第185-186行(parse_json使用)
- `billing-cost-management-mcp-server/tools/ri_performance_tools.py`: 第82行(filter定义)
- `billing-cost-management-mcp-server/tools/cost_explorer_tools.py`: 第150行(filter定义), 第79行(使用示例)
- `billing-cost-management-mcp-server/utilities/aws_service_base.py`: 第140行(parse_json函数定义)
- `costq-risp-mcp-server/handlers/sp_handler.py`: 第605行左右(当前的dict类型定义)
- Gateway `tools/list` 响应: filter_expression缺少 `type: object` 定义
- 用户提供的max_results错误截图 (2026-01-19)

## 结论

**根本原因确认:**
`costq-risp-mcp-server` 使用 `dict` 类型定义 `filter_expression` 参数,导致FastMCP框架生成的OpenAPI Schema中缺少 `type: object` 定义。Bedrock AgentCore在Schema验证时将输入错误地解释为 `string` 或 `null` 类型,从而触发 `JsonSchemaException`。

**最佳实践:**
对于需要传递复杂JSON对象的参数(如AWS Cost Explorer的Filter),应该:
1. 在Python函数签名中定义为 `Optional[str]` 类型
2. 在文档中明确说明要传递JSON字符串
3. 在函数内部使用 `json.loads()` 或 `parse_json()` 将字符串解析为dict
4. 将解析后的dict传递给AWS API

这种模式既符合Bedrock AgentCore的限制,又能正确处理复杂的JSON结构。
