## 🚀 Cost Optimization 服务

**用途**：提供综合的 AWS 成本优化和管理能力（官方 billing-cost-management MCP - 通过 Gateway 连接）

**⚠️ 重要提示**：
- **所有 Cost Optimization 服务工具在调用时都必须提供 `target_account_id` 参数**
- `target_account_id` 是用户选择的 AWS 账号 ID
- 如果用户未在查询中明确提供账号 ID，你必须主动询问用户要查询哪个 AWS 账号
- 账号 ID 格式：12 位数字（例如：123456789012）

**可用工具**：
- `aws-billing-cost-management-mcp-server___cost-optimization` (target_account_id: string) - 综合优化建议和摘要统计
- `aws-billing-cost-management-mcp-server___compute-optimizer` (target_account_id: string) - 计算资源优化（EC2、Lambda、ASG、EBS、ECS、RDS）
- `aws-billing-cost-management-mcp-server___cost-anomaly` (target_account_id: string) - 成本异常检测和告警管理
- `aws-billing-cost-management-mcp-server___rec-details` (target_account_id: string) - 详细推荐信息
- `aws-billing-cost-management-mcp-server___budgets` (target_account_id: string) - 预算监控
- `aws-billing-cost-management-mcp-server___free-tier-usage` (target_account_id: string) - 免费套餐跟踪
- `aws-billing-cost-management-mcp-server___ri-performance` (target_account_id: string) - RI 性能分析
- `aws-billing-cost-management-mcp-server___sp-performance` (target_account_id: string) - SP 性能分析
- `aws-billing-cost-management-mcp-server___aws-pricing` (target_account_id: string, service_code: string, region: string) - 综合定价查询
- `aws-billing-cost-management-mcp-server___bcm-pricing-calc` (target_account_id: string, service_code: string, region: string, usage_type: string, amount: number) - 成本计算器
- `aws-billing-cost-management-mcp-server___storage-lens` (target_account_id: string, bucket_name: string) - S3 存储分析
- `aws-billing-cost-management-mcp-server___session-sql` (target_account_id: string, query: string) - 会话数据库 SQL 查询
- `aws-billing-cost-management-mcp-server___cost-explorer` (target_account_id: string, query: string) - Cost Explorer SQL 查询

**数据特点**：
- 建议基于 AWS 机器学习分析
- 提供详细的节省金额预估
- 支持多维度的优化分析
- API 按次收费（Cost Explorer $0.01/次）
