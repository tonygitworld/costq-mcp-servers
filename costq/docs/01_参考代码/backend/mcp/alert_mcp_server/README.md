# Alert MCP Server

## 概述

Alert MCP Server 是一个基于 FastMCP 的告警管理服务器，提供 AWS 成本告警配置管理和邮件通知功能。

## 核心特性

- ✅ **纯自然语言告警配置** - 使用完整的自然语言描述告警规则
- ✅ **多租户隔离** - 基于 org_id 和 user_id 的完整租户隔离
- ✅ **AWS SES 邮件发送** - 使用 AWS SES 发送告警邮件（ap-northeast-1 区域）
- ✅ **告警历史记录** - 完整记录每次告警执行结果
- ✅ **权限控制** - Admin 可管理组织内所有告警，普通用户只能管理自己的告警

## 架构设计

### 纯自然语言架构

告警配置只存储一个核心字段 `query_description`，包含完整的执行逻辑：

```
"每天查询 prod-01 账号的 SP 覆盖率，如果低于 70%，发邮件给 finance@company.com"
```

Agent 自主解析并执行：
1. 查询数据（调用 Cost Explorer MCP）
2. 判断阈值
3. 发送邮件（调用 Send Email MCP 的 send_email 工具）

## MCP 工具列表

### 1. create_alert - 创建告警配置

创建新的告警配置。

**参数：**
- `query_description` (str, 必需): 完整的自然语言描述
- `display_name` (str, 可选): 告警显示名称
- `user_id` (str, 必需): 用户 ID
- `org_id` (str, 必需): 组织 ID
- `check_frequency` (str, 可选): 检查频率（hourly/daily/weekly/monthly）

**返回：**
```json
{
  "success": true,
  "alert_id": "uuid",
  "message": "告警创建成功"
}
```

### 2. list_alerts - 查询告警列表

查询告警配置列表。

**参数：**
- `org_id` (str, 必需): 组织 ID
- `user_id` (str, 可选): 用户 ID（如果提供，只返回该用户的告警）
- `status_filter` (str, 可选): 状态过滤（active/inactive/all）

**返回：**
```json
{
  "success": true,
  "alerts": [...]
}
```

### 3. update_alert - 更新告警配置

更新现有告警配置。

**参数：**
- `alert_id` (str, 必需): 告警 ID
- `query_description` (str, 可选): 新的自然语言描述
- `display_name` (str, 可选): 新的显示名称
- `check_frequency` (str, 可选): 新的检查频率
- `user_id` (str, 必需): 用户 ID（权限验证）
- `org_id` (str, 必需): 组织 ID（权限验证）

**返回：**
```json
{
  "success": true,
  "message": "告警更新成功"
}
```

### 4. toggle_alert - 启用/禁用告警

切换告警的启用状态。

**参数：**
- `alert_id` (str, 必需): 告警 ID
- `user_id` (str, 必需): 用户 ID（权限验证）
- `org_id` (str, 必需): 组织 ID（权限验证）

**返回：**
```json
{
  "success": true,
  "is_active": true,
  "message": "告警已启用"
}
```

### 5. ~~send_alert_email~~ - ❌ 已移除

**此工具已迁移到 Send Email MCP Server。**

请使用 **Send Email MCP** 的 `send_email` 工具发送邮件。

**新工具：** `send_email`（来自 Send Email MCP）

**参数：**
- `to_emails` (List[str], 必需): 收件人邮箱列表
- `subject` (str, 必需): 邮件主题
- `body_html` (str, 可选): HTML 格式邮件正文
- `body_text` (str, 可选): 纯文本格式邮件正文

**返回：**
```json
{
  "success": true,
  "message_id": "ses-message-id",
  "to_emails": ["user@example.com"]
}
```

**详细文档：** 请参考 [Send Email MCP README](../send_email_mcp_server/README.md)

## AWS SES 配置

- **区域**: ap-northeast-1 (东京)
- **发件人**: no_reply@costq-mail.cloudminos.jp
- **要求**: 发件人邮箱必须在 SES 中验证

### 验证发件人邮箱

```bash
aws ses verify-email-identity \
    --email-address no_reply@costq-mail.cloudminos.jp \
    --region ap-northeast-1
```

## 数据库表结构

### monitoring_configs - 告警配置表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键 |
| org_id | VARCHAR(36) | 组织 ID（外键） |
| user_id | VARCHAR(36) | 用户 ID（外键） |
| query_description | TEXT | 完整的自然语言描述 |
| display_name | VARCHAR(200) | 显示名称 |
| is_active | BOOLEAN | 是否启用 |
| check_frequency | VARCHAR(20) | 检查频率 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| last_checked_at | TIMESTAMP | 最后检查时间 |

### alert_history - 告警历史表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键 |
| alert_id | VARCHAR(36) | 告警配置 ID（外键） |
| org_id | VARCHAR(36) | 组织 ID（外键） |
| triggered | BOOLEAN | 是否触发 |
| current_value | FLOAT | 当前值 |
| email_sent | BOOLEAN | 邮件是否发送成功 |
| email_error | TEXT | 邮件发送错误信息 |
| execution_result | JSONB | 完整执行结果 |
| error_message | TEXT | 执行错误信息 |
| created_at | TIMESTAMP | 执行时间 |

## 使用示例

### 示例 1: 创建 SP 覆盖率告警

```python
# Agent 调用
result = await create_alert(
    query_description="每天查询 prod-01 账号的 SP 覆盖率，如果低于 70%，发邮件给 finance@company.com",
    display_name="prod-01 SP 覆盖率监控",
    user_id="user-123",
    org_id="org-456",
    check_frequency="daily"
)
```

### 示例 2: 发送告警邮件

```python
# Agent 检测到告警触发后调用 Send Email MCP
result = await send_email(
    to_emails=["finance@company.com"],
    subject="AWS 告警：prod-01 SP 覆盖率过低",
    body_html="<h2>告警通知</h2><p>SP覆盖率过低</p>",
    body_text="告警通知\\n\\nSP覆盖率过低"
)
```

**注意：** 使用 `send_email` 工具（来自 Send Email MCP），不要使用 `send_alert_email`（已移除）。

## 开发和测试

### 运行数据库迁移

```bash
python backend/migrations/008_create_monitoring_tables_postgresql.py
```

### 测试邮件发送

```bash
python -m backend.mcp.alert_mcp_server.utils.ses_client
```

## 许可证

MIT License
