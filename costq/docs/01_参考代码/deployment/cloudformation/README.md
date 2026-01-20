# 📄 CloudFormation 模板使用指南

**模板版本**: 1.0.0
**最后更新**: 2025-10-30

---

## 📋 模板文件

### costq-iam-role.yaml

**用途**: 为 CostQ 平台创建 IAM Role，支持成本分析和优化功能

**权限**:
- ✅ `ReadOnlyAccess`（AWS 托管策略）- 所有 AWS 服务只读
- ✅ `refresh-sp-recommendations`（自定义策略）- 启动 SP 推荐生成

---

## 🚀 快速部署

### 方式 1: 通过 CostQ 平台（推荐）

1. 在 CostQ 平台点击"添加 AWS 账号"
2. 选择"IAM Role"方式
3. 点击"🚀 在 AWS 中创建 IAM Role"
4. AWS 控制台会自动打开，参数已预填充
5. 点击"创建堆栈"
6. 复制 Role ARN 并返回 CostQ 平台

---

### 方式 2: 手动部署

#### 步骤 1: 获取参数

**必需参数**:
- `CostQPlatformAccountId`: 联系 CostQ 获取
- `ExternalId`: 在 CostQ 平台获取（每个组织唯一）

**可选参数**:
- `RoleName`: 默认 `CostQAgentRole`
- `SessionDuration`: 默认 `3600`（1 小时）

#### 步骤 2: 部署 CloudFormation

**通过 AWS 控制台**:

1. 登录 AWS 控制台
2. 进入 CloudFormation 服务
3. 点击"创建堆栈"
4. 上传模板文件 `costq-iam-role.yaml`
5. 填写参数：
   ```
   CostQPlatformAccountId: 123456789012  # CostQ 提供
   ExternalId: a1b2c3d4-e5f6-7890...       # CostQ 平台获取
   RoleName: CostQAgentRole               # 可选
   SessionDuration: 3600                    # 可选
   ```
6. 确认并创建

**通过 AWS CLI**:

```bash
# 1. 下载模板
wget https://costq-storage.s3.amazonaws.com/cloudformation/costq-iam-role.yaml

# 2. 部署
aws cloudformation create-stack \
  --stack-name costq-integration \
  --template-body file://costq-iam-role.yaml \
  --parameters \
    ParameterKey=CostQPlatformAccountId,ParameterValue=123456789012 \
    ParameterKey=ExternalId,ParameterValue=YOUR_EXTERNAL_ID \
    ParameterKey=RoleName,ParameterValue=CostQAgentRole \
    ParameterKey=SessionDuration,ParameterValue=3600 \
  --capabilities CAPABILITY_NAMED_IAM

# 3. 等待部署完成
aws cloudformation wait stack-create-complete \
  --stack-name costq-integration

# 4. 获取 Role ARN
aws cloudformation describe-stacks \
  --stack-name costq-integration \
  --query "Stacks[0].Outputs[?OutputKey=='RoleArn'].OutputValue" \
  --output text
```

---

## 📊 部署后验证

### 验证 1: 检查 Role 是否创建

```bash
aws iam get-role --role-name CostQAgentRole
```

预期输出：
```json
{
  "Role": {
    "RoleName": "CostQAgentRole",
    "Arn": "arn:aws:iam::123456789012:role/CostQAgentRole",
    "AssumeRolePolicyDocument": {
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"AWS": "arn:aws:iam::PLATFORM_ACCOUNT:root"},
        "Condition": {"StringEquals": {"sts:ExternalId": "..."}}
      }]
    }
  }
}
```

---

### 验证 2: 检查附加的策略

```bash
aws iam list-attached-role-policies --role-name CostQAgentRole
```

预期输出：
```json
{
  "AttachedPolicies": [
    {
      "PolicyName": "ReadOnlyAccess",
      "PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess"
    },
    {
      "PolicyName": "CostQAgentRole-RefreshSPRecommendations",
      "PolicyArn": "arn:aws:iam::123456789012:policy/..."
    }
  ]
}
```

