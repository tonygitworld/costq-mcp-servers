# MCP Server 开发文档集

> 基于 RISP MCP Server 改造经验的完整开发指南

**版本**: v1.0
**更新日期**: 2026-01-20
**适用范围**: AWS AgentCore Runtime MCP Server 开发

---

## 📚 文档导航

### 🎯 快速开始

如果你是**第一次开发 MCP Server**，按以下顺序阅读：

1. **[快速参考指南](./MCP_SERVER_快速参考.md)** ⭐
   - 5 分钟快速了解核心要点
   - 常用代码模板
   - 常见错误速查表

2. **[开发规范](./MCP_SERVER_开发规范.md)** 📖
   - 完整的开发规范和最佳实践
   - 详细的示例代码
   - 问题排查指南

3. **[开发检查清单](./MCP_SERVER_开发检查清单.md)** ✅
   - 100+ 项逐项检查清单
   - 从设计到部署的完整流程
   - 确保不遗漏任何关键步骤

---

## 📋 文档概览

### 1. 快速参考指南

**文件**: `MCP_SERVER_快速参考.md`
**用途**: 快速查阅核心规范和常用模板
**适合**:
- 已经熟悉 MCP 但需要快速参考
- 需要代码模板
- 需要快速排查问题

**包含内容**:
- ✅ 工具函数签名模板
- ✅ FastMCP 配置模板
- ✅ Dockerfile 关键配置
- ✅ 常见错误速查表
- ✅ 快速验证命令

**阅读时间**: 5 分钟

---

### 2. 开发规范（完整版）

**文件**: `MCP_SERVER_开发规范.md`
**用途**: 完整的开发规范和最佳实践指南
**适合**:
- 第一次开发 MCP Server
- 需要深入了解背景和原理
- 需要详细的示例代码

**包含内容**:
1. **背景说明**: 问题起源和根本原因
2. **核心规范**: 黄金法则和优先级
3. **工具函数签名规范**: 正确 vs 错误示例、JSON Schema 对比
4. **FastMCP 配置规范**: 标准配置和命名规范
5. **Dockerfile 规范**: 健康检查、依赖版本、启动命令
6. **包结构规范**: 目录结构和 pyproject.toml
7. **测试与验证**: 本地测试流程和验证清单
8. **常见问题与解决方案**: Q&A 和排查指南
9. **参考示例**: 成功案例和相关文档

**阅读时间**: 30 分钟

---

### 3. 开发检查清单

**文件**: `MCP_SERVER_开发检查清单.md`
**用途**: 从设计到部署的完整检查清单
**适合**:
- 确保开发过程不遗漏任何步骤
- 作为 Code Review 的参考
- 部署前的最终验证

**包含内容**:
- **阶段 1**: 设计与规划（命名、工具设计）
- **阶段 2**: 代码开发（函数签名、参数描述、FastMCP 配置）
- **阶段 3**: Dockerfile 配置（依赖版本、健康检查、启动命令）
- **阶段 4**: 包结构（目录结构、pyproject.toml）
- **阶段 5**: 本地测试（构建、启动、验证）
- **阶段 6**: 部署准备（ECR 推送、文档）
- **阶段 7**: AgentCore Runtime 部署（Runtime 更新、Gateway 刷新）
- **阶段 8**: 生产验证（性能、错误处理、监控）

**总计检查项**: 100+
**使用时间**: 30-60 分钟（取决于项目复杂度）

---

## 🎯 核心要点总结

### ⚠️ 必须遵守的规范（P0）

1. **工具函数签名**
   - ✅ 使用简单类型（`str`, `int`, `bool`, `list`, `dict`）
   - ✅ 使用 `Annotated[type, Field(description=...)]`
   - ❌ 禁止复杂 Pydantic 模型参数
   - ❌ 禁止嵌套对象

2. **FastMCP 配置**
   - ✅ `name` 使用 `awslabs.*` 格式
   - ✅ `host="0.0.0.0"`, `port=8000`
   - ✅ `stateless_http=True`

3. **Dockerfile 健康检查**
   - ✅ 使用进程存活检查
   - ❌ 禁止 `GET /mcp`（POST-only 端点）

4. **依赖版本**
   - ✅ `pydantic>=2.11.0`
   - ✅ `mcp[cli]==1.23.3`
   - ✅ 所有依赖使用精确版本

---

## 📊 使用流程

### 开发新 MCP Server 的推荐流程

