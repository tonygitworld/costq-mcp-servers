# MCP Server 多账号权限传递改造分析

> 📅 **创建日期**: 2025-01-17
> 📊 **状态**: 已完成
> 🎯 **目标**: 标准化 MCP Server 多账号改造流程

---

## 📚 文档导航

### 核心文档

1. **[改造需求分析](./01_改造需求分析.md)** ⭐️ 必读
   - 背景说明和架构概述
   - 核心问题和解决方案
   - 详细改造点分析
   - 数据库设计和环境变量配置

2. **[改造步骤指南](./02_改造步骤指南.md)** ⭐️ 必读
   - 详细的可执行改造步骤
   - 代码模板和示例
   - 常见问题排查
   - 部署上线指南

3. **[Skill vs Memory 方案对比](./03_Skill_vs_Memory方案对比.md)**
   - 两种方案的详细对比
   - 优缺点分析
   - 适用场景
   - 最终推荐方案

4. **[改造自动化方案](./04_改造自动化方案.md)**
   - Skill 自动化实现
   - CLI 工具
   - CI/CD 集成
   - 批量改造脚本

---

## 🎯 快速开始

### 场景 1: 我要改造一个新的 MCP Server

**方式 A: 手工改造（适合学习和理解）**
```bash
# 1. 阅读改造步骤指南
cat 02_改造步骤指南.md

# 2. 按照步骤执行
cd src/<your-mcp-server>
# ... 按照文档逐步操作
```

**方式 B: 自动化改造（推荐，快速）**
```bash
# 使用 Skill 自动化工具
python skills/mcp_migration_cli.py src/<your-mcp-server>

# 人工审查修改
git diff src/<your-mcp-server>

# 运行测试
pytest src/<your-mcp-server>/tests
```

---

### 场景 2: 我要理解改造原理

**阅读顺序**：
1. [改造需求分析](./01_改造需求分析.md) → 理解背景和核心概念
2. [改造步骤指南](./02_改造步骤指南.md) 第 3 章 → 看具体改造模板
3. 参考实际代码 → `src/billing-cost-management-mcp-server/`

**关键知识点**：
- ✅ 账号上下文传递机制
- ✅ 凭证提取服务层设计
- ✅ 环境变量管理
- ✅ 异常处理模式
- ✅ boto3 自动识别凭证

---

### 场景 3: 我要批量改造多个 MCP Server

```bash
# 1. 准备批量改造脚本
cat 04_改造自动化方案.md | grep -A 30 "批量改造"

# 2. 执行批量改造
./scripts/batch_migrate.sh

# 3. 逐个审查和提交
# ... 按提示操作
```

---

## 🎯 快速参考：哪些文件可以直接复制？

| 文件/目录 | 是否可复制 | 需要修改 | 说明 |
|-----------|-----------|---------|------|
| `cred_extract_services/` | ✅ **可直接复制** | ❌ 无需修改 | 完全通用，自包含，不依赖项目代码 |
| `Dockerfile-AgentCore-Runtime` | ✅ **可直接复制** | ❌ 无需修改 | 通用模板，使用相对路径和环境变量 |
| `entrypoint.py` | ⚠️ **可复制但需修改** | ✅ 修改 1 行 | 需要修改导入路径：`from awslabs.<your_package>_mcp_server.server import mcp, setup` |
| `costq/scripts/build_*.sh` | ⚠️ **可复制但需修改** | ✅ 修改 1 个变量 | 需要修改 `MCP_SERVER_NAME="<your-mcp-server-name>"` |

**改造速度**：
- ✅ **80% 文件可直接复制**（2 分钟）
- ⚠️ **20% 需要简单修改**（3 分钟）
- 🔧 **修改 Tool 函数**（5-10 分钟）
- 🚀 **总计：10-15 分钟完成改造**

---

## 📊 改造统计

### 已完成改造
| MCP Server | 改造日期 | 状态 | 备注 |
|-----------|---------|------|------|
| billing-cost-management-mcp-server | 2025-01-17 | ✅ 已完成 | 参考实现 |

### 待改造列表
| MCP Server | 优先级 | 预计时间 | 备注 |
|-----------|-------|---------|------|
| cloudwatch-mcp-server | 高 | 10 分钟 | 直接复制文件 |
| s3-tables-mcp-server | 高 | 10 分钟 | 直接复制文件 |
| lambda-tool-mcp-server | 中 | 10 分钟 | 直接复制文件 |
| ... | ... | ... | ... |

---

## 🔑 核心改造点总结

### 1. 新增凭证提取服务层
```
cred_extract_services/
├── __init__.py           # 公共接口
├── aws_client.py         # STS AssumeRole
├── context_manager.py    # 环境变量管理
├── credential_extractor.py  # 凭证提取核心
├── crypto.py             # AKSK 解密
├── database.py           # 数据库查询
└── exceptions.py         # 自定义异常
```

