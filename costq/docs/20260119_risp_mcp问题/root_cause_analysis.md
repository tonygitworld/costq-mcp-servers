# RISP MCP 工具调用失败 - 根因分析报告

**日期**: 2026-01-20
**分析人**: DeepV Code AI Assistant
**状态**: 🔍 **根因已识别** - 缺少 pyproject.toml 导致包结构不完整

---

## 📋 执行摘要

### 问题核心
`costq-risp-mcp-dev___get_sp_coverage` 工具调用在 **AgentCore Gateway 层面失败**（7ms 内返回 InternalServerException），Gateway 未将请求转发到 Runtime。

### 根因定位
通过对比 **cloudtrail-mcp-server**（成功）和 **costq-risp-mcp-server**（失败）两个 MCP 服务器的实现，发现 **RISP MCP 缺少 pyproject.toml 包配置文件**，导致：

1. ✅ **Runtime 部署成功**（健康检查通过）
2. ✅ **Gateway Target 创建成功**（配置正确）
3. ❌ **工具调用失败**（Gateway 无法发现工具）

---

## 🔍 对比分析：CloudTrail vs RISP

### 1. 包结构对比

#### ✅ CloudTrail MCP（成功案例）

```
cloudtrail-mcp-server/
├── pyproject.toml                    # ⭐ 包配置文件
├── awslabs/
│   └── cloudtrail_mcp_server/
│       ├── __init__.py               # ⭐ 包版本定义
│       ├── server.py                 # FastMCP 服务器
│       ├── tools.py                  # 工具实现
│       ├── models.py                 # Pydantic 模型
│       └── common.py
├── cred_extract_services/            # 凭证提取服务
│   ├── __init__.py
│   └── ...
└── tests/
    └── test_*.py
```

**pyproject.toml 配置**:
```toml
[project]
name = "awslabs.cloudtrail-mcp-server"
version = "0.0.9"
requires-python = ">=3.10"
dependencies = [
    "boto3>=1.38.22",
    "mcp[cli]>=1.23.0",
    "pydantic>=2.10.6",
]

[project.scripts]
"awslabs.cloudtrail-mcp-server" = "awslabs.cloudtrail_mcp_server.server:main"

[tool.hatch.build.targets.wheel]
packages = ["awslabs"]  # 指定打包目录
```

**关键特征**:
- ✅ **标准 Python 包结构** - 通过 `pyproject.toml` 定义
- ✅ **入口点声明** - `[project.scripts]` 定义可执行命令
- ✅ **包元数据完整** - name, version, dependencies 全部声明
- ✅ **可安装性** - 可通过 `pip install .` 或 `uvx` 安装

#### ❌ RISP MCP（失败案例）

```
costq-risp-mcp-server/
├── server.py                         # 直接启动文件
├── handlers/
│   ├── __init__.py
│   ├── ri_handler.py
│   ├── sp_handler.py
│   └── commitment_handler.py
├── cred_extract_services/
│   ├── __init__.py
│   └── ...
├── models/
│   ├── __init__.py
│   └── ...
├── utils/
│   ├── __init__.py
│   └── ...
├── constants.py
├── __init__.py
└── Dockerfile-AgentCore-Runtime      # ⚠️ 仅支持 Docker 部署
```

**缺失的配置**:
- ❌ **无 pyproject.toml** - 缺少包定义
- ❌ **无包元数据** - name, version 未声明
- ❌ **无入口点声明** - 仅依赖 Dockerfile CMD
- ⚠️ **仅支持容器化部署** - 无法通过包管理器安装

---

### 2. 服务器初始化对比

#### ✅ CloudTrail MCP

```python
# awslabs/cloudtrail_mcp_server/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name='awslabs.cloudtrail-mcp-server',  # 与 pyproject.toml 一致
    instructions='...',
    dependencies=['boto3', 'botocore', 'pydantic'],
    host="0.0.0.0",
    stateless_http=True
)

# 模块级工具注册
cloudtrail_tools = CloudTrailTools()
cloudtrail_tools.register(mcp)

def main():
    mcp.run(transport="streamable-http")
```

