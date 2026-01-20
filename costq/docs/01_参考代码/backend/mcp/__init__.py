"""
MCP (Model Context Protocol) 模块

这个包包含：
- MCP客户端管理：clients.py
- 本地 MCP服务器实现：
  - risp_mcp_server: Reserved Instance和Savings Plans分析服务器
  - gcp_cost_mcp_server: GCP 成本分析服务器
  - alert_mcp_server: 告警管理服务器
  - send_email_mcp_server: 邮件发送服务器

使用方法：
    # 启动RISP MCP服务器
    python -m backend.mcp.risp_mcp_server.server

    # 启动GCP Cost MCP服务器
    python -m backend.mcp.gcp_cost_mcp_server.server
"""

__version__ = "1.0.0"
__author__ = "AWS Cost Analysis Team"
__description__ = "MCP客户端和服务器实现"

# 导出主要组件
__all__ = [
    "clients",
    "risp_mcp_server",
    "gcp_cost_mcp_server",
    "alert_mcp_server",
    "send_email_mcp_server",
]
