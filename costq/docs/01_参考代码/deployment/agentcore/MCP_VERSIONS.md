# MCP Server 版本管理

本文档记录 CostQ 项目使用的所有 AWS Labs MCP Server 的版本历史和更新日志。

---

## 📊 当前版本 (2025-12-14)

| MCP Server | 版本 | PyPI 最新版本 | 状态 |
|-----------|------|-------------|------|
| cost-explorer | **0.0.14** | 0.0.14 | ✅ 最新 |
| aws-pricing | **1.0.20** | 1.0.20 | ✅ 最新 |
| aws-documentation | **1.1.13** | 1.1.13 | ✅ 最新 |
| billing-cost-management | **0.0.7** | 0.0.7 | ✅ 最新 |
| cloudtrail | **0.0.6** | 0.0.6 | ✅ 最新 |

---

## 🔒 版本锁定策略

**策略**: 所有 MCP Server 版本**已锁定**，不使用 `latest`

**原因**:
1. ✅ **生产稳定性优先**: 避免自动更新导致的意外问题
2. ✅ **可控的更新节奏**: 主动选择更新时机，而非被动接受
3. ✅ **便于问题定位**: 明确知道使用的版本，便于回溯和调试
4. ✅ **符合行业最佳实践**: 生产环境推荐锁定依赖版本

---

## 📝 版本更新历史

### 2025-12-14 - 统一版本锁定策略

**更新内容**:
- ✅ cost-explorer: `0.0.13` → `0.0.14` (补丁版本更新)
- ✅ aws-pricing: 锁定版本为 `1.0.20` (之前为 latest)
- ✅ aws-documentation: 锁定版本为 `1.1.13` (之前为 latest)
- ✅ billing-cost-management: 锁定版本为 `0.0.7` (之前为 latest)
- ✅ cloudtrail: 锁定版本为 `0.0.6` (之前为 latest)

**更新原因**:
- 统一版本管理策略，提高生产环境稳定性
- cost-explorer 从 0.0.13 更新到 0.0.14，获取最新 bug 修复

**影响评估**:
- ✅ 风险：低（仅 cost-explorer 有版本变更，其他只是策略调整）
- ✅ 兼容性：高（补丁版本更新，无 breaking changes）
- ✅ 功能影响：无（功能完全兼容）

**部署环境**:
- ✅ 开发环境: 已部署 (2025-12-14 15:18) - Runtime ID: cosq_agentcore_runtime_development-49gbDzHm0G
- ✅ 生产环境: 已部署 (2025-12-14 15:24) - Runtime ID: cosq_agentcore_runtime_production-5x9j6eBjmZ

**镜像 URI**: `000451883532.dkr.ecr.ap-northeast-1.amazonaws.com/costq-agentcore:v20251214-151435`

**验证结果**:
- ✅ 开发环境验证通过 (MCP 加载 0.6s, 57 工具)
- ✅ 生产环境验证通过 (MCP 加载 0.74s, 57 工具, Agent 智能错误修正)
- ✅ 详细测试报告:
  - `docs/问题分析/20251214_dev_runtime_test_result.md`
  - `docs/问题分析/20251214_prod_runtime_test_result.md`

---

### 2025-12-14 之前 - 混合版本策略

**版本配置**:
- cost-explorer: `0.0.13` (锁定)
- aws-pricing: `latest` (自动跟随)
- aws-documentation: `latest` (自动跟随)
- billing-cost-management: `latest` (自动跟随)
- cloudtrail: `latest` (自动跟随)

**问题**:
- ⚠️ 版本策略不统一，管理复杂
- ⚠️ `latest` 可能引入不兼容变更
- ⚠️ 难以回溯和定位问题版本

---

## 🔍 版本检查流程

### 定期检查 (每月 1 次)

**时间**: 每月 14 号
**负责人**: DevOps Team

**检查命令**:
```bash
# 检查所有 MCP Server 最新版本
pip index versions awslabs.cost-explorer-mcp-server | grep "LATEST:"
pip index versions awslabs.aws-pricing-mcp-server | grep "LATEST:"
pip index versions awslabs.aws-documentation-mcp-server | grep "LATEST:"
pip index versions awslabs.billing-cost-management-mcp-server | grep "LATEST:"
pip index versions awslabs.cloudtrail-mcp-server | grep "LATEST:"
```

**检查内容**:
1. 是否有新版本发布
2. 查看版本更新日志（CHANGELOG）
3. 评估更新风险和收益
4. 决定是否更新

---

### 安全更新 (每周 1 次)

**时间**: 每周一
**负责人**: Security Team

