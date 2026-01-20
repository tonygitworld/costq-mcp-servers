# MCP Core - 二次开发核心模块

这个目录包含基于 AWS Labs MCP 项目的二次开发核心代码。

## 📁 目录结构

```
mcp-core/
├── extensions/          # 扩展现有 MCP 服务器
├── integrations/        # 集成模块
├── custom_servers/      # 自定义 MCP 服务器
├── utils/              # 工具函数
└── README.md           # 本文件
```

## 🔧 开发指南

### 扩展现有服务器

在 `extensions/` 目录下创建扩展类：

```python
from mcp_upstream.src.cost_analysis_mcp_server import CostAnalysisServer

class EnhancedCostAnalysisServer(CostAnalysisServer):
    def __init__(self):
        super().__init__()
        self.add_custom_tools()
```

### 创建自定义服务器

在 `custom_servers/` 目录下创建新的 MCP 服务器：

```python
from mcp import Server

class CustomServer(Server):
    def __init__(self):
        super().__init__("custom-server")
```

### 集成第三方服务

在 `integrations/` 目录下创建集成模块：

```python
class SlackIntegration:
    def send_notification(self, message):
        # 实现 Slack 通知逻辑
        pass
```

## 🚀 使用方法

1. 在此目录下开发您的扩展代码
2. 通过配置文件启用您的自定义功能
3. 运行测试确保功能正常
4. 使用uvx或pip安装所需的AWS MCP服务器

## 📝 注意事项

- 所有自定义代码都应该在此目录下
- 遵循项目的代码规范和测试要求
- 使用远程MCP服务器确保获得最新功能
