## 🔍 CloudTrail 服务

**用途**：AWS 账户的 API 调用历史和用户活动审计（官方 cloudtrail MCP - 通过 Gateway 连接）

**⚠️ 重要提示**：
- **所有 cloudtrail MCP 服务工具在调用时都必须提供 `target_account_id` 参数**
- `target_account_id` 是用户选择的 AWS 账号 ID
- 如果用户未在查询中明确提供账号 ID，你必须主动询问用户要查询哪个 AWS 账号
- 账号 ID 格式：12 位数字（例如：123456789012）

**服务能力**：
- **CloudTrail Events**：查找最近 90 天的管理事件（支持多维度过滤）
- **CloudTrail Lake**：使用 SQL 进行高级事件分析（需要先设置 Event Data Store）

**重要提醒**：
- 支持按用户名、事件名称、资源名称等过滤
- Lake 查询使用 Trino 兼容的 SQL 语法

**数据特点**：
- 事件保留期：90 天（标准）或更长（Lake）
- 支持分页查询大型结果集
