# AWS RISP (Reserved Instance & Savings Plans) MCP Server

## 🎯 概述

AWS RISP MCP Server 是一个专门用于分析 AWS Reserved Instance (RI) 和 Savings Plans (SP) 的 Model Context Protocol (MCP) 服务器。它提供了全面的 RISP 分析功能，帮助用户优化 AWS 成本。

## ✨ 核心功能

### Reserved Instance (RI) 分析
- **利用率分析** (`get_reservation_utilization`) - 监控 RI 使用效率
- **覆盖率分析** (`get_reservation_coverage`) - 查看 RI 覆盖的使用量比例
- **购买推荐** (`get_reservation_purchase_recommendation`) - 获取智能 RI 购买建议

### Savings Plans (SP) 分析
- **利用率分析** (`get_savings_plans_utilization`) - 监控 SP 使用效率
- **覆盖率分析** (`get_savings_plans_coverage`) - 查看 SP 覆盖的支出比例
- **购买推荐** (`get_savings_plans_purchase_recommendation`) - 获取智能 SP 购买建议
- **推荐生成** (`start_savings_plans_purchase_recommendation_generation`) - 启动 SP 推荐生成（异步）

## 🚀 快速开始

### 前置要求

1. **Python 3.8+**
2. **AWS 凭证配置**
3. **必需的 AWS 权限**：
   - `ce:GetReservationUtilization`
   - `ce:GetReservationCoverage`
   - `ce:GetReservationPurchaseRecommendation`
   - `ce:GetSavingsPlansUtilization`
   - `ce:GetSavingsPlansCoverage`
   - `ce:GetSavingsPlansPurchaseRecommendation`
   - `ce:StartSavingsPlansPurchaseRecommendationGeneration`

### 安装依赖

```bash
# 安装必需的 Python 包
pip install mcp fastmcp boto3 pydantic loguru
```

### 启动服务器

#### 方法 1：使用专用启动脚本
```bash
# 使用项目提供的启动脚本
./scripts/start_risp.sh

# 或者带参数启动
./scripts/start_risp.sh --log-level DEBUG --aws-profile prod
```

#### 方法 2：直接运行
```bash
# 设置环境变量
export AWS_PROFILE=default
export FASTMCP_LOG_LEVEL=INFO
export PYTHONPATH=.

# 启动服务器
python -m mcp-core.risp_mcp_server.server
```

#### 方法 3：集成到主应用
```bash
# 启动包含 RISP 功能的完整应用
./scripts/start_web.sh
```

## 🔧 配置

### 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `AWS_PROFILE` | AWS 配置文件名称 | `default` |
| `AWS_REGION` | AWS 区域 | `us-east-1` |
| `FASTMCP_LOG_LEVEL` | 日志级别 | `WARNING` |

### MCP 配置

在 `config/mcp_config.json` 中添加 RISP 服务器配置：

```json
{
  "servers": {
    "risp-analyzer": {
      "command": "python",
      "args": ["-m", "mcp-core.risp_mcp_server.server"],
      "cwd": ".",
      "env": {
        "AWS_PROFILE": "default",
        "FASTMCP_LOG_LEVEL": "INFO",
        "PYTHONPATH": "."
      },
      "description": "AWS RISP MCP 服务器"
    }
  }
}
```

## 📊 使用示例

### Reserved Instance 分析

```python
# RI 利用率分析
result = await get_reservation_utilization(
    context=context,
    time_period=DateRange(start_date="2024-01-01", end_date="2024-01-31"),
    granularity="MONTHLY",
    group_by_subscription_id=True
)

# RI 覆盖率分析
result = await get_reservation_coverage(
    context=context,
    time_period=DateRange(start_date="2024-01-01", end_date="2024-01-31"),
    group_by=["SERVICE", "INSTANCE_TYPE"]
)

# RI 购买推荐
result = await get_reservation_purchase_recommendation(
    context=context,
    service="EC2-Instance",
    term_in_years="ONE_YEAR",
    payment_option="NO_UPFRONT",
    lookback_period_in_days="THIRTY_DAYS"
)
```

