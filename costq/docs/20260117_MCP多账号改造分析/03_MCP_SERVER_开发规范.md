# MCP Server 开发规范与最佳实践

**版本**: v1.0
**更新日期**: 2026-01-20
**基于**: RISP MCP Server 改造经验总结

---

## 📋 目录

1. [背景说明](#背景说明)
2. [核心规范](#核心规范)
3. [工具函数签名规范](#工具函数签名规范)
4. [FastMCP 配置规范](#fastmcp-配置规范)
5. [Dockerfile 规范](#dockerfile-规范)
6. [包结构规范](#包结构规范)
7. [测试与验证](#测试与验证)
8. [常见问题与解决方案](#常见问题与解决方案)
9. [参考示例](#参考示例)

---

## 背景说明

### 问题起源

在将 RISP MCP Server 部署到 AWS AgentCore Gateway 时，遇到了以下关键问题：

1. **工具注册失败**: 请求在 7ms 内快速失败，返回 `InternalServerException`
2. **健康检查失败**: 容器始终处于 `unhealthy` 状态
3. **依赖版本冲突**: 镜像构建失败

### 根本原因

经过深入分析（参考 `cloudtrail-mcp-server` 成功案例），发现核心问题是：

**AgentCore Gateway 无法正确解析复杂嵌套的 Pydantic 模型作为工具参数**

- ❌ **错误模式**: 使用复杂 Pydantic 模型（如 `SavingsPlansCoverageParams`）作为函数参数
- ✅ **正确模式**: 使用简单类型（`str`, `int`, `bool`, `dict`, `list`）+ `Annotated[type, Field(description=...)]`

---

## 核心规范

### 🎯 黄金法则

> **AgentCore Gateway 兼容性原则**: 所有工具函数参数必须使用简单类型 + Annotated 描述，禁止使用复杂嵌套 Pydantic 模型。

### 📊 规范优先级

| 优先级 | 规范类别 | 影响 | 是否必须 |
|--------|---------|------|---------|
| **P0** | 工具函数签名 | 🔴 工具注册失败 | ✅ 必须 |
| **P1** | FastMCP 配置 | 🟠 服务器识别问题 | ✅ 必须 |
| **P1** | Dockerfile 健康检查 | 🟠 容器 unhealthy | ✅ 必须 |
| **P1** | 依赖版本锁定 | 🟠 构建失败 | ✅ 必须 |
| **P2** | 包结构规范 | 🟡 可维护性 | 🔶 推荐 |

---

## 工具函数签名规范

### ✅ 正确示例（推荐模式）

```python
from typing import Optional, Annotated, Any
from pydantic import Field
from mcp.server.fastmcp import Context

async def get_savings_plans_coverage(
    ctx: Context,
    start_date: Annotated[str, Field(description="Start date in YYYY-MM-DD format")],
    end_date: Annotated[str, Field(description="End date in YYYY-MM-DD format")],
    granularity: Annotated[Optional[str], Field(description="Time granularity: DAILY or MONTHLY")] = "MONTHLY",
    group_by: Annotated[Optional[list[str]], Field(description="Dimensions to group by")] = None,
    filter_expression: Annotated[Optional[dict], Field(description="Filter expression for Cost Explorer API")] = None,
    target_account_id: Annotated[Optional[str], Field(description="Target AWS account ID for multi-account access")] = None,
) -> dict[str, Any]:
    """
    Get Savings Plans coverage analysis.

    Args:
        ctx: MCP context
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        granularity: Time granularity (DAILY or MONTHLY)
        group_by: Dimensions to group by
        filter_expression: Filter expression
        target_account_id: Target AWS account ID

    Returns:
        Dict containing coverage analysis results
    """
    # 内部可以将参数转换为 Pydantic 模型（如果需要验证）
    params = SavingsPlansCoverageParams(
        time_period=TimePeriod(start_date=start_date, end_date=end_date),
        granularity=granularity,
        group_by=group_by,
        filter_expression=filter_expression,
    )

    # 业务逻辑...
    return result
```

### ❌ 错误示例（禁止模式）

```python
from pydantic import BaseModel
from mcp.server.fastmcp import Context

class TimePeriod(BaseModel):
    start_date: str
    end_date: str

class SavingsPlansCoverageParams(BaseModel):
    time_period: TimePeriod  # ❌ 嵌套对象
    granularity: Optional[str] = "MONTHLY"
    group_by: Optional[list[str]] = None

async def get_savings_plans_coverage(
    context: Context,
    params: SavingsPlansCoverageParams,  # ❌❌❌ 复杂模型参数
    target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """这种模式会导致 Gateway 无法解析 JSON Schema"""
    pass
```

### 📐 JSON Schema 对比

**❌ 错误模式生成的 JSON Schema**:
```json
{
  "properties": {
    "params": {
      "type": "object",  // ❌ 嵌套对象
      "properties": {
        "time_period": {
          "type": "object",  // ❌❌ 双重嵌套
          "properties": {
            "start_date": {"type": "string"},
            "end_date": {"type": "string"}
          }
        }
      }
    }
  }
}
```

**✅ 正确模式生成的 JSON Schema**:
```json
{
  "properties": {
    "start_date": {
      "type": "string",
      "description": "Start date in YYYY-MM-DD format"
    },
    "end_date": {
      "type": "string",
      "description": "End date in YYYY-MM-DD format"
    },
    "granularity": {
      "type": "string",
      "description": "Time granularity: DAILY or MONTHLY"
    }
  },
  "required": ["start_date", "end_date"]
}
```

### 🔧 参数类型规范

| Python 类型 | JSON Schema 类型 | 使用场景 | 示例 |
|-------------|-----------------|---------|------|
| `str` | `string` | 文本、日期、枚举 | `"2026-01-20"`, `"MONTHLY"` |
| `int` | `integer` | 数字、计数 | `100`, `30` |
| `float` | `number` | 小数 | `3.14`, `0.5` |
| `bool` | `boolean` | 布尔值 | `True`, `False` |
| `list[str]` | `array<string>` | 字符串列表 | `["EC2", "RDS"]` |
| `dict` | `object` | 复杂结构（**扁平**） | `{"key": "value"}` |
| `Optional[T]` | `T` or `null` | 可选参数 | `None`, `"value"` |

**⚠️ 重要限制**:
- ✅ **允许**: `dict` 类型（单层对象，如 `filter_expression: dict`）
- ❌ **禁止**: 嵌套 Pydantic 模型（如 `params: SavingsPlansParams`）
- ❌ **禁止**: 多层嵌套字典（如 `{"nested": {"deep": {"value": 1}}}`）

### 📝 参数命名规范

1. **使用蛇形命名法**: `start_date`, `target_account_id`
2. **避免缩写**: `target_account_id` 而非 `target_acc_id`
3. **清晰描述**: `group_by_subscription_id` 而非 `group_sub`
4. **一致性**: 同类参数使用相同前缀（如 `start_date`, `end_date`）

### 🎨 描述规范

每个参数的 `Field(description=...)` 必须：

1. **简洁清晰**: 一句话说明用途
2. **包含格式**: 如 `"Start date in YYYY-MM-DD format"`
3. **说明限制**: 如 `"Time granularity: DAILY or MONTHLY"`
4. **提供示例**: 如 `"Filter expression for Cost Explorer API"`

**示例**:
```python
start_date: Annotated[str, Field(description="Start date in YYYY-MM-DD format (e.g., 2026-01-01)")]
granularity: Annotated[Optional[str], Field(description="Time granularity: DAILY or MONTHLY. Default is MONTHLY")] = "MONTHLY"
```

---

## FastMCP 配置规范

### ✅ 标准配置

```python
from mcp.server.fastmcp import FastMCP

# 服务器名称必须遵循 awslabs 命名约定
mcp = FastMCP(
    name="awslabs.costq-risp-mcp-server",  # ✅ 标准格式: awslabs.<project>-<service>-mcp-server
    instructions="Tool instructions here...",
    dependencies=['boto3', 'pydantic', 'sqlalchemy'],
    host="0.0.0.0",
    stateless_http=True,
    port=8000  # AgentCore Runtime 默认端口
)
```

### 🎯 命名规范

**格式**: `awslabs.<project>-<service>-mcp-server`

**示例**:
- ✅ `awslabs.costq-risp-mcp-server` (CostQ 项目的 RISP 服务)
- ✅ `awslabs.cloudtrail-mcp-server` (官方 CloudTrail 服务)
- ❌ `AWS RISP MCP Server` (非标准格式)
- ❌ `risp-server` (缺少命名空间)

### 📋 配置参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | `str` | ✅ | 服务器唯一标识符，必须使用 `awslabs.*` 格式 |
| `instructions` | `str` | 🔶 | 服务器使用说明 |
| `dependencies` | `list[str]` | 🔶 | Python 依赖列表 |
| `host` | `str` | ✅ | 监听地址，AgentCore Runtime 使用 `0.0.0.0` |
| `port` | `int` | ✅ | 监听端口，AgentCore Runtime 使用 `8000` |
| `stateless_http` | `bool` | ✅ | 必须为 `True`（AgentCore 要求） |

---

## Dockerfile 规范

### ✅ 完整示例

```dockerfile
# ==================================================
# Stage 1: Builder - 构建虚拟环境和依赖
# ==================================================
FROM public.ecr.aws/docker/library/python:3.13-alpine AS builder

WORKDIR /app

# 安装编译依赖
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    postgresql-dev

# 创建虚拟环境
RUN python -m venv /app/.venv

# 安装 Python 依赖（版本锁定）
RUN /app/.venv/bin/pip install --no-cache-dir \
    boto3==1.38.22 \
    pydantic==2.11.7 \
    'mcp[cli]==1.23.3' \
    sqlalchemy==2.0.36 \
    psycopg2-binary==2.9.10 \
    cryptography==44.0.0 \
    aws-opentelemetry-distro==0.12.2

# ==================================================
# Stage 2: Runtime - 最小化运行时镜像
# ==================================================
FROM public.ecr.aws/docker/library/python:3.13-alpine

WORKDIR /app

# 安装运行时依赖
RUN apk add --no-cache \
    libpq \
    openssl \
    libffi

# 从 builder 复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制应用代码
COPY . /app/

# 设置环境变量
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    AWS_REGION=ap-northeast-1 \
    BEDROCK_REGION=ap-northeast-1

# 健康检查（进程存活检查，避免 POST-only 端点问题）
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD pgrep -f "python.*server" > /dev/null || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令（使用 OpenTelemetry 自动注入）
CMD ["opentelemetry-instrument", "python", "-m", "awslabs.costq_risp_mcp_server.server"]
```

### 🔧 关键配置说明

#### 1. 健康检查规范

**✅ 正确方式（进程存活检查）**:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD pgrep -f "python.*server" > /dev/null || exit 1
```

**❌ 错误方式（GET 请求到 POST-only 端点）**:
```dockerfile
# ❌ /mcp 端点仅支持 POST，GET 会失败
HEALTHCHECK CMD curl -f http://localhost:8000/mcp || exit 1
```

**原因**:
- MCP 协议要求 `/mcp` 端点**仅支持 POST** 请求
- 使用 GET 请求会导致容器始终 `unhealthy`
- 进程存活检查更可靠且符合最佳实践

#### 2. 依赖版本锁定规范

**✅ 推荐方式（精确版本）**:
```dockerfile
RUN pip install --no-cache-dir \
    boto3==1.38.22 \
    pydantic==2.11.7 \
    'mcp[cli]==1.23.3'
```

**❌ 不推荐方式（范围版本）**:
```dockerfile
RUN pip install --no-cache-dir \
    boto3>=1.38.0 \
    pydantic>=2.10.0 \
    'mcp[cli]>=1.23.0'
```

**重要版本依赖**:
| 包名 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| `mcp[cli]` | `>=1.23.0` | `==1.23.3` | 核心 MCP 框架 |
| `pydantic` | `>=2.11.0` | `==2.11.7` | mcp 1.23.3 要求 |
| `boto3` | `>=1.38.0` | `==1.38.22` | AWS SDK |

**⚠️ 版本兼容性问题**:
```
mcp[cli]==1.23.3 要求 pydantic>=2.11.0
如果使用 pydantic==2.10.6 会导致构建失败：
ERROR: Cannot install mcp and pydantic==2.10.6 because these package
versions have conflicting dependencies.
```

#### 3. 启动命令规范

**✅ 推荐方式（模块执行）**:
```dockerfile
CMD ["opentelemetry-instrument", "python", "-m", "awslabs.costq_risp_mcp_server.server"]
```

**说明**:
- 使用 `python -m` 执行模块而非直接运行 `server.py`
- 符合 Python 包最佳实践
- 便于后续结构重构

---

## 包结构规范

### ✅ 推荐结构（符合 awslabs 标准）

```
src/costq-risp-mcp-server/
├── pyproject.toml                    # Python 包配置
├── README.md                         # 项目说明
├── Dockerfile-AgentCore-Runtime      # AgentCore Runtime 专用 Dockerfile
├── awslabs/                          # awslabs 命名空间
│   ├── __init__.py
│   └── costq_risp_mcp_server/        # 主包目录
│       ├── __init__.py
│       ├── server.py                 # FastMCP 服务器入口
│       ├── handlers/                 # 工具处理器
│       │   ├── __init__.py
│       │   ├── sp_handler.py         # Savings Plans 工具
│       │   ├── ri_handler.py         # Reserved Instance 工具
│       │   └── commitment_handler.py # Commitment 工具
│       └── models/                   # 数据模型（内部使用）
│           ├── __init__.py
│           ├── sp_models.py
│           ├── ri_models.py
│           └── common_models.py
└── tests/                            # 测试目录
    ├── __init__.py
    └── test_server.py
```

### 📄 pyproject.toml 示例

```toml
[project]
name = "awslabs.costq-risp-mcp-server"
version = "1.0.0"
description = "AWS Reserved Instance & Savings Plans MCP Server for CostQ"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "boto3==1.38.22",
    "mcp[cli]==1.23.3",
    "pydantic==2.11.7",
    "sqlalchemy==2.0.36",
    "psycopg2-binary==2.9.10",
    "cryptography==44.0.0",
]
license = {text = "Apache-2.0"}

[project.scripts]
"awslabs.costq-risp-mcp-server" = "awslabs.costq_risp_mcp_server.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["awslabs"]
```

### 📦 命名空间说明

**awslabs 命名空间**:
- 所有 AWS Labs 项目使用统一的 `awslabs` 命名空间
- 避免与其他 Python 包冲突
- 便于组织和管理多个 MCP Server

**包名转换规则**:
- 项目名: `costq-risp-mcp-server` (kebab-case)
- 包名: `costq_risp_mcp_server` (snake_case)
- 导入: `from awslabs.costq_risp_mcp_server import server`

---

## 测试与验证

### 🧪 本地容器测试

#### 1. 构建镜像

```bash
cd src/costq-risp-mcp-server
docker build -f Dockerfile-AgentCore-Runtime -t costq-risp-mcp:test .
```

#### 2. 启动容器

```bash
docker run -d \
  --name costq-risp-mcp-test \
  -p 8000:8000 \
  -e AWS_PROFILE=your-profile \
  -e AWS_REGION=ap-northeast-1 \
  -v ~/.aws:/root/.aws:ro \
  costq-risp-mcp:test
```

#### 3. 验证容器健康状态

```bash
docker ps | grep costq-risp-mcp-test
# 期望输出：STATUS 显示 "Up X seconds (healthy)"
```

#### 4. 测试 MCP 工具列表

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

**期望响应**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "get_sp_utilization",
        "description": "...",
        "inputSchema": {
          "properties": {
            "start_date": {
              "type": "string",
              "description": "Start date in YYYY-MM-DD format"
            }
          }
        }
      }
    ]
  }
}
```

### ✅ 验证清单

- [ ] **容器启动成功**: `docker ps` 显示容器运行
- [ ] **健康检查通过**: STATUS 显示 `(healthy)`
- [ ] **工具数量正确**: `tools/list` 返回预期数量的工具
- [ ] **JSON Schema 格式正确**: 所有参数使用简单类型，无嵌套模型
- [ ] **参数描述完整**: 每个参数都有 `description` 字段
- [ ] **无错误日志**: `docker logs` 无 ERROR 或 WARNING

### 🔍 JSON Schema 验证脚本

```python
import json
import sys

def validate_tool_schema(tool):
    """验证工具的 JSON Schema 是否符合规范"""
    errors = []

    # 检查参数是否有嵌套对象
    for param_name, param_schema in tool['inputSchema']['properties'].items():
        if 'properties' in param_schema:
            errors.append(f"参数 '{param_name}' 包含嵌套对象（禁止）")

        if 'description' not in param_schema:
            errors.append(f"参数 '{param_name}' 缺少 description")

    return errors

# 使用示例
response = json.loads(tools_list_response)
for tool in response['result']['tools']:
    errors = validate_tool_schema(tool)
    if errors:
        print(f"❌ 工具 '{tool['name']}' 验证失败:")
        for error in errors:
            print(f"   - {error}")
    else:
        print(f"✅ 工具 '{tool['name']}' 验证通过")
```

---

## 常见问题与解决方案

### ❓ Q1: 工具注册失败，Gateway 返回 7ms InternalServerException

**症状**:
- Agent 调用工具时立即失败（响应时间 < 10ms）
- 日志中未见 `tools/call` 请求
- Gateway 返回 `InternalServerException`

**原因**:
- 工具函数使用了复杂 Pydantic 模型参数
- Gateway 无法解析嵌套 JSON Schema

**解决方案**:
1. 将所有工具函数参数改为简单类型
2. 使用 `Annotated[type, Field(description=...)]` 添加元数据
3. 在函数内部构造 Pydantic 模型（如果需要验证）

**参考代码**:
```python
# ❌ 错误
async def my_tool(ctx: Context, params: MyComplexParams):
    pass

# ✅ 正确
async def my_tool(
    ctx: Context,
    param1: Annotated[str, Field(description="...")],
    param2: Annotated[int, Field(description="...")] = 0,
):
    # 内部构造模型（可选）
    params = MyComplexParams(param1=param1, param2=param2)
    pass
```

---

### ❓ Q2: 容器健康检查失败，始终 unhealthy

**症状**:
- `docker ps` 显示容器状态为 `unhealthy`
- 容器重复重启

**原因**:
- 健康检查使用 `GET /mcp`，但 MCP 端点仅支持 POST

**解决方案**:
更改 Dockerfile 健康检查为进程存活检查：
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD pgrep -f "python.*server" > /dev/null || exit 1
```

---

### ❓ Q3: Docker 镜像构建失败，依赖冲突

**症状**:
```
ERROR: Cannot install mcp and pydantic==2.10.6 because these package
versions have conflicting dependencies.
```

**原因**:
- `mcp[cli]==1.23.3` 要求 `pydantic>=2.11.0`
- 使用了旧版本 `pydantic==2.10.6`

**解决方案**:
升级 pydantic 到 2.11.7 或更高版本：
```dockerfile
RUN pip install --no-cache-dir \
    pydantic==2.11.7 \
    'mcp[cli]==1.23.3'
```

---

### ❓ Q4: 如何处理复杂的 AWS API 参数？

**场景**: AWS Cost Explorer API 需要复杂的 Filter Expression

**❌ 错误方式**:
```python
class FilterExpression(BaseModel):
    dimensions: Optional[dict] = None
    tags: Optional[dict] = None

async def get_data(ctx: Context, filter: FilterExpression):  # ❌
    pass
```

**✅ 正确方式**:
```python
async def get_data(
    ctx: Context,
    filter_expression: Annotated[Optional[dict], Field(
        description="Filter expression for Cost Explorer API. Example: {'Dimensions': {'Key': 'SERVICE', 'Values': ['Amazon EC2']}}"
    )] = None,
):
    """
    使用扁平的 dict 类型，在 description 中说明结构
    """
    if filter_expression:
        # 内部验证（可选）
        pass
```

---

### ❓ Q5: 如何从旧代码迁移到新规范？

**迁移步骤**:

1. **识别所有工具函数**
   ```bash
   grep -r "@mcp.tool\|async def.*Context" src/
   ```

2. **提取 Pydantic 模型字段**
   ```python
   # 原模型
   class MyParams(BaseModel):
       field1: str
       field2: int
       nested: NestedModel  # 需要展开
   ```

3. **展开为函数参数**
   ```python
   async def my_tool(
       ctx: Context,
       field1: Annotated[str, Field(description="...")],
       field2: Annotated[int, Field(description="...")],
       # 展开 nested 模型的字段
       nested_field1: Annotated[str, Field(description="...")] = None,
       nested_field2: Annotated[int, Field(description="...")] = None,
   ):
       # 内部重建模型（如果需要）
       params = MyParams(
           field1=field1,
           field2=field2,
           nested=NestedModel(
               field1=nested_field1,
               field2=nested_field2
           )
       )
   ```

4. **更新函数调用**
   ```python
   # 如果函数内部逻辑使用 params.field1
   # 改为直接使用 field1
   ```

5. **测试验证**
   - 本地容器测试
   - 验证 JSON Schema
   - 部署到 AgentCore Gateway 验证

---

## 参考示例

### 📚 成功案例

1. **CloudTrail MCP Server** (`src/cloudtrail-mcp-server/`)
   - ✅ 工具函数使用简单类型
   - ✅ 健康检查使用进程存活检查
   - ✅ 标准 awslabs 包结构

2. **RISP MCP Server** (`src/costq-risp-mcp-server/`)
   - ✅ 13 个工具函数全部重构
   - ✅ 完整的 Dockerfile 配置
   - ✅ 本地测试全部通过

### 🔗 相关文档

- [MCP 协议规范](https://spec.modelcontextprotocol.io/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [AWS AgentCore Runtime 文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html)
- [Pydantic 文档](https://docs.pydantic.dev/)

### 📝 修复记录

详细的修复过程记录在：
- `costq/docs/20260119_risp_mcp问题/20260120_修复完成报告.md`
- `costq/docs/20260119_risp_mcp问题/20260120_本地测试报告.md`

---

## 总结

### 🎯 核心要点

1. **工具函数签名**: 使用简单类型 + `Annotated[type, Field(description=...)]`
2. **禁止嵌套模型**: 复杂 Pydantic 模型只能在函数内部使用
3. **健康检查**: 使用进程存活检查，避免 GET /mcp
4. **依赖锁定**: 精确版本号，特别是 `pydantic>=2.11.0`
5. **命名规范**: `awslabs.<project>-<service>-mcp-server`

### ✅ 遵循本规范的好处

- ✅ **AgentCore Gateway 兼容**: 工具注册 100% 成功
- ✅ **容器稳定性**: 健康检查可靠
- ✅ **构建可靠性**: 无依赖冲突
- ✅ **可维护性**: 标准化结构易于维护
- ✅ **可扩展性**: 便于添加新工具

### 🚀 快速开始

1. 复制 `src/cloudtrail-mcp-server/` 或 `src/costq-risp-mcp-server/` 作为模板
2. 修改 `name`, `description`, `dependencies`
3. 添加工具函数（遵循签名规范）
4. 本地测试验证
5. 部署到 AgentCore Gateway

---

**文档维护者**: DeepV Code AI Assistant
**最后更新**: 2026-01-20
**版本**: v1.0
**基于项目**: CostQ RISP MCP Server 改造
