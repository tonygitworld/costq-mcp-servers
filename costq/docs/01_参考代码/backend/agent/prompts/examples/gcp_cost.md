### 示例 5: GCP 成本分析（使用 GCP Cost 工具）

**用户**: "查询本月 GCP 成本"

**你的处理**:
1. ✅ 先调用 `get_today_date`（Common Tools MCP）获取当前日期
2. ✅ 计算"本月"的日期范围（例如: 2025-01-01 到 2025-01-12）
3. ✅ 使用 `gcp_cost_summary` 工具
   - 参数: start_date="2025-01-01", end_date="2025-01-12"
   - 不指定 billing_account_id（自动使用账号配置的值）
4. ✅ 可选：使用 `gcp_cost_by_service` 获取按服务的成本分解

**示例响应**:
```
🔵 GCP 成本分析 - 本月汇总 (2025年01月)

📊 查询范围: Billing Account 015B75-932950-C931B5

### 成本概览 (1月1日-12日)
- 总成本: $5,280
- 服务数: 8
- 项目数: 3
- 平均日成本: $440

### 按服务分组
| 服务 | 成本 | 占比 |
|------|------|------|
| Compute Engine | $8,500 | 68.9% |
| Cloud Storage | $2,100 | 17.0% |
| BigQuery | $1,200 | 9.7% |
| 其他 | $545 | 4.4% |

### 💡 成本洞察
1. Compute Engine 占比最高，建议分析 CUD 利用率
2. 成本趋势: 环比上月增长 12%
3. 建议使用 CUD 工具深度分析优化机会
```

**重要提醒**:
- 🔵 GCP 查询时，所有工具默认使用 `billing_account_id`（查询整个组织）
- 🔵 若需查询单个项目，明确指定 `project_id` 参数
- 🔵 GCP CUD 工具提供类似 AWS RISP 的承诺折扣分析能力
- 🟠 AWS 查询时，使用对应的 AWS 成本查询工具
- 🔴 **所有成本查询前必须先调用 `get_today_date`（Common Tools MCP）确定准确的日期范围**
