# 测试 _setup_account_context 函数

## 📋 测试目的

验证多账号凭证提取功能是否正常工作：
1. 数据库连接和账号查询
2. AWS 凭证提取（AKSK 或 IAM Role）
3. ContextVar 设置
4. 凭证有效性验证

## 🚀 快速开始

### 前置条件

1. **Python 环境**: Python 3.11+
2. **AWS 凭证**: 需要能够访问 Secrets Manager（获取数据库连接信息）
3. **网络**: 能够连接到 RDS 数据库

### 安装依赖

```bash
cd /Users/liyuguang/data/gitworld/tonygithub/costq-mcp/awslabs/mcp/src/billing-cost-management-mcp-server

# 如果还没有虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 运行测试

```bash
# 确保在虚拟环境中
source .venv/bin/activate

# 运行测试脚本
python test_setup_context.py
```

测试脚本会**自动设置**默认的环境变量：
- `RDS_SECRET_NAME=costq/rds/postgresql-dev`
- `AWS_REGION=ap-northeast-1`

## 📝 测试步骤

脚本会按顺序执行以下步骤：

### 步骤 1: 检查环境变量
- ✅ AWS_REGION
- ✅ DATABASE_URL / RDS_SECRET_NAME
- ⚠️ ENCRYPTION_KEY（仅 AKSK 类型需要）

### 步骤 2: 导入模块
- ✅ `entrypoint._setup_account_context`
- ✅ `cred_extract_services.*`

### 步骤 3: 查询账号信息
- 📊 从数据库查询账号 `000451883532`
- 📊 显示账号类型、区域、认证方式

### 步骤 4: 提取凭证
- 🔐 根据账号类型提取 AWS 凭证
- 🔐 AKSK: 解密 Secret Access Key
- 🔐 IAM Role: 执行 AssumeRole

### 步骤 5: 测试完整函数
- 🚀 调用 `_setup_account_context("000451883532")`
- 🚀 验证返回值

### 步骤 6: 验证凭证有效性
- ✅ 调用 `STS GetCallerIdentity`
- ✅ 确认凭证可以正常使用

## 🔧 常见问题

### 问题 1: 数据库连接失败

**错误信息**: `DatabaseConnectionError` 或 `Secrets Manager` 相关错误

**解决方案**:
1. 确认 AWS 凭证有效（能够访问 Secrets Manager）
2. 确认密钥名称正确：`costq/rds/postgresql-dev`
3. 确认网络能够访问 RDS

```bash
# 测试 Secrets Manager 访问
aws secretsmanager get-secret-value \
    --secret-id costq/rds/postgresql-dev \
    --region ap-northeast-1
```

### 问题 2: 账号不存在

**错误信息**: `AccountNotFoundError: 账号不存在: 000451883532`

**解决方案**:
1. 连接数据库检查账号是否存在：
```bash
# 在 EKS Pod 中执行
kubectl exec -it deployment/costq-fastapi -n costq-fastapi -c app -- python3 << 'EOF'
import asyncio
from backend.database import get_db
from backend.models.aws_account import AWSAccount

async def check():
    async for db in get_db():
        acc = db.query(AWSAccount).filter(AWSAccount.account_id=='000451883532').first()
        if acc:
            print(f"账号存在: {acc.alias}, 类型: {acc.auth_type}")
        else:
            print("账号不存在")
        break

asyncio.run(check())
EOF
```

### 问题 3: AKSK 解密失败

**错误信息**: `CredentialDecryptionError: AKSK 凭证提取失败`

**解决方案**:
1. 设置 `ENCRYPTION_KEY` 环境变量
2. 确认密钥格式正确（Base64 编码的 Fernet 密钥）

```bash
export ENCRYPTION_KEY="your-base64-encoded-fernet-key"
```

### 问题 4: AssumeRole 失败

**错误信息**: `AssumeRoleError: AssumeRole 失败`

**解决方案**:
1. 确认当前环境有 `sts:AssumeRole` 权限
2. 检查目标 Role 的信任策略
3. 验证 Role ARN 是否正确

```bash
# 测试 AssumeRole
aws sts assume-role \
    --role-arn "arn:aws:iam::000451883532:role/YourTargetRole" \
    --role-session-name "test-session"
```

## 📊 成功输出示例

```
================================================================================
开始测试 _setup_account_context 函数
================================================================================

📋 步骤 1: 检查环境变量
--------------------------------------------------------------------------------
✅ AWS_REGION: ap-northeast-1
✅ RDS_SECRET_NAME: costq/rds/postgresql-dev

📦 步骤 2: 导入模块
--------------------------------------------------------------------------------
✅ 成功导入 _setup_account_context
✅ 成功导入 cred_extract_services 模块

🔍 步骤 3: 查询账号信息 (账号ID: 000451883532)
--------------------------------------------------------------------------------
✅ 成功查询到账号信息:
   - 账号 ID: 000451883532
   - 别名: Production
   - 认证类型: iam_role
   - 区域: ap-northeast-1
   - Role ARN: arn:aws:iam::000451883532:role/CostQAssumeRole

🔐 步骤 4: 提取 AWS 凭证
--------------------------------------------------------------------------------
✅ 成功提取凭证:
   - 认证类型: iam_role
   - 区域: ap-northeast-1
   - 账号 ID: 000451883532
   - 别名: Production

🚀 步骤 5: 测试完整的 _setup_account_context 函数
--------------------------------------------------------------------------------
✅ 成功设置 AWS 凭证上下文!
返回的脱敏信息:
   - 账号 ID: 000451883532
   - 别名: Production
   - 认证类型: iam_role
   - 区域: ap-northeast-1

✅ 步骤 6: 验证凭证有效性
--------------------------------------------------------------------------------
✅ 凭证有效! 调用者身份:
   - Account: 000451883532
   - UserId: AROAXXXXXXXXXXXXXXXXX:costq-session-xxx
   - Arn: arn:aws:sts::000451883532:assumed-role/CostQAssumeRole/costq-session-xxx

================================================================================
🎉 测试完成!
================================================================================
```

## 🎯 下一步

测试成功后：

1. **部署到 Runtime**
   ```bash
   cd /Users/liyuguang/data/gitworld/tonygithub/costq-mcp
   ./deployment/01-build_and_push.sh
   ```

2. **通过 Gateway 测试**
   - 使用 Strands Agent 调用 MCP Server
   - 传入 `target_account_id` 参数
   - 验证是否使用正确的账号凭证

3. **验证多账号查询**
   - 测试不同账号的成本查询
   - 验证凭证隔离是否正确

## 📚 相关文档

- 凭证提取服务设计：`cred_extract_services/README.md`
- 多账号功能设计：`docs/20260106_多账号凭证管理设计.md`
- Gateway 权限诊断：`docs/20260111_gateway_permission_diagnosis.md`
