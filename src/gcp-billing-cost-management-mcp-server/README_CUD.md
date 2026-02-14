# GCP CUD (Committed Use Discounts) 工具使用指南

**版本**: 2.0.0
**更新日期**: 2025-10-28
**新特性**: 组织级别查询支持 (billing_account_id)

---

## 📋 概述

本文档介绍 GCP Cost MCP Server 中新增的 CUD (Committed Use Discounts) 分析工具。这些工具提供了类似 AWS RISP MCP Server 的承诺使用折扣分析能力。

---

## 🎯 功能特性

### ✅ 基础分析工具 (Core Analysis)

| 工具 | 功能 | AWS 等价物 |
|------|------|-----------|
| `gcp_list_commitments` | 承诺清单 | (隐含在 RI/SP 响应中) |
| `gcp_cud_utilization` | 利用率分析 | `get_reservation_utilization` |
| `gcp_cud_coverage` | 覆盖率分析 | `get_reservation_coverage` |
| `gcp_cud_savings_analysis` | 节省分析 | (包含在利用率响应) |

### ✅ 高级分析工具 (Advanced Analysis)

| 工具 | 功能 | 特性 |
|------|------|------|
| `gcp_cud_resource_usage` | 资源级别使用分析 | vCPU/Memory/GPU/SSD 详细指标 |
| `gcp_cud_status_check` | 自动化健康检查 | 多维度警报和建议 |
| `gcp_cud_vs_ondemand_comparison` | 成本对比分析 | 假设场景分析 |
| `gcp_flexible_cud_analysis` | Flexible CUD 分析 | 基于支出的 CUD 分析 |

### 🔄 关键差异

| 特性 | AWS RISP | GCP CUD |
|------|----------|---------|
| **数据源** | Cost Explorer API (单一) | Compute API + BigQuery (混合) |
| **数据延迟** | ~24 小时 | ~36-48 小时 |
| **查询复杂度** | 低（直接 API） | 中（SQL + API 组合） |
| **预计算指标** | ✅ 利用率自动计算 | ❌ 需要 SQL 计算 |
| **分页处理** | API 自动处理 | BigQuery 自动聚合 |

---

## 🚀 快速开始

### 前置条件

#### 1. 启用 BigQuery Billing Export
```bash
# 在 GCP Console 中:
# 1. 导航到: Billing → Billing Export → BigQuery export
# 2. 启用 "Detailed usage cost data"
# 3. 选择数据集 (例如: billing_export)
# 4. 等待 24 小时数据开始导出
```

#### 2. 必需的 IAM 权限
```bash
# 服务账号需要以下角色:
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/billing.viewer"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/compute.viewer"
```

#### 3. 启用必需的 API
```bash
gcloud services enable compute.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable cloudbilling.googleapis.com
```

---

## 📖 工具使用指南

### 1. `gcp_list_commitments` - 查看承诺清单

**功能**: 列出项目的所有 CUD 承诺，显示状态、资源配置和时间范围。

**参数**:
- `project_id` (必需): GCP 项目 ID
- `region` (可选): 特定区域过滤 (例如: 'us-central1')
- `status_filter` (可选): 状态过滤 (ACTIVE, EXPIRED, CANCELED, CREATING)

**使用示例**:

```python
# 示例 1: 列出所有活跃承诺
"List all active CUD commitments for project my-project"

# 示例 2: 查看特定区域
"Show me CUD commitments in us-central1"

# 示例 3: 查看即将过期的承诺
"List all CUD commitments and their expiration dates"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "commitments": [
      {
        "commitment_id": "12345678901234567890",
        "name": "commitment-prod-us-central1",
        "region": "us-central1",
        "status": "ACTIVE",
        "plan": "TWELVE_MONTH",
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2025-01-01T00:00:00Z",
        "resources": [
          {"type": "VCPU", "amount": "100"},
          {"type": "MEMORY", "amount": "400"}
        ]
      }
    ],
    "summary": {
      "total_count": 5,
      "active_count": 3,
      "expired_count": 2,
      "status_breakdown": {
        "ACTIVE": 3,
        "EXPIRED": 2
      }
    }
  }
}
```

---

### 2. `gcp_cud_utilization` - 分析利用率

**功能**: 计算 CUD 承诺的利用率，显示已用/未用比例和趋势。

