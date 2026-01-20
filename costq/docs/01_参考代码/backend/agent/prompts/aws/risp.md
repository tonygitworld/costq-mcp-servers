## 🎯 RISP 服务（Reserved Instance & Savings Plans）

**用途**：分析和优化 AWS 预留实例和储蓄计划

**重要参数说明**：

### **account_scope 参数**（RI/SP 推荐工具）
- `"LINKED"`（默认）：获取账户级别的详细推荐
- `"PAYER"`：获取组织级别的汇总推荐

### **在调用 GetReservationUtilization 接口时，Granularity 参数不能与 GroupBy 同时使用。这两个参数是互斥的。**

### **Savings Plans 推荐流程**
1. 先调用推荐生成工具（无需参数）
2. 等待生成完成（异步）
3. 再调用获取推荐工具（可指定过滤条件）

**数据特点**：
- 推荐基于历史使用模式（默认 30 天）
- 支持多种 RI 类型和 SP 类型
- 提供详细的节省金额预估
