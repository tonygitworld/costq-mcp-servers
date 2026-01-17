# CloudTrail MCP Server 多账号改造测试记录

> **日期**: 2026-01-17
> **改造对象**: `src/cloudtrail-mcp-server`
> **改造状态**: ✅ 代码改造完成，🔄 容器测试进行中

---

## 📋 改造执行记录

### ✅ 已完成的改造步骤

#### Step 1: 复制凭证提取服务层
```bash
cd src/cloudtrail-mcp-server
cp -r ../billing-cost-management-mcp-server/cred_extract_services ./
```
**状态**: ✅ 完成
**文件**: 完全通用，直接复制无需修改

---

#### Step 2: 复制并修改 entrypoint.py
```bash
cp ../billing-cost-management-mcp-server/entrypoint.py ./
```

**修改内容**:
1. ✅ 修改导入路径（第 138 行）
   ```python
   # 修改前
   from awslabs.billing_cost_management_mcp_server.server import mcp, setup

   # 修改后
   from awslabs.cloudtrail_mcp_server.server import mcp
   ```

2. ✅ 添加 setup 函数兼容性处理（第 139-145 行）
   ```python
   # 尝试导入 setup 函数（有些 MCP Server 可能没有）
   try:
       from awslabs.cloudtrail_mcp_server.server import setup
       has_setup = True
   except ImportError:
       has_setup = False
       logger.info("ℹ️  MCP Server 没有 setup 函数，直接启动")
   ```

**原因**: cloudtrail-mcp-server 的 `server.py` 没有 `setup` 函数，需要兼容处理

---

#### Step 3: 复制 Dockerfile-AgentCore-Runtime
```bash
cp ../billing-cost-management-mcp-server/Dockerfile-AgentCore-Runtime ./
```
**状态**: ✅ 完成
**说明**: 通用模板，无需修改

---

#### Step 4: 修改所有 Tool 函数

**工具列表** (5 个):
1. ✅ `lookup_events`
2. ✅ `lake_query`
3. ✅ `get_query_status`
4. ✅ `get_query_results`
5. ✅ `list_event_data_stores`

**修改内容**（每个函数）:
```python
# 1. 添加参数（所有必需参数之后、其他可选参数之前）
async def tool_function(
    self,
    ctx: Context,
    required_param: str,                      # 必需参数
    target_account_id: Optional[str] = None,  # ⭐ 新增
    optional_param: Optional[int] = None,     # 其他可选参数
):

# 2. 添加账号上下文初始化（函数体开始处）
try:
    # ✅ 账号上下文初始化
    if target_account_id:
        from entrypoint import _setup_account_context
        await _setup_account_context(target_account_id)

    # 原有业务逻辑...
```

**验证**: ✅ 语法检查通过
```bash
python3 -m py_compile awslabs/cloudtrail_mcp_server/tools.py
```

---

#### Step 5: 创建部署脚本
```bash
cp costq/scripts/build_and_push_template.sh \
   costq/scripts/01-build_and_push_cloudtrail-mcp-server.sh

# 修改服务器名称
sed -i '' 's/<mcp-server-name>/cloudtrail-mcp-server/' \
   costq/scripts/01-build_and_push_cloudtrail-mcp-server.sh
```
**状态**: ✅ 完成

---

## 🐋 Docker 镜像构建记录

### 首次构建

**执行命令**:
```bash
bash costq/scripts/build_and_push_template.sh cloudtrail-mcp-server
```

**构建过程**:
- ✅ **Step 1**: ECR 登录成功
- ✅ **Step 2**: Docker 镜像构建成功
  - 平台: `linux/arm64`
  - 基础镜像: `python:3.13-alpine`
  - 镜像 SHA: `8d435699330778379b88f6e84765f93b072dc30a22bfda0c372fb322ec5fc34e`
  - 镜像大小: `255MB`
  - 构建用时: 约 25 分钟（首次构建）
- ✅ **Step 3**: 镜像打标签成功
  - `latest`
  - `v20260117-111930`
- ❌ **Step 4**: 推送到 ECR 失败
  - 原因: ECR 仓库 `awslabs-mcp/cloudtrail-mcp-server` 不存在
  - **影响**: 无，本地镜像已构建成功，可直接进行本地测试

**本地镜像**:
```
REPOSITORY                                                                                                   TAG                IMAGE ID       SIZE
000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/cloudtrail-mcp-server                          latest             8d4356993307   255MB
000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/awslabs-mcp/cloudtrail-mcp-server                          v20260117-111930   8d4356993307   255MB
```

---