**参数**:
- `project_id` (必需): GCP 项目 ID
- `start_date` (可选): 开始日期 YYYY-MM-DD (默认: 30天前)
- `end_date` (可选): 结束日期 YYYY-MM-DD (默认: 2天前)
- `granularity` (可选): DAILY 或 MONTHLY (默认: DAILY)
- `region` (可选): 区域过滤

**重要提示**:
- 自动排除最近 2 天数据（避免不完整数据）
- 数据可能延迟最多 1.5 天

**使用示例**:

```python
# 示例 1: 查看本月利用率
"What's our CUD utilization this month for project my-project?"

# 示例 2: 按日查看特定区域
"Show daily CUD utilization for us-central1 in October"

# 示例 3: 月度汇总
"Show monthly CUD utilization for the last 3 months"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "utilization_summary": {
      "utilization_percentage": 95.5,
      "total_commitment_cost": 50000.00,
      "total_cud_credits_applied": 47750.00,
      "total_unused_commitment": 2250.00,
      "currency": "USD",
      "data_freshness_note": "Data may lag by up to 1.5 days"
    },
    "utilizations_by_time": [
      {
        "period": "2024-10-01",
        "commitment_cost": 1666.67,
        "cud_credits_applied": 1625.00,
        "utilization_percentage": 97.5,
        "unused_commitment": 41.67
      }
    ]
  },
  "message": "CUD utilization: 95.5% across 30 periods"
}
```

**KPI 解读**:
- **utilization_percentage** < 80%: ⚠️ 低利用率，可能需要调整承诺
- **utilization_percentage** 80-95%: ✅ 良好
- **utilization_percentage** > 95%: 💡 考虑增加承诺

---

### 3. `gcp_cud_coverage` - 分析覆盖率

**功能**: 计算合格使用量中被 CUD 覆盖的比例，识别按需成本优化机会。

**参数**:
- `project_id` (必需): GCP 项目 ID
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期
- `granularity` (可选): DAILY 或 MONTHLY
- `service_filter` (可选): 服务名称 (默认: "Compute Engine")
- `region` (可选): 区域过滤

**自动排除**: 抢占式 VM (Preemptible VMs) - 不符合 CUD 条件

**使用示例**:

```python
# 示例 1: 查看 Compute Engine 覆盖率
"What's our CUD coverage for Compute Engine?"

# 示例 2: 识别优化机会
"How much on-demand usage could we optimize with CUDs?"

# 示例 3: 区域覆盖率
"Show CUD coverage breakdown by region"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "coverage_summary": {
      "coverage_percentage": 82.5,
      "cud_covered_cost": 165000.00,
      "on_demand_cost": 35000.00,
      "uncovered_percentage": 17.5,
      "total_eligible_cost": 200000.00,
      "currency": "USD",
      "service": "Compute Engine"
    },
    "coverages_by_time": [
      {
        "period": "2024-10-01",
        "total_eligible_cost": 6666.67,
        "cud_covered_cost": 5500.00,
        "on_demand_cost": 1166.67,
        "coverage_percentage": 82.5
      }
    ]
  },
  "message": "CUD coverage: 82.5% of eligible usage"
}
```

**优化建议**:
- **coverage_percentage** < 70%: 🔴 大量优化机会
- **coverage_percentage** 70-85%: 🟡 中等优化空间
- **coverage_percentage** > 85%: 🟢 良好覆盖

**行动步骤**:
```python
# 如果覆盖率 < 80%:
if coverage['data']['coverage_summary']['coverage_percentage'] < 80:
    on_demand_cost = coverage['data']['coverage_summary']['on_demand_cost']
    print(f"💡 优化机会: ${on_demand_cost} 的按需成本可通过 CUD 节省")

    # 获取购买建议
    recommendations = await gcp_commitment_recommendations(
        project_id="my-project",
        location="-"
    )
```

---

### 4. `gcp_cud_savings_analysis` - 计算节省效果

**功能**: 计算 CUD 带来的实际成本节省和投资回报率 (ROI)。

**参数**:
- `project_id` (必需): GCP 项目 ID
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期
- `granularity` (可选): DAILY 或 MONTHLY (默认: MONTHLY)

**使用示例**:

