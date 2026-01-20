# Send Email MCP Server

邮件发送服务，使用 AWS SES（Simple Email Service）。

## 🎯 功能特性

- ✅ 发送 HTML/纯文本邮件
- ✅ 支持多个收件人
- ✅ 自动重试机制（最多3次）
- ✅ 详细的发送日志
- ✅ 完善的错误处理
- ✅ 单一职责，通用性强

## 🚀 快速开始

### 安装依赖

```bash
pip install boto3 loguru fastmcp
```

### 本地测试

```bash
# 方式1: 直接运行
python -m backend.mcp.send_email_mcp_server.server

# 方式2: 使用 uvx（推荐）
uvx --from . backend.mcp.send_email_mcp_server.server
```

### 使用示例

#### 通过 MCP 客户端调用

```python
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters

# 创建客户端
server_params = StdioServerParameters(
    command="python",
    args=["-m", "backend.mcp.send_email_mcp_server.server"]
)

async with stdio_client(server_params) as client:
    # 调用工具
    result = await client.call_tool(
        "send_email",
        {
            "to_emails": ["user@example.com"],
            "subject": "测试邮件",
            "body_html": "<h1>测试</h1><p>这是一封测试邮件</p>",
            "body_text": "测试\\n\\n这是一封测试邮件"
        }
    )

    print(result)
```

#### 在 Agent 中使用

```python
# Agent 会自动加载 Send Email MCP
# 直接在提示词中使用即可

response = await agent.run(
    "发送邮件给 finance@company.com，主题是'成本告警'，"
    "内容是'您的 AWS 成本已超过预算'"
)
```

## 📖 API 文档

### send_email

发送邮件到指定收件人。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `to_emails` | List[str] | ✅ | 收件人邮箱列表 |
| `subject` | str | ✅ | 邮件主题 |
| `body_html` | str | ❌ | HTML邮件正文 |
| `body_text` | str | ❌ | 纯文本邮件正文 |

**注意：** `body_html` 和 `body_text` 至少提供一个。

**返回值：**

成功时：
```json
{
  "success": true,
  "message_id": "010101234567890-abcdef...",
  "to_emails": ["user@example.com"]
}
```

失败时：
```json
{
  "success": false,
  "error": "错误信息描述",
  "to_emails": ["user@example.com"]
}
```

**示例：**

```python
# 1. 发送 HTML 邮件
result = await send_email(
    to_emails=["user@example.com"],
    subject="欢迎使用 CostQ",
    body_html="<h1>欢迎</h1><p>感谢您使用 CostQ。</p>"
)

# 2. 发送纯文本邮件
result = await send_email(
    to_emails=["user@example.com"],
    subject="密码重置",
    body_text="您的验证码是：123456"
)

# 3. 同时发送 HTML 和纯文本（推荐）
result = await send_email(
    to_emails=["user@example.com", "admin@example.com"],
    subject="AWS 成本告警",
    body_html="<h2>告警</h2><p>成本超标</p>",
    body_text="告警\\n\\n成本超标"
)
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SES_REGION` | `ap-northeast-1` | AWS SES 服务区域 |
| `SES_SENDER_EMAIL` | `no_reply@costq-mail.cloudminos.jp` | 发件人邮箱 |
| `SES_CONFIGURATION_SET` | `""` | SES 配置集（可选） |
| `LOG_LEVEL` | `WARNING` | 日志级别 |

### AWS 权限

需要以下 IAM 权限：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

**权限来源：**

- **本地开发：** 使用 `AWS_PROFILE` 环境变量指定的配置文件
- **生产环境：** 使用 EKS Pod 的 IAM Role（ServiceAccount）

## ⚠️ 注意事项

### 1. SES 沙盒模式

新 AWS 账号默认处于沙盒模式：
- ✅ 发件人邮箱需要验证
- ✅ 收件人邮箱也需要验证
- ✅ 每天最多发送 200 封邮件
- ✅ 每秒最多发送 1 封邮件

**移出沙盒：**
1. 登录 AWS Console
2. 进入 SES 服务
3. 请求提高发送限制

### 2. 邮箱验证

在沙盒模式下，需要验证邮箱：

```bash
# 验证发件人邮箱（一次性）
aws ses verify-email-identity \
  --email-address no_reply@costq-mail.cloudminos.jp \
  --region ap-northeast-1

# 验证收件人邮箱（测试时）
aws ses verify-email-identity \
  --email-address test@example.com \
  --region ap-northeast-1
```