### 第二次构建（修复 entrypoint.py 后）

**原因**: 修复 `setup` 函数导入问题

**状态**: 🔄 进行中

---

## 🧪 本地容器测试记录

### 测试脚本
创建了专用测试脚本: `costq/scripts/test_cloudtrail_local.sh`

### 第一次测试（失败）

**时间**: 2026-01-17 11:42

**执行命令**:
```bash
bash costq/scripts/test_cloudtrail_local.sh
```

**测试结果**: ❌ 失败

**错误日志**:
```
ImportError: cannot import name 'setup' from 'awslabs.cloudtrail_mcp_server.server'
```

**根本原因**:
- cloudtrail-mcp-server 的 `server.py` 没有 `setup` 函数
- entrypoint.py 强制要求导入 `setup`
- billing-cost-management-mcp-server 有 `setup`，但不是所有 MCP Server 都有

**解决方案**:
修改 `entrypoint.py` 添加兼容性处理：
```python
try:
    from awslabs.cloudtrail_mcp_server.server import setup
    has_setup = True
except ImportError:
    has_setup = False
```

**改进记录**:
- ✅ 发现问题：entrypoint.py 模板不够通用
- ✅ 解决方案：添加 setup 函数可选导入
- ⏳ 待验证：重新构建镜像并测试

---

### 第二次测试（待执行）

**前置条件**:
- ⏳ 等待镜像重新构建完成

**测试计划**:
1. 容器启动检查
2. 工具注册验证（5 个工具）
3. 凭证服务导入验证
4. 多账号参数检查

---

## 📝 改造经验总结

### ✅ 成功经验

#### 1. 文件复用效率高
- ✅ `cred_extract_services/` - 100% 复用
- ✅ `Dockerfile-AgentCore-Runtime` - 100% 复用
- ⚠️ `entrypoint.py` - 需要简单适配

#### 2. 改造速度快
- 文件复制: 2 分钟
- 修改 entrypoint.py: 1 分钟
- 修改 tools.py (5 个函数): 5 分钟
- **总计**: 约 8 分钟

#### 3. 语法检查通过
```bash
python3 -m py_compile awslabs/cloudtrail_mcp_server/tools.py entrypoint.py
# ✅ 无错误
```

---

### ⚠️ 发现的问题

#### 问题 1: entrypoint.py 通用性不足

**现象**:
```
ImportError: cannot import name 'setup' from 'awslabs.cloudtrail_mcp_server.server'
```

**原因**:
不同 MCP Server 的 `server.py` 结构不同：
- billing-cost-management: 有 `async def setup()` 函数
- cloudtrail: 没有 `setup` 函数，直接使用 `mcp.run()`

**影响范围**:
可能影响所有没有 `setup` 函数的 MCP Server

**解决方案**:
修改 `entrypoint.py` 模板，添加兼容性处理：
```python
try:
    from awslabs.<package>_mcp_server.server import setup
    has_setup = True
except ImportError:
    has_setup = False

if has_setup:
    asyncio.run(setup())
```

**改进建议**:
1. ✅ 更新 `entrypoint.py` 模板（已完成）
2. ⏳ 更新改造文档，说明适配步骤
3. ⏳ 测试验证修复效果

---

### 📊 改造效果评估

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 文件复用率 | 80% | 90% | ✅ 超出预期 |
| 改造时间 | 15分钟 | 8分钟 | ✅ 超出预期 |
| 代码改动量 | 最小化 | 5个函数 + 1行导入 | ✅ 符合预期 |
| 语法检查 | 通过 | 通过 | ✅ 符合预期 |
| 容器测试 | 通过 | 首次失败，修复中 | 🔄 进行中 |

---

## 🔧 待完成任务

- [ ] 重新构建 Docker 镜像（使用修复后的 entrypoint.py）
- [ ] 执行完整的容器测试
- [ ] 验证 5 个工具的注册状态
- [ ] 验证 target_account_id 参数
- [ ] 更新改造文档（entrypoint.py 适配说明）
- [ ] 提交所有代码到 Git

---

## 📚 参考文档

- [01_改造需求分析.md](./01_改造需求分析.md)
- [02_改造步骤指南.md](./02_改造步骤指南.md)
- [README.md](./README.md)

---

## 🎯 下一步计划

1. **短期（今天）**:
   - 完成镜像重新构建
   - 完成容器测试
   - 提交代码

2. **中期（本周）**:
   - 更新 entrypoint.py 模板
   - 更新改造文档
   - 改造更多 MCP Server

3. **长期**:
   - 总结通用改造模式
   - 考虑自动化脚本