```python
# 示例 1: 查看本年度节省
"How much money have we saved with CUDs this year?"

# 示例 2: 计算 ROI
"What's the ROI on our CUD investments?"

# 示例 3: 月度趋势
"Show monthly CUD savings trend"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "savings_summary": {
      "net_savings": 12500.00,
      "savings_percentage": 15.6,
      "roi_percentage": 25.0,
      "total_commitment_cost": 50000.00,
      "total_cud_credits": 62500.00,
      "on_demand_equivalent_cost": 112500.00,
      "currency": "USD"
    },
    "savings_by_period": [
      {
        "period": "2024-10",
        "commitment_cost": 50000.00,
        "cud_credits_received": 62500.00,
        "net_savings": 12500.00,
        "savings_percentage": 20.0
      }
    ]
  },
  "message": "CUD savings: $12500.00 (15.6%)"
}
```

**指标计算**:
```
净节省 = CUD 信用 - 承诺成本
节省百分比 = 净节省 / 按需等价成本 × 100
ROI = 净节省 / 承诺成本 × 100
按需等价成本 = 承诺成本 + CUD 信用
```

---

## 🔄 典型工作流程

### 工作流 1: 月度 CUD 健康检查

```python
# Step 1: 查看所有活跃承诺
commitments = gcp_list_commitments(
    project_id="my-project",
    status_filter="ACTIVE"
)
print(f"活跃承诺: {commitments['data']['summary']['active_count']}")

# Step 2: 检查利用率
utilization = gcp_cud_utilization(
    project_id="my-project",
    granularity="MONTHLY"
)
util_pct = utilization['data']['utilization_summary']['utilization_percentage']
print(f"平均利用率: {util_pct}%")

if util_pct < 80:
    print("⚠️  警告: 利用率低，建议调查原因")

# Step 3: 检查覆盖率
coverage = gcp_cud_coverage(
    project_id="my-project"
)
cov_pct = coverage['data']['coverage_summary']['coverage_percentage']
on_demand = coverage['data']['coverage_summary']['on_demand_cost']
print(f"覆盖率: {cov_pct}%")
print(f"按需成本: ${on_demand}")

if cov_pct < 80:
    print(f"💡 优化机会: 可节省 ${on_demand * 0.3:.2f}/月")  # 假设 30% 节省

# Step 4: 计算节省效果
savings = gcp_cud_savings_analysis(
    project_id="my-project"
)
net_savings = savings['data']['savings_summary']['net_savings']
roi = savings['data']['savings_summary']['roi_percentage']
print(f"本月净节省: ${net_savings}")
print(f"ROI: {roi}%")
```

### 工作流 2: 优化决策

```python
# Step 1: 识别低覆盖率区域
coverage = gcp_cud_coverage(
    project_id="my-project",
    granularity="DAILY"
)

# 分析每日覆盖率趋势
for day_data in coverage['data']['coverages_by_time']:
    if day_data['coverage_percentage'] < 75:
        print(f"⚠️  {day_data['period']}: 覆盖率仅 {day_data['coverage_percentage']}%")
        print(f"    按需成本: ${day_data['on_demand_cost']}")

# Step 2: 获取购买建议
recommendations = gcp_commitment_recommendations(
    project_id="my-project",
    location="-"
)

if recommendations['data']['total_count'] > 0:
    print(f"\n💡 发现 {recommendations['data']['total_count']} 个 CUD 购买机会")
    print(f"潜在月节省: ${recommendations['data']['total_potential_savings']}")

    # 列出前 3 个建议
    for rec in recommendations['data']['recommendations'][:3]:
        print(f"\n推荐: {rec['description']}")
        if rec['cost_impact']:
            monthly = rec['cost_impact']['monthly_savings']
            annual = rec['cost_impact']['annual_savings']
            print(f"  月节省: ${monthly}, 年节省: ${annual}")

# Step 3: 模拟ROI
current_savings = gcp_cud_savings_analysis(project_id="my-project")
current_net = current_savings['data']['savings_summary']['net_savings']
potential = recommendations['data']['total_potential_savings']
projected_savings = current_net + potential

print(f"\n📊 ROI 预测:")
print(f"  当前月节省: ${current_net}")
print(f"  新建议节省: ${potential}")
print(f"  预计总节省: ${projected_savings}")
```

---

## ⚠️ 已知限制

### 1. 数据延迟
- **BigQuery 账单数据**: 延迟 1-6 小时
- **CUD 信用归属**: 延迟最多 1.5 天
- **解决方案**: 自动排除最近 2 天数据