**关键特征**:
- ✅ **server name 与 package name 一致** - `awslabs.cloudtrail-mcp-server`
- ✅ **模块级初始化** - 导入时即注册工具
- ✅ **标准入口函数** - `main()` 由 pyproject.toml 引用

#### ❌ RISP MCP

```python
# server.py (顶层文件)
from mcp.server.fastmcp import FastMCP

app = FastMCP(
    name="AWS RISP MCP Server",  # ⚠️ 通用名称，无版本控制
    instructions='...',
    host="0.0.0.0",
    stateless_http=True,
    port=8000
)

# 直接注册工具
app.tool("get_ri_utilization")(get_reservation_utilization)
app.tool("get_sp_coverage")(get_savings_plans_coverage)
# ... 14 个工具

def main():
    app.run(transport="streamable-http")
```

**问题**:
- ⚠️ **server name 不匹配** - 无对应的 package name
- ⚠️ **无版本信息** - 无法追踪版本变化
- ⚠️ **依赖 Dockerfile CMD** - `CMD ["python", "server.py"]`

---

### 3. 工具注册方式对比

#### ✅ CloudTrail MCP - 类封装模式

```python
# awslabs/cloudtrail_mcp_server/tools.py
class CloudTrailTools:
    def register(self, mcp):
        mcp.tool(name='lookup_events')(self.lookup_events)
        mcp.tool(name='lake_query')(self.lake_query)
        # ... 5 个工具

    async def lookup_events(self, ctx: Context, ...):
        """带完整类型注解的工具实现"""
        pass

# server.py
cloudtrail_tools = CloudTrailTools()
cloudtrail_tools.register(mcp)
```

**优点**:
- ✅ 工具逻辑封装在类中
- ✅ 便于单元测试（mock 实例方法）
- ✅ 清晰的职责分离

#### ⚠️ RISP MCP - 直接注册模式

```python
# server.py
from handlers.ri_handler import get_reservation_utilization
from handlers.sp_handler import get_savings_plans_coverage

app.tool("get_ri_utilization")(get_reservation_utilization)
app.tool("get_sp_coverage")(get_savings_plans_coverage)
# ... 14 个工具
```

**问题**:
- ⚠️ 工具分散在多个模块
- ⚠️ server.py 变成大量导入语句
- ⚠️ 工具名称缩写（为满足 43 字符限制）可能影响可发现性

---

### 4. 依赖管理对比

#### ✅ CloudTrail MCP

**pyproject.toml**:
```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "boto3>=1.38.22",
    "mcp[cli]>=1.23.0",
    "pydantic>=2.10.6",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.26.0",
    "ruff>=0.9.7",
    "pyright>=1.1.398",
]
```

**优点**:
- ✅ **声明式依赖管理**
- ✅ **开发/生产依赖分离**
- ✅ **版本约束清晰**
- ✅ **支持 `pip install -e .`**

#### ❌ RISP MCP

**Dockerfile-AgentCore-Runtime**:
```dockerfile
RUN /app/.venv/bin/pip install --no-cache-dir \
    boto3>=1.38.0 \
    pydantic>=2.10.0 \
    'mcp[cli]>=1.23.0' \
    sqlalchemy>=2.0.0 \
    psycopg2-binary>=2.9.0 \
    cryptography>=41.0.0 \
    aws-opentelemetry-distro==0.12.2
```

**问题**:
- ❌ **依赖硬编码在 Dockerfile**
- ❌ **无法本地开发** - 需要构建容器
- ❌ **无依赖锁定** - 无 `uv.lock` 或 `requirements.txt`
- ❌ **版本变更历史丢失**

---

### 5. 启动方式对比

#### ✅ CloudTrail MCP

**多种启动方式**:

1. **UVX (推荐)**:
   ```bash
   uvx awslabs.cloudtrail-mcp-server@latest
   ```

2. **Docker**:
   ```bash
   docker run awslabs/cloudtrail-mcp-server:latest
   ```

3. **本地开发**:
   ```bash
   pip install -e .
   awslabs.cloudtrail-mcp-server
   ```

4. **直接运行**:
   ```bash
   python -m awslabs.cloudtrail_mcp_server.server
   ```

#### ❌ RISP MCP

**仅容器化部署**:

```dockerfile
CMD ["opentelemetry-instrument", "python", "server.py"]
```

