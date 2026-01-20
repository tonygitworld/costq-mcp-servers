"""Alert MCP Server 常量定义"""

# ============ 告警配置默认值 ============
DEFAULT_CHECK_FREQUENCY = "daily"  # 默认检查频率
MAX_ALERTS_PER_USER = 100  # 每个用户最多创建的告警数量
MAX_ALERTS_PER_ORG = 500  # 每个组织最多创建的告警数量

# ============ 检查频率选项 ============
CHECK_FREQUENCIES = {"hourly": "每小时", "daily": "每天", "weekly": "每周", "monthly": "每月"}

# ============ 错误消息 ============
ERROR_MESSAGES = {
    "ALERT_NOT_FOUND": "告警不存在或无权限访问",
    "ALERT_LIMIT_EXCEEDED": "已达到告警数量上限",
    "INVALID_FREQUENCY": "无效的检查频率",
    "PERMISSION_DENIED": "权限不足",
    "DATABASE_ERROR": "数据库操作失败",
    "INVALID_PARAMS": "参数验证失败",
}

# ============ 成功消息 ============
SUCCESS_MESSAGES = {
    "ALERT_CREATED": "告警创建成功",
    "ALERT_UPDATED": "告警更新成功",
    "ALERT_DELETED": "告警删除成功",
    "ALERT_TOGGLED": "告警状态切换成功",
}

# ============ 日志配置 ============
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