---

### 验证 3: 测试 AssumeRole（从 CostQ 平台）

在 CostQ 平台添加账号时，系统会自动执行此验证。

手动测试（需要 CostQ 平台凭证）：
```bash
# 从 CostQ 平台账号执行
aws sts assume-role \
  --role-arn arn:aws:iam::CUSTOMER_ACCOUNT:role/CostQAgentRole \
  --role-session-name test-session \
  --external-id YOUR_EXTERNAL_ID \
  --duration-seconds 900

# 应返回临时凭证
{
  "Credentials": {
    "AccessKeyId": "ASIA...",
    "SecretAccessKey": "...",
    "SessionToken": "...",
    "Expiration": "2025-10-30T12:00:00Z"
  }
}
```

---

## 🔒 安全说明

### External ID 重要性

**什么是 External ID**:
- 一个随机生成的字符串（如 `a1b2c3d4-e5f6-7890-...`）
- 由 CostQ 平台自动生成，每个组织唯一
- 防止"混淆代理人攻击"

**为什么需要 External ID**:

假设没有 External ID：
```
1. 客户 A 创建 Role，信任 CostQ 平台账号
2. 恶意用户 B 知道客户 A 的 Role ARN
3. 用户 B 在 CostQ 平台输入客户 A 的 Role ARN
4. CostQ 平台成功 AssumeRole
5. 用户 B 访问了客户 A 的数据 ❌
```

有了 External ID：
```
1. 客户 A 创建 Role，信任 CostQ + External ID = "org-a-secret"
2. 恶意用户 B 知道 Role ARN，但不知道 External ID
3. 用户 B 尝试 AssumeRole → AWS 拒绝（External ID 不匹配）✅
```

**最佳实践**:
- ✅ 每个组织使用不同的 External ID
- ✅ External ID 长度 >= 32 字符
- ✅ 使用密码学安全的随机数生成器
- ❌ 不要共享 External ID 给其他组织

---

### 权限说明

#### ReadOnlyAccess（AWS 托管策略）

**包含的权限**:
- ✅ 所有 AWS 服务的 `Describe*`、`Get*`、`List*` 操作
- ✅ 自动包含新 AWS 服务
- ❌ **不包含任何写操作**

**示例允许的操作**:
```
✅ ec2:DescribeInstances          - 查看 EC2 实例
✅ rds:DescribeDBInstances        - 查看 RDS 数据库
✅ s3:ListBucket                  - 列出 S3 存储桶
✅ ce:GetCostAndUsage             - 获取成本数据
✅ cloudtrail:LookupEvents        - 查询 CloudTrail 事件
```

**示例拒绝的操作**:
```
❌ ec2:StartInstances             - 启动 EC2 实例
❌ ec2:StopInstances              - 停止 EC2 实例
❌ rds:DeleteDBInstance           - 删除 RDS 数据库
❌ s3:PutObject                   - 上传 S3 对象
❌ iam:CreateUser                 - 创建 IAM 用户
```

---

#### refresh-sp-recommendations（自定义策略）

**唯一允许的写操作**:
```json
{
  "Action": "ce:StartSavingsPlansPurchaseRecommendationGeneration"
}
```

**用途**:
- 启动 Savings Plans 推荐生成任务
- ⚠️ **不会自动购买** Savings Plans
- ✅ 仅生成推荐报告供您参考

**工作流程**:
```
1. CostQ 调用: ce:StartSavingsPlansPurchaseRecommendationGeneration
   → 启动异步任务

2. AWS 后台生成推荐（需要几分钟）

3. CostQ 调用: ce:GetSavingsPlansPurchaseRecommendation（只读）
   → 获取推荐结果

4. CostQ 展示推荐给您

5. 您决定是否购买（需要您手动操作）
```

---

## 🛠️ 故障排查

### 问题 1: AssumeRole 失败（Access Denied）