**检查命令**:
```bash
# 检查安全漏洞
pip-audit
```

**处理流程**:
1. 如发现安全漏洞，立即评估影响
2. 检查是否有修复版本
3. 紧急更新到安全版本
4. 记录更新日志

---

## 📋 版本更新检查清单

### 更新前

- [ ] 检查所有 MCP Server 最新版本
- [ ] 查看版本更新日志（CHANGELOG）
  - GitHub: https://github.com/awslabs/mcp-servers
  - PyPI: https://pypi.org/project/awslabs.{package-name}/
- [ ] 评估更新风险
  - 是否有 breaking changes
  - 是否影响现有功能
  - 是否需要代码修改
- [ ] 准备回滚方案
  - 记录当前镜像 URI
  - 准备回滚命令

---

### 更新中

- [ ] 修改 `deployment/agentcore/Dockerfile`
  - 更新版本号
  - 重新构建镜像
- [ ] 修改 `backend/mcp/mcp_manager.py`
  - 同步版本号
  - 更新注释
- [ ] 更新本文档 (`MCP_VERSIONS.md`)
  - 记录更新时间
  - 记录更新原因
  - 记录影响评估
- [ ] 构建并推送镜像
  ```bash
  cd deployment/agentcore
  ./01-build_and_push.sh
  ```
- [ ] 更新开发环境 Runtime
  ```bash
  aws bedrock-agentcore update-runtime \
    --runtime-id cosq_agentcore_runtime_development-49gbDzHm0G \
    --image-uri <新镜像URI> \
    --region ap-northeast-1 \
    --profile 3532
  ```

---

### 更新后

- [ ] 验证开发环境
  - MCP 加载成功（8/8）
  - 所有工具可用（57 个）
  - 无 ERROR 日志
- [ ] 功能测试
  - cost-explorer: 查询成本数据
  - aws-pricing: 查询定价信息
  - aws-documentation: 搜索文档
  - billing-cost-management: 查询优化建议
  - cloudtrail: 查询审计日志
- [ ] 性能测试
  - MCP 加载时间 < 15 秒
  - 查询响应时间正常
- [ ] 监控日志（24-48 小时）
  - 无 ERROR 日志
  - 无异常警告
  - 无性能下降
- [ ] 更新生产环境
  ```bash
  aws bedrock-agentcore update-runtime \
    --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
    --image-uri <新镜像URI> \
    --region ap-northeast-1 \
    --profile 3532
  ```
- [ ] 生产环境验证（同开发环境）
- [ ] 更新完成通知
  - 通知团队成员
  - 记录到 Confluence/Wiki

---

## 🔄 回滚流程

**触发条件**:
- 发现严重 bug
- 功能异常
- 性能严重下降
- 生产事故

**回滚步骤**:
```bash
# 1. 查找上一个稳定镜像 URI
# （记录在更新日志中）

# 2. 回滚开发环境
aws bedrock-agentcore update-runtime \
  --runtime-id cosq_agentcore_runtime_development-49gbDzHm0G \
  --image-uri <上一个稳定镜像URI> \
  --region ap-northeast-1 \
  --profile 3532

# 3. 验证功能正常

# 4. 回滚生产环境
aws bedrock-agentcore update-runtime \
  --runtime-id cosq_agentcore_runtime_production-5x9j6eBjmZ \
  --image-uri <上一个稳定镜像URI> \
  --region ap-northeast-1 \
  --profile 3532

# 5. 验证生产环境

# 6. 记录回滚原因和事后分析
```

---

## 📚 参考资料

### PyPI 包地址

- [awslabs.cost-explorer-mcp-server](https://pypi.org/project/awslabs.cost-explorer-mcp-server/)
- [awslabs.aws-pricing-mcp-server](https://pypi.org/project/awslabs.aws-pricing-mcp-server/)
- [awslabs.aws-documentation-mcp-server](https://pypi.org/project/awslabs.aws-documentation-mcp-server/)
- [awslabs.billing-cost-management-mcp-server](https://pypi.org/project/awslabs.billing-cost-management-mcp-server/)
- [awslabs.cloudtrail-mcp-server](https://pypi.org/project/awslabs.cloudtrail-mcp-server/)

### GitHub 仓库

- [AWS Labs MCP Servers](https://github.com/awslabs/mcp-servers)

### 官方文档

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [AWS Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/)

---

## 📞 联系人

**版本管理负责人**: DevOps Team
**紧急联系**: Security Team (安全漏洞)

---

**最后更新**: 2025-12-14
**下次检查**: 2025-01-14
