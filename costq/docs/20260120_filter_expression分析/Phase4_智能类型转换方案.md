# Phase 4: 智能类型转换方案

## 📋 背景

### 观察到的问题

**用户反馈:** 后端两次收到的 `filter_expression` 类型不一致
- **第一次:** 收到 `string` 类型
- **第二次:** 收到 `dict` 类型

### 根本原因分析

这个现象揭示了 **Gateway/MCP 协议的复杂序列化行为**:

1. **Gateway Schema 变化时的行为差异:**
   - Schema 说 `type=object` → Gateway 序列化 dict 为 JSON string
   - Schema 说 `type=string` → Gateway 可能直接转发 dict (不序列化)

2. **模型端的行为一致性:**
   - 模型始终传递 `dict` 对象
   - 模型可能不理解如何将 dict 转为 JSON string
   - 模型依赖中间层(Gateway)进行序列化

---

## 🎯 解决方案: 智能类型转换

### 核心思路

**既然上游行为不可控,那就让代码具有鲁棒性!**

在 Runtime 层添加智能类型检测和转换:
```python
def parse_filter_expression(filter_expression, function_name):
    """智能解析 filter_expression

    支持两种输入:
    1. JSON 字符串 (标准方式)
    2. dict 对象 (兼容上游未正确序列化的情况)
    """
    if not filter_expression:
        return None

    # 🔍 调试: 记录接收到的类型
    logger.info(
        "🔍 [%s] filter_expression type: %s",
        function_name,
        type(filter_expression).__name__
    )

    # ⚡ 智能处理: 如果是 dict,直接使用 (自动兼容)
    if isinstance(filter_expression, dict):
        logger.warning(
            "⚠️ [%s] Received dict instead of string! Auto-converting...",
            function_name
        )
        return filter_expression

    # ✅ 标准处理: JSON 字符串解析
    try:
        return json.loads(filter_expression)
    except json.JSONDecodeError as e:
        logger.error("❌ [%s] Invalid JSON: %s", function_name, e)
        raise ValueError(f"Invalid JSON format: {e}")
```

---

## ✅ 实施细节

### 1. 创建辅助函数

**位置:**
- `handlers/sp_handler.py` - L53-108
- `handlers/ri_handler.py` - L53-108

**功能:**
1. ✅ 类型检测和日志记录
2. ✅ 智能 dict 转换 (向后兼容)
3. ✅ 标准 JSON 字符串解析
4. ✅ 详细的错误处理和日志

### 2. 更新所有使用点

**sp_handler.py (4个函数):**
1. ✅ `get_savings_plans_utilization()` - L257
2. ✅ `get_savings_plans_coverage()` - L494
3. ✅ `get_savings_plans_purchase_recommendation()` - L718
4. ✅ `get_savings_plans_utilization_details()` - L1054

**ri_handler.py (2个函数):**
1. ✅ `get_reservation_utilization()` - L231
2. ✅ `get_reservation_coverage()` - L452

**修改模式:**
```python
# 旧代码 (15+ 行)
filter_dict = None
if filter_expression:
    try:
        filter_dict = json.loads(filter_expression)
    except json.JSONDecodeError as e:
        logger.error("...")
        raise ValueError("...")

if filter_dict:
    request_params["Filter"] = filter_dict

# 新代码 (2 行)
filter_dict = parse_filter_expression(filter_expression, "function_name")
if filter_dict:
    request_params["Filter"] = filter_dict
```

---

## 📊 优势分析

### 技术优势

1. **🛡️ 鲁棒性增强**
   - 同时支持 string 和 dict 输入
   - 自动适应上游序列化行为的变化
   - 向后兼容旧版 Gateway/模型

2. **🔍 可观测性提升**
   - 详细的类型日志 (每次调用都记录)
   - 警告日志标记异常情况
   - 便于追踪和调试类型问题

3. **📝 代码简化**
   - 减少重复代码 (90+ 行 → 6个函数调用)
   - 统一的错误处理
   - 更易维护

4. **🔧 灵活性**
   - 集中管理解析逻辑
   - 未来可以轻松添加其他类型支持
   - 不依赖上游的具体实现

---

## 🔬 调试能力

### 日志示例

**正常情况 (JSON string):**
```
🔍 [get_sp_coverage] filter_expression type: str, value: {"Dimensions": ...}
✅ [get_sp_coverage] Successfully parsed filter_expression
```

**兼容情况 (dict):**
```
🔍 [get_sp_utilization] filter_expression type: dict, value: {'Dimensions': ...}
⚠️ [get_sp_utilization] Received dict instead of string! Auto-converting...
```