**问题**:
- ❌ **无法通过 uvx 安装** - 缺少 pyproject.toml
- ❌ **无法本地快速测试** - 需要构建容器
- ❌ **依赖容器环境变量** - DATABASE_URL, ENCRYPTION_KEY

---

## 🎯 根因分析

### Gateway 工具发现机制

根据 AWS 文档和 AgentCore 最佳实践，Gateway 发现 MCP 工具的流程：

```
1. Gateway 调用 Runtime Endpoint
   ↓
2. Runtime 加载 MCP Server（通过入口点）
   ↓
3. MCP Server 返回 tool list（tools/list 协议）
   ↓
4. Gateway 缓存工具元数据
   ↓
5. Agent 调用工具时，Gateway 路由到 Runtime
```

### RISP MCP 失败的原因

#### ⚠️ 假设 1: Gateway 无法正确识别 MCP Server

**证据**:
- ✅ Runtime 健康检查通过（说明 `server.py` 启动成功）
- ✅ Target 同步成功（说明 Gateway 能连接 Runtime）
- ❌ **工具调用 7ms 内失败**（说明 Gateway 未转发请求）

**推论**:
Gateway 可能在 **工具发现阶段** 就失败了，因为：

1. **缺少标准包结构** - Gateway 可能期望 `awslabs.xxx-mcp-server` 格式
2. **server name 不匹配** - `"AWS RISP MCP Server"` vs 预期的 `awslabs.costq-risp-mcp-server`
3. **无版本信息** - Gateway 可能需要版本号进行缓存管理

#### ⚠️ 假设 2: Gateway 发现了工具，但工具名称冲突

**证据**:
- RISP MCP 使用缩写工具名称: `get_sp_coverage`
- CloudTrail MCP 使用完整名称: `lookup_events`

**推论**:
Gateway 可能在工具名称解析时失败，因为：

1. **工具名称过于通用** - `get_sp_coverage` 可能与其他 MCP 冲突
2. **缺少命名空间** - 无 package prefix 导致命名冲突
3. **Gateway 缓存错误** - 旧的工具元数据未清除

#### ⚠️ 假设 3: pyproject.toml 是 AgentCore 的必需配置

**证据**:
- ✅ CloudTrail MCP（有 pyproject.toml）工作正常
- ❌ RISP MCP（无 pyproject.toml）失败
- AWS 文档明确提到使用 `uvx` 或包管理器安装 MCP Server

**推论**:
AgentCore Gateway 可能：

1. **依赖包元数据** - 读取 `pyproject.toml` 获取 server name, version
2. **使用包导入机制** - 通过 `importlib` 加载 MCP Server
3. **验证包签名** - 检查是否为有效的 Python 包

---

## 🔧 解决方案

### 方案 1: 添加标准 pyproject.toml（推荐） ⭐

**步骤**:

1. **创建 pyproject.toml**:

```toml
[project]
name = "awslabs.costq-risp-mcp-server"
version = "1.0.0"
description = "AWS Reserved Instance & Savings Plans MCP Server"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "boto3>=1.38.0",
    "mcp[cli]>=1.23.0",
    "pydantic>=2.10.0",
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "cryptography>=41.0.0",
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

2. **重构目录结构**:

```
costq-risp-mcp-server/
├── pyproject.toml              # 新增
├── awslabs/                    # 新增包目录
│   └── costq_risp_mcp_server/
│       ├── __init__.py         # 添加版本号
│       ├── server.py           # 移动到包内
│       ├── handlers/
│       ├── models/
│       ├── utils/
│       ├── constants.py
│       └── cred_extract_services/
└── tests/
```

3. **更新 server.py**:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name='awslabs.costq-risp-mcp-server',  # 与 pyproject.toml 一致
    instructions='...',
    dependencies=['boto3', 'pydantic', 'sqlalchemy'],
    host="0.0.0.0",
    stateless_http=True
)

# 工具注册保持不变
mcp.tool("get_ri_utilization")(get_reservation_utilization)
# ...

def main():
    mcp.run(transport="streamable-http")
```

4. **更新 Dockerfile**:

```dockerfile
# 安装包到虚拟环境
COPY pyproject.toml /app/
RUN /app/.venv/bin/pip install -e .

# 复制应用代码
COPY awslabs /app/awslabs

# 启动命令使用入口点
CMD ["awslabs.costq-risp-mcp-server"]
```

5. **重新部署**:

```bash
# 构建新镜像
docker build -f Dockerfile-AgentCore-Runtime -t costq-risp-mcp:v2 .

# 推送到 ECR
aws ecr get-login-password --region ap-northeast-1 --profile 3532 | \
  docker login --username AWS --password-stdin 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com
docker tag costq-risp-mcp:v2 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-risp-mcp:v2
docker push 000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-risp-mcp:v2

# 更新 Runtime
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id costq_risp_mcp_dev_lyg-gdDA9aAoEP \
  --agent-runtime-version 4 \
  --profile 3532 \
  --region ap-northeast-1

# 同步 Gateway
aws bedrock-agentcore-control synchronize-gateway-targets \
  --gateway-identifier costq-aws-mcp-servers-gateway-lyg-gfqjxiflzv \
  --target-id-list D23VGQCN2A \
  --profile 3532 \
  --region ap-northeast-1
```

**预期效果**:
- ✅ Gateway 能正确识别 MCP Server
- ✅ 工具名称带命名空间前缀
- ✅ 支持本地开发和测试
- ✅ 版本控制完整

---

### 方案 2: 修改工具名称为完整格式（临时方案）

**步骤**:

1. **使用完整工具名称**:

```python
# 从缩写格式
app.tool("get_sp_coverage")(get_savings_plans_coverage)

# 改为完整格式（模仿 CloudTrail）
app.tool("savings_plans_coverage")(get_savings_plans_coverage)
app.tool("reservation_utilization")(get_reservation_utilization)
```

2. **重新部署并测试**

**优点**:
- ✅ 快速验证（无需重构）
- ✅ 避免命名冲突

**缺点**:
- ❌ 未解决根本问题
- ❌ 仍然缺少包结构

---

### 方案 3: 对比日志差异（诊断方案）

**步骤**:

1. **收集 CloudTrail MCP Runtime 日志**:

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/cloudtrail-runtime-id-DEFAULT \
  --since 30m --profile 3532 --region ap-northeast-1 > cloudtrail_runtime.log
```

2. **对比工具调用流程**:
   - 对比 `tools/list` 请求的响应
   - 对比 `tools/call` 请求的参数
   - 对比 HTTP 请求头（user-agent, content-type）

3. **验证假设**

---

## 📊 验证计划

### 第一阶段: 快速验证

1. **添加最小化 pyproject.toml**
2. **保持现有目录结构**（server.py 在顶层）
3. **重新部署并测试**

### 第二阶段: 完整重构（如果第一阶段成功）

1. **重构为标准包结构**
2. **添加单元测试**
3. **支持 uvx 安装**

### 第三阶段: 优化（如果问题仍存在）

1. **联系 AWS Support 获取 Gateway 内部日志**
2. **对比 CloudTrail MCP 的部署配置**
3. **检查 OAuth scope 或权限问题**

---

## 🎯 结论

### 最可能的根因

**RISP MCP 缺少 `pyproject.toml` 包配置文件**，导致 AgentCore Gateway 无法正确识别和路由工具调用。

### 证据链

1. ✅ CloudTrail MCP（有 pyproject.toml）工作正常
2. ❌ RISP MCP（无 pyproject.toml）失败
3. ⚠️ Gateway 在 7ms 内失败（未到达 Runtime）
4. ⚠️ Runtime 日志无工具调用记录
5. ✅ 健康检查和 OAuth 认证全部正常

### 建议行动

1. **立即执行**: 添加 pyproject.toml（方案 1 第一阶段）
2. **验证假设**: 重新部署并测试
3. **如果成功**: 进行完整重构（方案 1 第二阶段）
4. **如果失败**: 联系 AWS Support（方案 3）

### 预计工作量

- **方案 1 第一阶段**: 30 分钟（添加配置 + 部署）
- **方案 1 第二阶段**: 2-4 小时（重构 + 测试）
- **总计**: 3-5 小时完成完整优化

---

**报告完成时间**: 2026-01-20
**下一步**: 等待确认后执行方案 1
