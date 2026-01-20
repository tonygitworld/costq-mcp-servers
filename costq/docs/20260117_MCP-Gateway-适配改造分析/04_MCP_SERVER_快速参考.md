# MCP Server 快速参考指南

> 基于 RISP MCP Server 改造经验总结的快速参考卡片

---

## 🎯 核心原则

### 黄金法则

```
❌ 禁止：复杂 Pydantic 模型作为工具参数
✅ 必须：简单类型 + Annotated[type, Field(description=...)]
```

---

## 📝 工具函数签名模板

### ✅ 标准模板

```python
from typing import Optional, Annotated, Any
from pydantic import Field
from mcp.server.fastmcp import Context

async def tool_name(
    ctx: Context,
    required_param: Annotated[str, Field(description="Required parameter description")],
    optional_param: Annotated[Optional[str], Field(description="Optional parameter description")] = None,
    list_param: Annotated[Optional[list[str]], Field(description="List parameter description")] = None,
    dict_param: Annotated[Optional[dict], Field(description="Dict parameter description")] = None,
    target_account_id: Annotated[Optional[str], Field(description="Target AWS account ID")] = None,
) -> dict[str, Any]:
    """
    Tool description here.

    Args:
        ctx: MCP context
        required_param: Required parameter
        optional_param: Optional parameter
        ...

    Returns:
        Dict containing results
    """
    # 业务逻辑
    return result
```

### ❌ 错误示例

```python
# ❌❌❌ 禁止使用复杂模型参数
class MyParams(BaseModel):
    field1: str
    nested: NestedModel  # ❌ 嵌套模型

async def tool_name(ctx: Context, params: MyParams):  # ❌❌❌
    pass
```

---

## 🔧 FastMCP 配置模板

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="awslabs.<project>-<service>-mcp-server",  # 必须：awslabs 命名空间
    instructions="Server instructions...",
    dependencies=['boto3', 'pydantic', 'sqlalchemy'],
    host="0.0.0.0",
    stateless_http=True,
    port=8000
)
```

**命名示例**:
- ✅ `awslabs.costq-risp-mcp-server`
- ✅ `awslabs.cloudtrail-mcp-server`
- ❌ `AWS RISP Server`

---

## 🐳 Dockerfile 关键配置

### 1. 依赖版本（必须锁定）

```dockerfile
RUN /app/.venv/bin/pip install --no-cache-dir \
    boto3==1.38.22 \
    pydantic==2.11.7 \      # ⚠️ 必须 >=2.11.0
    'mcp[cli]==1.23.3' \
    sqlalchemy==2.0.36 \
    psycopg2-binary==2.9.10 \
    cryptography==44.0.0 \
    aws-opentelemetry-distro==0.12.2
```

### 2. 健康检查（进程存活）

```dockerfile
# ✅ 正确：进程存活检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD pgrep -f "python.*server" > /dev/null || exit 1

# ❌ 错误：GET /mcp（POST-only 端点）
# HEALTHCHECK CMD curl -f http://localhost:8000/mcp || exit 1
```

### 3. 启动命令

```dockerfile
CMD ["opentelemetry-instrument", "python", "-m", "awslabs.costq_risp_mcp_server.server"]
```

---

## 📦 包结构模板

```
src/<your-mcp-server>/
├── pyproject.toml
├── Dockerfile-AgentCore-Runtime
├── awslabs/
│   └── <your_package>/
│       ├── __init__.py
│       ├── server.py
│       ├── handlers/
│       │   ├── __init__.py
│       │   └── tool_handler.py
│       └── models/
│           ├── __init__.py
│           └── data_models.py
└── tests/
```

---

## ✅ 快速验证清单

### 本地测试

```bash
# 1. 构建镜像
docker build -f Dockerfile-AgentCore-Runtime -t my-mcp:test .

# 2. 启动容器
docker run -d --name my-mcp-test -p 8000:8000 my-mcp:test

# 3. 检查健康状态
docker ps | grep my-mcp-test
# 期望：STATUS 显示 "(healthy)"

# 4. 测试工具列表
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# 5. 清理
docker stop my-mcp-test && docker rm my-mcp-test
```

### JSON Schema 验证

检查 `tools/list` 响应，确保：
- ✅ 所有参数类型是简单类型（`string`, `integer`, `boolean`, `array`, `object`）
- ✅ 每个参数都有 `description` 字段
- ❌ 没有嵌套的 `properties`（嵌套对象）

---

## 🚨 常见错误速查

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| 7ms InternalServerException | 复杂模型参数 | 展开为简单类型 |
| 容器 unhealthy | GET /mcp 健康检查 | 改用进程存活检查 |
| 构建失败（依赖冲突） | pydantic 版本太低 | 升级到 >=2.11.0 |
| 工具未注册 | FastMCP name 非标准 | 使用 `awslabs.*` 格式 |

---

## 📚 参数类型快速参考

| Python 类型 | JSON Schema | 使用场景 |
|-------------|------------|---------|
| `str` | `string` | 文本、日期、枚举 |
| `int` | `integer` | 数字 |
| `bool` | `boolean` | 布尔值 |
| `list[str]` | `array` | 字符串列表 |
| `dict` | `object` | 扁平结构 |
| `Optional[T]` | `T \| null` | 可选参数 |

---

## 🔗 完整文档

- **详细规范**: `costq/docs/MCP_SERVER_开发规范.md`
- **修复报告**: `costq/docs/20260119_risp_mcp问题/20260120_修复完成报告.md`
- **测试报告**: `costq/docs/20260119_risp_mcp问题/20260120_本地测试报告.md`

---

## 💡 快速开始

1. 复制 `src/cloudtrail-mcp-server/` 作为模板
2. 修改 `name`, `description`
3. 添加工具函数（使用简单类型）
4. 本地测试 → 部署

---

**版本**: v1.0
**更新**: 2026-01-20
**维护**: DeepV Code AI Assistant