```
1. 阅读快速参考指南（5 分钟）
   ↓
2. 参考 cloudtrail-mcp-server 或 costq-risp-mcp-server 作为模板
   ↓
3. 设计工具函数（参考开发规范第 3 章）
   ↓
4. 实现代码（使用快速参考中的模板）
   ↓
5. 配置 Dockerfile（参考开发规范第 5 章）
   ↓
6. 本地测试（参考开发规范第 7 章）
   ↓
7. 使用检查清单逐项验证
   ↓
8. 部署到 AgentCore Runtime
   ↓
9. 生产验证
```

---

## 🔍 常见问题快速查找

| 问题 | 查找位置 |
|------|---------|
| 工具注册失败（7ms 错误） | 快速参考 → 常见错误速查 |
| 容器 unhealthy | 开发规范 → Q&A → Q2 |
| 依赖冲突 | 开发规范 → Q&A → Q3 |
| JSON Schema 嵌套对象 | 开发规范 → 工具函数签名规范 |
| 如何迁移旧代码 | 开发规范 → Q&A → Q5 |
| 本地测试步骤 | 开发规范 → 测试与验证 |
| 部署验证清单 | 开发检查清单 → 阶段 7-8 |

---

## 📖 参考示例

### 成功案例

1. **CloudTrail MCP Server**
   - 位置: `src/cloudtrail-mcp-server/`
   - 特点: AWS 官方 MCP，标准参考实现
   - 推荐用途: 学习标准结构和配置

2. **RISP MCP Server**
   - 位置: `src/costq-risp-mcp-server/`
   - 特点: 完整的改造案例，13 个工具
   - 推荐用途: 学习复杂工具的实现

### 修复案例文档

- **根因诊断**: `20260119_risp_mcp问题/20260119_final_diagnosis.md`
- **修复报告**: `20260119_risp_mcp问题/20260120_修复完成报告.md`
- **测试报告**: `20260119_risp_mcp问题/20260120_本地测试报告.md`

---

## 🔗 相关资源

### 官方文档

- [MCP 协议规范](https://spec.modelcontextprotocol.io/)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [AWS AgentCore Runtime 文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html)
- [Pydantic 文档](https://docs.pydantic.dev/)

### 内部文档

- DEEPV.md（项目执行规范）
- CODING_STANDARDS.md（编码标准）

---

## 💡 最佳实践

### 开发前

1. ✅ 阅读快速参考指南
2. ✅ 参考成功案例（CloudTrail 或 RISP）
3. ✅ 明确工具功能和参数

### 开发中

1. ✅ 使用简单类型参数（避免 Pydantic 模型）
2. ✅ 添加完整的参数描述
3. ✅ 遵循命名规范
4. ✅ 锁定依赖版本

### 开发后

1. ✅ 本地容器测试
2. ✅ 验证 JSON Schema 格式
3. ✅ 使用检查清单逐项确认
4. ✅ 部署前预验证

---

## 🚀 快速开始模板

```bash
# 1. 复制模板
cp -r src/cloudtrail-mcp-server src/your-new-mcp-server

# 2. 修改配置
cd src/your-new-mcp-server
# 编辑 server.py, pyproject.toml, Dockerfile

# 3. 实现工具函数
# 使用快速参考中的模板

# 4. 本地测试
docker build -f Dockerfile-AgentCore-Runtime -t your-mcp:test .
docker run -d --name test-mcp -p 8000:8000 your-mcp:test
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# 5. 使用检查清单验证
# 参考 MCP_SERVER_开发检查清单.md

# 6. 部署
bash costq/scripts/build_and_push_template.sh your-new-mcp-server
```

---

## 📝 文档维护

### 更新历史

| 版本 | 日期 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-01-20 | 初始版本，基于 RISP MCP 改造经验 | DeepV Code AI |

### 反馈与改进

如果发现文档问题或有改进建议，请：
1. 创建 Issue 记录问题
2. 提交 Pull Request 改进文档
3. 联系文档维护者

---

## ✅ 文档使用检查

开始开发前，请确认：

- [ ] 已阅读快速参考指南
- [ ] 已了解核心规范（特别是 P0 级别）
- [ ] 已参考成功案例
- [ ] 已准备好检查清单

开发过程中：

- [ ] 遵循工具函数签名规范
- [ ] 遵循 FastMCP 配置规范
- [ ] 遵循 Dockerfile 规范
- [ ] 定期参考检查清单

部署前：

- [ ] 完成本地测试
- [ ] 使用检查清单逐项验证
- [ ] 所有关键检查项通过
- [ ] 文档已更新

---

**文档维护者**: DeepV Code AI Assistant
**最后更新**: 2026-01-20
**版本**: v1.0
**基于项目**: CostQ RISP MCP Server 改造经验

**联系方式**:
- 文档位置: `costq/docs/`
- 问题反馈: GitHub Issues
- 技术支持: CostQ 开发团队
