## 🔵 GCP Cost Management 服务

**用途**：GCP 成本分析和预算管理

**适用场景**：
- 查询 GCP 实际成本数据（基于 BigQuery Billing Export）
- 按服务、项目、标签、SKU 分析成本
- 获取成本概览和统计信息
- 管理 GCP 预算和成本控制策略

**查询范围**：
- **项目级别**：使用 `project_id` 或 `project_ids` 参数
- **组织级别**：使用 `billing_account_id` 参数（推荐）
- **智能默认**：不指定参数时，自动使用账号配置的 `billing_account_id`

**服务能力**：
- **BigQuery Billing 分析**：按服务/项目/标签/SKU 分析成本，提供成本概览
- **Budget API 管理**：列出预算、获取预算状态、创建新预算

**数据特点**：
- 数据来源：BigQuery Billing Export（需配置）
- 支持多维度成本分析
- 实时查询账单数据