**错误情况 (invalid JSON):**
```
🔍 [get_ri_coverage] filter_expression type: str, value: {invalid json...
❌ [get_ri_coverage] Invalid JSON format for filter_expression: Expecting property name...
```

通过这些日志,可以清楚地看到:
1. 每次调用接收到的**确切类型**
2. 是否触发了**兼容模式**
3. 是否发生了**解析错误**

---

## 🚀 部署流程

### 1. 代码修改
- ✅ 添加 `parse_filter_expression()` 辅助函数
- ✅ 更新 6个函数的调用点
- ✅ 语法检查通过

### 2. 镜像构建
- ✅ 构建新镜像: `v20260121-105128`
- ✅ 推送到 ECR
- 镜像大小: 258MB

### 3. Runtime 更新
- ⏳ 等待 Runtime 自动更新
- 或手动触发更新

### 4. 验证测试
- ⏳ 提交相同的测试请求
- ⏳ 检查日志输出
- ⏳ 验证功能正常

---

## 📋 预期效果

### 场景A: Gateway 传递 JSON string

```
模型 → dict
    ↓
Gateway (新Schema) → json.dumps(dict) → string
    ↓
Runtime 接收 → string
    ↓
parse_filter_expression → isinstance(str) → json.loads() → dict ✅
    ↓
AWS API 调用成功 ✅
```

### 场景B: Gateway 传递 dict

```
模型 → dict
    ↓
Gateway (新Schema) → dict (不序列化)
    ↓
Runtime 接收 → dict
    ↓
parse_filter_expression → isinstance(dict) → 直接返回 dict ✅
    ↓
AWS API 调用成功 ✅
```

### 场景C: 用户手动传递 JSON string

```
用户 → JSON string
    ↓
模型 → string
    ↓
Gateway → string
    ↓
Runtime 接收 → string
    ↓
parse_filter_expression → isinstance(str) → json.loads() → dict ✅
    ↓
AWS API 调用成功 ✅
```

**结论:** 无论上游如何变化,Runtime 都能正确处理! 🎉

---

## 🔧 未来改进

### 可选优化1: 规范化输出日志

如果日志过多,可以添加开关:
```python
def parse_filter_expression(
    filter_expression,
    function_name,
    verbose_logging=True  # 可通过环境变量控制
):
    if verbose_logging:
        logger.info(...)
```

### 可选优化2: 类型提示增强

```python
from typing import Union, Dict, Any

def parse_filter_expression(
    filter_expression: Optional[Union[str, Dict[str, Any]]],
    function_name: str
) -> Optional[Dict[str, Any]]:
    """支持 string 或 dict 输入"""
    ...
```

### 可选优化3: 性能优化

```python
def parse_filter_expression(filter_expression, function_name):
    if not filter_expression:
        return None

    # ⚡ 快速路径: dict 直接返回
    if isinstance(filter_expression, dict):
        logger.debug("Direct dict usage")  # 降级为 debug
        return filter_expression

    # 标准路径: JSON 解析
    return json.loads(filter_expression)
```

---

## ✅ 验证清单

### 部署后验证

- [ ] 日志中出现 `🔍 [function_name] filter_expression type: ...`
- [ ] 如果收到 dict,日志显示 `⚠️ Received dict instead of string!`
- [ ] 如果收到 string,日志显示 `✅ Successfully parsed filter_expression`
- [ ] AWS API 调用成功
- [ ] 返回数据正确

### 回归测试

- [ ] 使用 JSON string 参数测试
- [ ] 使用原始 dict 参数测试
- [ ] 使用无效 JSON 测试错误处理
- [ ] 使用 None 值测试
- [ ] 使用空字符串测试

---

## 📝 总结

### 关键创新

1. **问题诊断:**
   - 通过用户反馈发现类型不一致问题
   - 分析出 Gateway 序列化行为的变化

2. **解决方案:**
   - 不依赖上游修复
   - 在 Runtime 层实现智能兼容
   - 同时支持 string 和 dict

3. **额外价值:**
   - 详细的调试日志
   - 统一的错误处理
   - 代码简化和可维护性提升

### 经验总结

**核心教训:**
> 当跨服务通信涉及类型转换时,不要假设上游行为恒定。
> 在自己的服务边界做好防御性编程和兼容性处理。

**最佳实践:**
1. ✅ 详细的类型日志
2. ✅ 智能的类型转换
3. ✅ 清晰的错误消息
4. ✅ 代码复用和抽象

---

**文档完成时间:** 2026-01-21 10:51 AM
**作者:** DeepV Code AI Assistant
**状态:** 代码已修改,等待部署验证