### Savings Plans 分析

```python
# SP 利用率分析
result = await get_savings_plans_utilization(
    context=context,
    time_period=DateRange(start_date="2024-01-01", end_date="2024-01-31"),
    granularity="DAILY"
)

# SP 覆盖率分析
result = await get_savings_plans_coverage(
    context=context,
    time_period=DateRange(start_date="2024-01-01", end_date="2024-01-31"),
    group_by=["SERVICE"]
)

# SP 购买推荐（需要先生成）
# 1. 启动推荐生成
generation_result = await start_savings_plans_purchase_recommendation_generation(
    context=context,
    savings_plans_type="COMPUTE_SP",
    term_in_years="ONE_YEAR",
    payment_option="NO_UPFRONT",
    lookback_period_in_days="THIRTY_DAYS"
)

# 2. 获取推荐结果（等待生成完成后）
recommendation_result = await get_savings_plans_purchase_recommendation(
    context=context,
    savings_plans_type="COMPUTE_SP",
    term_in_years="ONE_YEAR",
    payment_option="NO_UPFRONT",
    lookback_period_in_days="THIRTY_DAYS"
)
```

## 🎯 成本优化建议

### Reserved Instance 优化
- **监控利用率**：目标 >80% 利用率
- **分析覆盖率**：识别未覆盖的使用量
- **定期评估**：每月检查 RI 推荐
- **考虑可转换 RI**：提供更大灵活性

### Savings Plans 优化
- **Compute SP**：最大灵活性，适用于多种服务
- **EC2 Instance SP**：特定使用模式下更高折扣
- **监控双重指标**：利用率和覆盖率
- **期限选择**：1年 vs 3年基于使用预测

### RI vs SP 对比
- **灵活性**：SP > RI
- **折扣率**：取决于具体使用模式
- **管理复杂度**：SP < RI
- **适用场景**：根据工作负载特性选择

## ⚠️ 重要注意事项

1. **API 成本**：每次 Cost Explorer API 调用费用 $0.01
2. **数据延迟**：利用率数据可能有 24 小时延迟
3. **推荐生成**：SP 推荐需要异步生成，通常需要几分钟
4. **权限要求**：确保 IAM 角色具有所有必需的 Cost Explorer 权限
5. **区域限制**：Cost Explorer API 仅在 us-east-1 区域可用

## 🧪 测试

```bash
# 运行所有测试
python -m pytest mcp-core/risp_mcp_server/tests/

# 运行特定测试
python -m pytest mcp-core/risp_mcp_server/tests/test_ri_handler.py

# 运行测试并显示覆盖率
python -m pytest mcp-core/risp_mcp_server/tests/ --cov=mcp-core.risp_mcp_server
```

## 🔍 故障排除

### 常见问题

1. **AWS 凭证错误**
   ```bash
   # 检查 AWS 凭证
   aws sts get-caller-identity
   ```

2. **权限不足**
   ```bash
   # 测试 Cost Explorer 权限
   aws ce get-dimension-values --time-period Start=2024-01-01,End=2024-01-02 --dimension SERVICE
   ```

3. **服务器启动失败**
   ```bash
   # 检查 Python 路径和依赖
   python -c "import mcp, fastmcp, boto3, pydantic, loguru"
   ```

### 日志调试

```bash
# 启用详细日志
export FASTMCP_LOG_LEVEL=DEBUG
python -m mcp-core.risp_mcp_server.server
```

## 📈 性能优化

1. **使用过滤器**：减少 API 调用的数据量
2. **合理的时间范围**：避免过长的查询期间
3. **批量查询**：合并相关的分析请求
4. **缓存结果**：对于重复查询考虑缓存

## 🤝 贡献

这个项目遵循开源最佳实践，欢迎贡献：

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 📄 许可证

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
Licensed under the Apache License, Version 2.0.
