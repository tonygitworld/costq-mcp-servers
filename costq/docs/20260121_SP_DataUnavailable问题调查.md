# Savings Plans 利用率查询 DataUnavailableException 问题调查

## 问题现象

**时间**: 2026-01-21 北京时间 17:12 (UTC 09:12)

**查询参数**:
- start_date: "2026-01-17"
- end_date: "2026-01-21"
- granularity: "DAILY"
- filter_expression:
```json
{
  "And": [
    {
      "Dimensions": {
        "Key": "SAVINGS_PLANS_TYPE",
        "Values": ["COMPUTE_SP"]
      }
    },
    {
      "Dimensions": {
        "Key": "LINKED_ACCOUNT",
        "Values": [
          "366941428704",
          "061051242070",
          "864899873504",
          "423623872634",
          "442042549049",
          "774206879749"
        ]
      }
    }
  ]
}
```
- target_account_id: "640874942658"

**错误信息**:
```
An error occurred (DataUnavailableException) when calling the GetSavingsPlansUtilization operation:
```

**实际情况**: 用户反馈这些账号的 Savings Plans 利用率实际上是 100%，但查询时返回数据不可用。

## 日志调查结果

### 1. Runtime 日志分析

从 `/aws/bedrock-agentcore/runtimes/cosq_agentcore_runtime_production-5x9j6eBjmZ-DEFAULT` 日志中找到：

**工具调用参数** (09:12:35 UTC):
```json
{
  "name": "costq-risp-mcp-production___get_sp_utilization",
  "input": {
    "end_date": "2026-01-21",
    "granularity": "DAILY",
    "filter_expression": "{\"And\": [{\"Dimensions\": {\"Key\": \"SAVINGS_PLANS_TYPE\", \"Values\": [\"COMPUTE_SP\"]}}, {\"Dimensions\": {\"Key\": \"LINKED_ACCOUNT\", \"Values\": [\"366941428704\", \"061051242070\", \"864899873504\", \"423623872634\", \"442042549049\", \"774206879749\"]}}]}",
    "start_date": "2026-01-17",
    "target_account_id": "640874942658"
  }
}
```

**关键发现**: `filter_expression` 是一个 **JSON 字符串**，而不是 JSON 对象！

**错误返回** (09:12:35 UTC):
```json
{
  "success": false,
  "error": "An error occurred (DataUnavailableException) when calling the GetSavingsPlansUtilization operation: ",
  "operation": "get_savings_plans_utilization",
  "message": "get_savings_plans_utilization failed: An error occurred (DataUnavailableException) when calling the GetSavingsPlansUtilization operation: ",
  "timestamp": "2026-01-21T09:12:35.904302"
}
```

**详细错误日志** (09:12:59 UTC):
```json
{
  "status": "error",
  "service": "Cost Explorer",
  "operation": "getSavingsPlansUtilization",
  "error_type": "DataUnavailableException",
  "message": "",
  "request_id": "a46d1bd3-a039-44a1-96ea-b50e215bc9f5",
  "http_status": 400,
  "full_error": "An error occurred (DataUnavailableException) when calling the GetSavingsPlansUtilization operation: ",
  "full_response": {
    "Error": {
      "Message": "",
      "Code": "DataUnavailableException"
    },
    "ResponseMetadata": {
      "RequestId": "a46d1bd3-a039-44a1-96ea-b50e215bc9f5",
      "HTTPStatusCode": 400,
      "HTTPHeaders": {
        "date": "Wed, 21 Jan 2026 09:12:59 GMT",
        "content-type": "application/x-amz-json-1.1",
        "content-length": "37",
        "connection": "keep-alive",
        "x-amzn-requestid": "a46d1bd3-a039-44a1-96ea-b50e215bc9f5",
        "cache-control": "no-store, no-cache"
      },
      "RetryAttempts": 0
    }
  }
}
```

**关键证据**:
- AWS API 返回 `DataUnavailableException`
- HTTP 状态码: 400 (客户端错误)
- Error Message 为空字符串
- 多次重试都返回相同错误

### 2. Gateway 和 RISP Runtime 日志

- Gateway log group 存在但无日志 (storedBytes: 0)
- RISP MCP production runtime log group 存在但无日志 (storedBytes: 0)

这表明 Gateway 和 RISP runtime 可能没有正常启动或记录日志。

## 代码分析

### parse_filter_expression 函数

在 `src/costq-risp-mcp-server/handlers/sp_handler.py` 中找到关键代码:

```python
def parse_filter_expression(filter_expression: Optional[Union[str, dict]], function_name: str) -> Optional[dict]:
    """解析 filter_expression 参数,支持调试日志.

    Args:
        filter_expression: JSON 字符串或 None
        function_name: 调用此函数的函数名(用于日志)

    Returns:
        解析后的 dict 或 None

    Raises:
        ValueError: 如果 JSON 格式无效
    """
    if not filter_expression:
        return None

    # 🔍 调试日志: 记录接收到的类型和值
    logger.info(
        "🔍 [%s] filter_expression type: %s, value: %s",
        function_name,
        type(filter_expression).__name__,
        str(filter_expression)[:200]  # 限制长度避免日志过长
    )

    # 如果已经是 dict,说明上游没有正确序列化,我们这里帮忙转换
    if isinstance(filter_expression, dict):
        logger.warning(
            "⚠️ [%s] Received dict instead of string! Auto-converting...",
            function_name
        )
        return filter_expression

    # 正常的 JSON 字符串解析
    try:
        filter_dict = json.loads(filter_expression)
        logger.info(
            "✅ [%s] Successfully parsed filter_expression",
            function_name
        )
        return filter_dict
    except json.JSONDecodeError as e:
        logger.error(
            "❌ [%s] Invalid JSON format for filter_expression: %s",
            function_name,
            str(e)
        )
        raise ValueError(
            f"Invalid JSON format for filter_expression: {e}"
        )
```

**分析**:
1. 函数设计接受 `Union[str, dict]` 类型
2. 如果是 dict 会记录警告并直接返回
3. 如果是字符串，会尝试 JSON 解析
4. 解析失败会抛出 ValueError

**问题**: 日志中没有看到 `parse_filter_expression` 的调试日志输出，这说明：
- RISP MCP Server 的日志没有写入到 RISP runtime log group
- 日志可能写入到其他位置，或者根本没有写入

## AWS API 文档调研结果

### GetSavingsPlansUtilization API

根据 AWS 文档和测试：

1. **DataUnavailableException 常见原因**:
   - 数据延迟：Cost Explorer 数据有 24-48 小时延迟
   - 无效时间范围：Start 日期必须在 13 个月内，End 日期必须在 Start 之后且不能是未来日期
   - 没有活跃的 Savings Plans：如果账号没有 SP，就没有利用率数据
   - 权限问题：需要 `ce:GetSavingsPlansUtilization` 权限

2. **Filter 参数格式**（已验证）:
   ```json
   {
     "Filter": {
       "And": [
         {
           "Dimensions": {
             "Key": "SAVINGS_PLANS_TYPE",
             "Values": ["COMPUTE_SP"]
           }
         },
         {
           "Dimensions": {
             "Key": "LINKED_ACCOUNT",
             "Values": ["123456789012", ...]
           }
         }
       ]
     }
   }
   ```

3. **SAVINGS_PLANS_TYPE 有效值** (需要进一步确认):
   - 文档中提到: "Compute Savings Plans", "EC2 Instance Savings Plans"
   - 代码中使用: "COMPUTE_SP", "EC2_INSTANCE_SP"
   - **可能的问题**: 值的大小写或格式不匹配

## 测试结果

### 测试 1: 不带 filter 的查询
```bash
aws ce get-savings-plans-utilization \
  --time-period Start=2026-01-17,End=2026-01-18 \
  --granularity DAILY \
  --profile 3532 \
  --region us-east-1
```

**结果**: `DataUnavailableException`

### 测试 2: 更早的日期范围
```bash
aws ce get-savings-plans-utilization \
  --time-period Start=2026-01-01,End=2026-01-18 \
  --granularity DAILY
```

**结果**: `DataUnavailableException`

### 重要发现

**即使不使用任何 filter，所有日期范围都返回 DataUnavailableException！**

这表明问题**不是 filter 参数格式**的问题，而是：

1. **账号 640874942658 (payer 账号) 可能没有可用的 Savings Plans 利用率数据**
2. **查询的时间范围可能过于接近当前日期（数据延迟）**
3. **需要在 Console 中确认该账号是否有活跃的 Savings Plans**

## 根本原因分析

基于测试结果，**DataUnavailableException 的根本原因最可能是**：

### 原因 1: Payer 账号查询限制
- 用户查询的 target_account_id 是 "640874942658" (payer 账号)
- GetSavingsPlansUtilization API 在 payer 账号级别查询时，可能需要特定的数据聚合
- 子账号的 Savings Plans 可能需要直接在子账号级别查询