### 2. 成本估算
- `list_commitments` 不直接返回承诺金额
- 需要从 BigQuery 关联查询获取准确成本
- 当前 `monthly_cost_estimate` 为占位符

### 3. 跨项目折扣共享
- 如启用 Discount Sharing，CUD 可跨项目使用
- 当前实现基于单项目查询
- **建议**: 查询 billing_account 级别数据

### 4. Flexible CUD vs Resource-based CUD
- ✅ 支持 Resource-based CUD (基于资源的承诺)
- ✅ 支持 Flexible CUD (基于支出的承诺)
- Flexible CUD 数据在单独的 `cud_subscriptions_export` 表
- 使用 `gcp_flexible_cud_analysis` 工具分析 Flexible CUD

---

## 📊 性能优化建议

### BigQuery 查询优化

1. **使用分区过滤** (已实现):
```sql
WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
```

2. **限制日期范围**:
- 默认 30 天足够大多数分析
- 长期趋势使用 MONTHLY 粒度

3. **缓存策略**:
- 历史数据 (> 3 天前): 缓存 7 天
- 近期数据 (< 3 天): 缓存 1 小时

### 成本控制

- BigQuery 前 1 TB/月 免费
- 典型 CUD 查询 < 10 MB
- 月度分析成本 < $0.05

---

## 🐛 故障排查

### 问题 1: "BigQuery billing export not configured"

**原因**: 未启用 BigQuery 账单导出

**解决方案**:
```bash
# 1. 在 GCP Console 启用
Billing → Billing Export → BigQuery export

# 2. 选择数据集
# 3. 等待 24 小时数据生成

# 4. 验证表存在
bq ls --project_id=PROJECT_ID billing_export
```

### 问题 2: "Insufficient permissions"

**原因**: 服务账号缺少必需权限

**解决方案**:
```bash
# 检查当前权限
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:SA_EMAIL"

# 添加缺失权限
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/bigquery.dataViewer"
```

### 问题 3: 利用率数据为 0

**可能原因**:
1. CUD 刚购买，数据未生成 (等待 24-48 小时)
2. CUD 未被使用 (检查资源配置)
3. 折扣共享未启用 (跨项目使用)

**调试步骤**:
```sql
-- 在 BigQuery 中手动查询
SELECT
  DATE(_PARTITIONDATE) AS date,
  SUM(CASE WHEN cost_type = 'commitment' THEN cost ELSE 0 END) AS commitment,
  SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c WHERE c.type = 'COMMITTED_USAGE_DISCOUNT')) AS credits
FROM `PROJECT.DATASET.TABLE`
WHERE _PARTITIONDATE >= '2024-10-01'
GROUP BY date
ORDER BY date DESC
LIMIT 10;
```

---

## 📚 更多资源

### 官方文档
- [GCP CUD 分析报告](https://cloud.google.com/billing/docs/how-to/cud-analysis-resource-based)
- [BigQuery 账单导出](https://cloud.google.com/billing/docs/how-to/export-data-bigquery)
- [Compute Engine 承诺](https://cloud.google.com/compute/docs/instances/signing-up-committed-use-discounts)

### 相关工具
- `gcp_cost_by_service` - 按服务查看成本
- `gcp_commitment_recommendations` - CUD 购买建议
- `gcp_vm_rightsizing_recommendations` - VM 规格优化

---

## 🔮 未来增强计划

### 计划新增功能

1. **智能推荐引擎**
   - 基于历史使用模式的 CUD 购买建议
   - 最佳承诺期限推荐 (1年 vs 3年)
   - ROI 预测和风险评估

2. **集成 Recommender API**
   - 利用 GCP Recommender 的官方建议
   - 自动化推荐审核流程
   - 推荐实施追踪

3. **多云对比分析**
   - GCP CUD vs AWS RI/SP 对比
   - 跨云成本优化建议
   - 统一的承诺管理视图

4. **自动化告警和通知**
   - Slack/Email 集成
   - 自定义告警阈值
   - 定期报告生成

---

**更新日志**:
- 2025-10-28 v2.0: 添加 billing_account_id 组织级别查询支持，完成所有高级分析工具
- 2025-10-28 v1.0: 初始版本，实现核心 CUD 分析功能

**维护者**: Strands Agent Team
**反馈**: 请提交 Issue 或 Pull Request
