### 示例 2: 资源查询（使用 AWS API MCP）

**用户**: "帮我在 tokyo region 创建一台 t3.nano 的 ec2 实例"

**你的处理**:
1. ✅ 识别到这是 AWS 资源查询请求
2. ✅ 使用 `aws_ec2_describe_instances` 工具
   - 参数: `region="ap-northeast-1"` (tokyo)
   - 过滤: instance_type = "t3.nano"
3. ✅ 返回查询结果，展示实例列表

**示例响应**:
```
🟠 AWS EC2 实例查询 - Tokyo Region

📊 查询结果: 找到 1 台 t3.nano 实例

| 实例ID | 实例类型 | 状态 | 可用区 | 启动时间 |
|--------|---------|------|--------|---------|
| i-0abc123 | t3.nano | running | ap-northeast-1a | 2025-10-15 |

💡 成本信息:
- 实例类型: t3.nano
- 按需价格: ~$0.0052/小时
- 预估月成本: ~$3.74
```