**职责**：
- 查询数据库获取账号信息
- 根据 auth_type 提取凭证（AKSK/IAM Role）
- 设置 boto3 标准环境变量

### 1.5 新增 Dockerfile-AgentCore-Runtime
**目的**：构建专门用于 AgentCore Runtime 部署的 ARM64 镜像

**关键内容**：
- 复制 `entrypoint.py` 和 `cred_extract_services/`
- 安装额外依赖（OpenTelemetry、SQLAlchemy、psycopg2、cryptography）
- 使用 `opentelemetry-instrument` 启动
- 配置 MCP 和 AWS 环境变量

### 1.6 新增部署脚本
**路径**：`costq/scripts/01-build_and_push_<mcp-server-name>.sh`

**功能**：
- 一键构建 ARM64 Docker 镜像
- 自动登录 ECR
- 打标签并推送到 ECR
- 提供后续操作提示

**使用**：
```bash
# 复制模板
cp costq/scripts/build_and_push_template.sh \
   costq/scripts/01-build_and_push_<mcp-server-name>.sh

# 修改配置
vim costq/scripts/01-build_and_push_<mcp-server-name>.sh
# 修改 MCP_SERVER_NAME="<mcp-server-name>"

# 执行部署
bash costq/scripts/01-build_and_push_<mcp-server-name>.sh
```

---

### 2. 新增统一入口
```python
# entrypoint.py
async def _setup_account_context(target_account_id: str) -> dict:
    """设置 AWS 凭证上下文"""
    # 1. 提取凭证
    credentials = await extract_aws_credentials(target_account_id)

    # 2. 设置环境变量
    set_aws_credentials(...)

    # 3. 返回脱敏信息
    return {"account_id": ..., "auth_type": ...}
```

---

### 3. 修改所有 Tool 函数
```python
# 每个 tool 函数都添加：
async def tool_function(
    ctx: Context,
    target_account_id: Optional[str] = None,  # ✅ 新增参数
    # ... 业务参数
):
    try:
        # ✅ 账号上下文初始化
        if target_account_id:
            from entrypoint import _setup_account_context
            await _setup_account_context(target_account_id)

        # ===== 原有业务逻辑（完全不变）=====
        # ...

    # ✅ 异常处理
    except AccountNotFoundError:
        return format_response('error', ...)
    # ... 其他异常
```

---

### 4. 零侵入性原则
✅ **关键**：工具函数（`create_aws_client`）完全不变

```python
# utilities/aws_service_base.py
def create_aws_client(service_name: str, region_name: str = None):
    # 逻辑完全不变！
    # boto3 自动从环境变量读取凭证
    session = boto3.Session(region_name=region)
    return session.client(service_name, config=config)
```

**原理**：boto3 自动识别这些环境变量
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (可选)
- `AWS_DEFAULT_REGION`

---

## 🎓 最佳实践

### ✅ 推荐方案
1. **Skill 自动化**（核心）
   - 批量改造快速
   - 一致性强
   - 易于维护

2. **Memory 记忆**（辅助）
   - 存储设计原则
   - 常见问题库
   - 历史经验

### ⚠️ 注意事项
1. **必须人工审查**
   - 自动化工具可能遗漏边界情况
   - git diff 检查所有修改

2. **完整测试**
   - 单元测试
   - 集成测试
   - 多账号切换测试

3. **安全检查**
   - 日志不包含敏感信息
   - External ID 正确验证
   - Session Token 正确处理

---

## 🔗 相关资源

### 参考代码
- [billing-cost-management-mcp-server](../../src/billing-cost-management-mcp-server/) - 参考实现
- [entrypoint.py](../../src/billing-cost-management-mcp-server/entrypoint.py) - 统一入口示例
- [cred_extract_services/](../../src/billing-cost-management-mcp-server/cred_extract_services/) - 凭证服务示例

### 外部文档
- [AWS IAM Roles for Cross-Account Access](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_aws-accounts.html)
- [boto3 Credentials Configuration](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
- [MCP Server Authentication](https://modelcontextprotocol.io/docs/concepts/authentication)

---

## 📞 联系和反馈

### 问题反馈
- 发现 Bug？请创建 Issue
- 改进建议？欢迎 Pull Request

### 文档维护
- 最后更新：2025-01-17
- 维护者：@tonygitworld
- 版本：v1.0

---

## 📝 变更历史

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2025-01-17 | v1.0 | 初始版本，完成核心文档 |
| 2025-01-15 | v0.1 | billing-cost-management-mcp-server 改造完成 |

---

**祝改造顺利！有任何问题随时联系。** 🚀
