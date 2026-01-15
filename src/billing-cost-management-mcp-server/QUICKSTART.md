# 🚀 快速开始测试

## 一键运行（推荐）

```bash
cd /Users/liyuguang/data/gitworld/tonygithub/costq-mcp/awslabs/mcp/src/billing-cost-management-mcp-server

./run_test.sh
```

这个脚本会自动：
1. ✅ 检查 Python 版本
2. ✅ 创建/激活虚拟环境
3. ✅ 安装依赖
4. ✅ 设置默认环境变量
5. ✅ 检查 AWS 凭证
6. ✅ 运行完整测试

## 手动运行

如果你想手动控制每一步：

```bash
# 1. 进入目录
cd /Users/liyuguang/data/gitworld/tonygithub/costq-mcp/awslabs/mcp/src/billing-cost-management-mcp-server

# 2. 创建虚拟环境（如果还没有）
python3 -m venv .venv

# 3. 激活虚拟环境
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 设置环境变量（可选，脚本会自动设置默认值）
export AWS_REGION=ap-northeast-1
export RDS_SECRET_NAME=costq/rds/postgresql-dev

# 6. 运行测试
python test_setup_context.py
```

## 测试内容

脚本会测试以下功能：

1. **数据库连接** - 从 Secrets Manager 获取连接信息
2. **账号查询** - 查询账号 `000451883532` 的信息
3. **凭证提取** - 提取 AWS 凭证（AKSK 或 IAM Role）
4. **上下文设置** - 将凭证设置到 ContextVar
5. **凭证验证** - 调用 AWS STS API 验证凭证有效性

## 期望输出

```
================================================================================
开始测试 _setup_account_context 函数
================================================================================

✅ 数据库查询: 成功
✅ 凭证提取: 成功
✅ 上下文设置: 成功
✅ 凭证验证: 成功

🎉 测试完成!
```

## 常见问题

### ❌ 数据库连接失败

**解决方案**: 确认 AWS 凭证能访问 Secrets Manager
```bash
aws secretsmanager get-secret-value \
    --secret-id costq/rds/postgresql-dev \
    --region ap-northeast-1
```

### ❌ 账号不存在

**解决方案**: 确认数据库中是否有账号 `000451883532`

### ❌ AKSK 解密失败

**解决方案**: 设置 `ENCRYPTION_KEY` 环境变量
```bash
export ENCRYPTION_KEY="your-fernet-key"
```

### ❌ AssumeRole 失败

**解决方案**: 检查当前环境是否有 `sts:AssumeRole` 权限

## 查看详细文档

```bash
cat README_TEST.md
```
