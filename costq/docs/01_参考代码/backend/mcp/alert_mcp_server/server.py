"""Alert MCP Server implementation.

提供AWS成本告警管理和邮件通知功能
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import FastMCP

# Import handler functions
from .handlers.alert_handler import (
    create_alert,
    delete_alert,
    list_alerts,
    toggle_alert,
    update_alert,
)

# Configure Loguru logging

# Define server instructions
SERVER_INSTRUCTIONS = """
# Alert MCP Server - AWS成本告警管理服务器

## 🎯 核心功能

专注于AWS成本告警的配置管理，包括：
- ✅ 创建和管理告警配置
- ✅ 查询告警历史记录
- ✅ 多租户隔离和权限控制

⚠️  **邮件发送功能已迁移到 Send Email MCP Server**

## 🔧 核心工具

### 1. create_alert - 创建告警配置
创建新的成本告警配置，使用纯自然语言描述告警规则。

**使用场景：**
- "帮我创建一个告警，每天查询prod-01账号的SP覆盖率，如果低于70%，发邮件给finance@company.com"
- "设置一个告警监控EC2成本，超过1000美元就通知我"

**参数：**
- query_description: 完整的自然语言描述（必需）
- display_name: 告警显示名称（可选）
- user_id: 用户ID（必需）
- org_id: 组织ID（必需）
- check_frequency: 检查频率（hourly/daily/weekly/monthly，默认daily）

### 2. list_alerts - 查询告警列表
查询告警配置列表，支持过滤。

**使用场景：**
- "显示我的所有告警"
- "查看组织内所有启用的告警"

**参数：**
- org_id: 组织ID（必需）
- user_id: 用户ID（可选，如果提供则只返回该用户的告警）
- status_filter: 状态过滤（active/inactive/all，默认all）

### 3. update_alert - 更新告警配置
更新现有告警的配置。

**使用场景：**
- "修改告警的阈值"
- "更改告警的检查频率"

**参数：**
- alert_id: 告警ID（必需）
- query_description: 新的自然语言描述（可选）
- display_name: 新的显示名称（可选）
- check_frequency: 新的检查频率（可选）
- user_id: 用户ID（必需，权限验证）
- org_id: 组织ID（必需，权限验证）

### 4. toggle_alert - 启用/禁用告警
快速切换告警的启用状态。

**使用场景：**
- "暂时禁用这个告警"
- "重新启用告警"

**参数：**
- alert_id: 告警ID（必需）
- user_id: 用户ID（必需，权限验证）
- org_id: 组织ID（必需，权限验证）

### 5. delete_alert - 删除告警
删除不再需要的告警配置。

**使用场景：**
- "删除这个告警"
- "清理过期的告警"

**参数：**
- alert_id: 告警ID（必需）
- user_id: 用户ID（必需，权限验证）
- org_id: 组织ID（必需，权限验证）

## 📧 邮件发送

告警触发后，使用 **Send Email MCP Server** 发送邮件通知。

**使用方式：**
```python
# Agent 组合使用示例
# 1. 检查告警条件（使用 Alert MCP）
alert_triggered = await check_alert_condition(...)

# 2. 如果触发，发送邮件（使用 Send Email MCP）
if alert_triggered:
    email_result = await send_email(
        to_emails=["finance@company.com"],
        subject="AWS成本告警 - SP覆盖率低于70%",
        body_html="<h2>告警通知</h2><p>...</p>",
        body_text="告警通知\\n\\n..."
    )
```

**注意事项：**
- ✅ 使用 `send_email` 工具（来自 Send Email MCP）
- ❌ 不要使用 `send_alert_email`（已移除）
- 邮件主题要清晰明确
- 同时提供 HTML 和纯文本格式

## 📊 典型工作流程

### 场景1：创建并执行告警

1. **用户请求**："帮我监控prod-01账号的SP覆盖率，低于70%就发邮件"

2. **Agent执行**：
   ```
   Step 1: 调用 Alert MCP 的 create_alert
   - query_description: "每天查询prod-01账号的SP覆盖率，如果低于70%，发邮件给finance@company.com"
   - display_name: "prod-01 SP覆盖率监控"
   - check_frequency: "daily"

   Step 2: Agent定期执行（由调度系统触发）
   - 调用 Cost Explorer MCP 查询SP覆盖率
   - 判断是否低于70%
   - 如果触发，调用 Send Email MCP 的 send_email 发送邮件
   ```

### 场景2：管理现有告警

1. **查看告警**：`list_alerts(org_id="org-123")`
2. **修改告警**：`update_alert(alert_id="alert-456", check_frequency="hourly")`
3. **禁用告警**：`toggle_alert(alert_id="alert-456")`
4. **删除告警**：`delete_alert(alert_id="alert-456")`

## 🔒 安全和权限

- **多租户隔离**：所有操作都基于org_id进行隔离
- **用户权限**：用户只能操作自己创建的告警（admin可以操作组织内所有告警）
- **数据安全**：使用PostgreSQL外键约束确保数据一致性

## 🔗 相关 MCP

- **Send Email MCP**: 邮件发送服务（告警触发后调用）
- **Cost Explorer MCP**: 成本查询服务（告警条件判断）
- **RISP MCP**: RI/SP分析服务（RI/SP相关告警）

## 📈 最佳实践

1. **告警描述要清晰**：包含完整的查询逻辑、阈值判断和收件人信息
2. **合理设置频率**：根据成本变化速度选择合适的检查频率
3. **职责分离**：告警管理用Alert MCP，邮件发送用Send Email MCP
4. **定期清理**：删除不再需要的告警配置
"""

# Create FastMCP application
app = FastMCP(name="Alert MCP Server", instructions=SERVER_INSTRUCTIONS)

# Register tools
app.tool("create_alert")(create_alert)
app.tool("list_alerts")(list_alerts)
app.tool("update_alert")(update_alert)
app.tool("toggle_alert")(toggle_alert)
app.tool("delete_alert")(delete_alert)

if __name__ == "__main__":
    app.run()