### 3. 发送限制

AWS SES 有速率限制：
- 默认：1 封/秒，200 封/天
- 可申请提高限制

批量发送时注意控制速率。

### 4. 邮件格式

**推荐做法：**
- ✅ 同时提供 HTML 和纯文本版本
- ✅ HTML 使用内联 CSS
- ✅ 避免外部图片（可能被过滤）
- ✅ 主题简洁明确

**不推荐：**
- ❌ 只提供 HTML 版本
- ❌ 使用复杂的 CSS 布局
- ❌ 嵌入大量图片

## 🧪 测试

### 单元测试

```bash
pytest backend/mcp/send_email_mcp_server/tests/
```

### 集成测试

```bash
# 测试 MCP 服务器启动
python -m backend.mcp.send_email_mcp_server.server

# 测试实际发送（需要配置 AWS 凭证）
python -c "
from backend.mcp.send_email_mcp_server.handlers.email_handler import send_email
import asyncio

result = asyncio.run(send_email(
    to_emails=['test@example.com'],
    subject='测试',
    body_html='<h1>测试</h1>'
))
print(result)
"
```

## 🔗 相关服务

### Alert MCP Server

告警服务在触发告警后使用本服务发送邮件：

```python
# Alert Agent 示例
# 1. 检查告警条件
alert_triggered = await check_alert_condition(...)

# 2. 如果触发，发送邮件
if alert_triggered:
    email_result = await send_email(
        to_emails=alert.to_emails,
        subject="AWS 成本告警",
        body_html=alert_html_content,
        body_text=alert_text_content
    )
```

### 其他使用场景

- 用户邀请邮件
- 密码重置邮件
- 验证码邮件
- 系统通知邮件
- 报表邮件

## 📊 架构设计

### 设计理念

1. **单一职责**
   - 只负责邮件发送
   - 不包含业务逻辑（如告警管理）

2. **通用性强**
   - 任何场景都可使用
   - 参数简洁，无业务依赖

3. **无状态设计**
   - 不依赖数据库
   - 每次调用独立

4. **职责分离**
   - Alert MCP：管理告警配置
   - Send Email MCP：发送邮件
   - Agent：组合两者完成告警流程

### 与 Alert MCP 的关系

```
┌─────────────┐
│ Alert Agent │
└──────┬──────┘
       │
       ├─── 调用 Alert MCP ────► 管理告警配置
       │                        查询告警历史
       │
       └─── 调用 Send Email MCP ► 发送告警邮件
```

**职责划分：**
- Alert MCP：告警管理（CRUD、查询）
- Send Email MCP：邮件发送
- Agent：业务编排

## 🛠️ 开发指南

### 添加新功能

如需添加邮件模板功能（Phase 2）：

1. 在 `handlers/` 添加 `template_handler.py`
2. 在 `server.py` 注册新工具 `send_template_email`
3. 更新文档

### 代码规范

- ✅ 完整的类型注解
- ✅ Google 风格 Docstring
- ✅ 使用 Loguru 记录日志
- ✅ 完善的错误处理
- ✅ 单元测试覆盖

## 📝 常见问题

**Q: 为什么拆分出独立的 MCP？**

A: 遵循单一职责原则：
- Alert MCP 专注告警管理
- Send Email MCP 专注邮件发送
- 提高代码复用性和可维护性

**Q: 与 Alert MCP 的 send_alert_email 有什么区别？**

A:
- `send_alert_email`（旧）：包含告警相关逻辑（alert_id, org_id）
- `send_email`（新）：纯粹的邮件发送，无业务依赖

**Q: 如何处理发送失败？**

A:
1. 检查返回的 `success` 状态
2. 自动重试 3 次（内置）
3. 记录 `error` 信息
4. 根据业务需求实现补偿机制

**Q: 能否自定义发件人？**

A:
- 发件人由 `SES_SENDER_EMAIL` 环境变量控制
- 必须在 SES 中验证
- 不支持每次调用自定义

## 📚 参考资料

- [AWS SES 文档](https://docs.aws.amazon.com/ses/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [MCP 协议规范](https://modelcontextprotocol.io/)

---

**版本：** 1.0.0
**最后更新：** 2025年12月3日
**维护者：** CostQ Team