**可能原因**:
- External ID 不匹配
- CostQ 平台账号 ID 错误
- Role 不存在或已删除

**排查步骤**:

```bash
# 1. 检查 Role 的信任策略
aws iam get-role --role-name CostQAgentRole \
  --query 'Role.AssumeRolePolicyDocument'

# 应该看到：
{
  "Statement": [{
    "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
    "Condition": {"StringEquals": {"sts:ExternalId": "YOUR_EXTERNAL_ID"}}
  }]
}

# 2. 确认 External ID 匹配
# 在 CostQ 平台查看您的 External ID，与上面的输出对比

# 3. 确认平台账号 ID
# 联系 CostQ 确认正确的平台账号 ID
```

---

### 问题 2: 权限不足（Permission Denied）

**可能原因**:
- ReadOnlyAccess 策略未附加
- 尝试执行写操作（除 SP 推荐外）

**排查步骤**:

```bash
# 检查附加的策略
aws iam list-attached-role-policies --role-name CostQAgentRole

# 应该看到两个策略：
# 1. ReadOnlyAccess
# 2. CostQAgentRole-RefreshSPRecommendations
```

---

### 问题 3: Session 频繁过期

**原因**:
- SessionDuration 设置过短

**解决方案**:

```bash
# 更新 CloudFormation Stack
aws cloudformation update-stack \
  --stack-name costq-integration \
  --use-previous-template \
  --parameters \
    ParameterKey=SessionDuration,ParameterValue=7200  # 2 小时

# 或直接修改 Role
aws iam update-role \
  --role-name CostQAgentRole \
  --max-session-duration 7200
```

---

## 🗑️ 删除部署

### 撤销 CostQ 平台访问权限

**方式 1: 删除 CloudFormation Stack（推荐）**

```bash
# 通过 CLI
aws cloudformation delete-stack \
  --stack-name costq-integration

# 通过控制台
# CloudFormation → 选择 Stack → 删除
```

**方式 2: 手动删除 Role**

```bash
# 1. 分离策略
aws iam detach-role-policy \
  --role-name CostQAgentRole \
  --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

aws iam detach-role-policy \
  --role-name CostQAgentRole \
  --policy-arn $(aws iam list-attached-role-policies \
    --role-name CostQAgentRole \
    --query 'AttachedPolicies[?contains(PolicyName, `RefreshSP`)].PolicyArn' \
    --output text)

# 2. 删除自定义策略
aws iam delete-policy \
  --policy-arn $(aws iam list-policies \
    --query 'Policies[?contains(PolicyName, `RefreshSP`)].Arn' \
    --output text)

# 3. 删除 Role
aws iam delete-role --role-name CostQAgentRole
```

**⚠️ 注意**: 删除后，CostQ 平台将无法访问您的账号数据。

---

## 📞 获取帮助

### 常见问题

**Q: 此 Role 会产生费用吗？**
A: 不会。STS AssumeRole 免费，Cost Explorer API 前 2000 次/月免费。

**Q: 可以修改 Role 名称吗？**
A: 可以。更新 CloudFormation Stack 的 `RoleName` 参数即可。

**Q: 可以撤销某个特定权限吗？**
A: 可以，但不推荐。修改策略可能导致 CostQ 功能异常。

**Q: External ID 可以修改吗？**
A: 可以，但修改后需要在 CostQ 平台重新配置账号。

**Q: 支持跨区域吗？**
A: 支持。IAM 是全球服务，Role 在所有区域有效。

---

### 联系支持

- 📧 邮件: support@strands.example.com
- 📖 文档: https://docs.strands.example.com
- 💬 社区: https://community.strands.example.com

---

## 📝 版本历史

### v1.0.0 (2025-10-30)
- 初始版本
- ReadOnlyAccess + refresh-sp-recommendations
- 支持 External ID 验证
- 可配置会话时长

---

**最后更新**: 2025-10-30
**模板版本**: 1.0.0