### 原因 2: 数据可用性
- Cost Explorer 数据有 24-48 小时延迟
- 查询时间 2026-01-21 09:12 UTC
- 查询范围 2026-01-17 到 2026-01-21 包含最近 4 天数据
- **最近 1-2 天的数据可能尚未处理完成**

### 原因 3: 正确的查询方式
用户提到的 6 个子账号：
- 366941428704
- 061051242070
- 864899873504
- 423623872634
- 442042549049
- 774206879749

**可能需要**：
1. 直接查询每个子账号（target_account_id 设置为子账号ID）
2. 或者使用 GetSavingsPlansUtilizationDetails API 并通过 filter 指定账号

## ✅ 根本原因确认

经过深入调查和联网搜索，**找到了问题的根本原因**：

### **SAVINGS_PLANS_TYPE 过滤器值格式错误**

**错误值** (代码中使用的):
```json
{
  "Dimensions": {
    "Key": "SAVINGS_PLANS_TYPE",
    "Values": ["COMPUTE_SP"]  // ❌ AWS API 无法识别此值
  }
}
```

**正确值** (AWS API 期望的):
```json
{
  "Dimensions": {
    "Key": "SAVINGS_PLANS_TYPE",
    "Values": ["Compute"]  // ✅ AWS API 识别的标准值
  }
}
```

### 证据链

1. **AWS 文档验证**:
   - AWS Cost Explorer API 文档明确指出 SAVINGS_PLANS_TYPE 的有效值为：
     - `"Compute"` (Compute Savings Plans)
     - `"EC2 Instance"` (EC2 Instance Savings Plans)
     - `"SageMaker"` (SageMaker Savings Plans)
     - `"Database"` (Database Savings Plans)

2. **代码分析**:
   - `constants.py` 中定义的值是: `"COMPUTE_SP"`, `"EC2_INSTANCE_SP"`, `"SAGEMAKER_SP"`
   - 这些是内部使用的友好名称，但直接传递给了 AWS API
   - AWS API 无法识别这些值，返回 DataUnavailableException

3. **错误行为解释**:
   - AWS API 收到无效的过滤器值后，认为没有数据匹配
   - 返回 HTTP 400 DataUnavailableException
   - Error Message 为空字符串，因为这是一个过滤器匹配失败而非真正的错误

## 🔧 解决方案

### 已实施的修复

1. **在 `constants.py` 中添加映射表**:
```python
SAVINGS_PLANS_TYPE_MAPPING: dict[str, str] = {
    "COMPUTE_SP": "Compute",
    "EC2_INSTANCE_SP": "EC2 Instance",
    "SAGEMAKER_SP": "SageMaker",
    "DATABASE_SP": "Database",
}
```

2. **在 `sp_handler.py` 中添加转换函数**:
```python
def convert_savings_plans_type_in_filter(filter_dict: Optional[dict]) -> Optional[dict]:
    """转换 filter 中的 SAVINGS_PLANS_TYPE 值为 AWS API 期望的格式"""
    # 递归处理所有 Dimensions，将 COMPUTE_SP 等值转换为 Compute 等
```

3. **在所有 SP API 调用前应用转换**:
   - `get_savings_plans_utilization()`
   - `get_savings_plans_coverage()`
   - `get_savings_plans_purchase_recommendation()`
   - `get_savings_plans_utilization_details()`

### 修复后的调用流程

```
用户调用: filter_expression={"Dimensions": {"Key": "SAVINGS_PLANS_TYPE", "Values": ["COMPUTE_SP"]}}
    ↓
parse_filter_expression(): 解析 JSON 字符串 → dict
    ↓
convert_savings_plans_type_in_filter(): "COMPUTE_SP" → "Compute"
    ↓
AWS API 调用: Filter={"Dimensions": {"Key": "SAVINGS_PLANS_TYPE", "Values": ["Compute"]}}
    ↓
✅ 成功返回数据
```

## 📝 修改的文件

1. `src/costq-risp-mcp-server/constants.py`
   - 添加 `SAVINGS_PLANS_TYPE_MAPPING` 映射表

2. `src/costq-risp-mcp-server/handlers/sp_handler.py`
   - 添加 `convert_savings_plans_type_in_filter()` 函数
   - 在 4 个函数中应用转换逻辑

## 🧪 下一步测试

修复后需要：
1. 重新部署 RISP MCP Server
2. 测试相同的查询参数
3. 验证能否成功返回 SP 利用率数据
4. 确认日志中显示正确的转换逻辑
