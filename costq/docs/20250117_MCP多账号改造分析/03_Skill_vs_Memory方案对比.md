# Skill vs Memory 方案对比

> 本文档评估"改造流程标准化"的两种实现方案：Skill 定义 vs 记忆存储

---

## 1. 方案概述

### 方案 A: Skill 定义（推荐）
将改造流程定义为可执行的 Skill，类似于工作流自动化。

### 方案 B: Memory 记忆存储
将改造指南存储为 AI 的长期记忆，通过自然语言检索使用。

---

## 2. 详细对比

| 维度 | Skill 定义 | Memory 记忆存储 | 结论 |
|------|-----------|----------------|------|
| **结构化程度** | ✅ 高度结构化<br>- 明确的输入/输出<br>- 标准化的执行步骤<br>- 类型安全 | ⚠️ 弱结构化<br>- 自然语言描述<br>- 依赖 AI 理解<br>- 执行不确定 | **Skill 胜出** |
| **可执行性** | ✅ 直接可执行<br>- 代码化的步骤<br>- 自动化程度高<br>- 可集成 CI/CD | ❌ 需要 AI 解释<br>- 人工介入<br>- 自动化难度大 | **Skill 胜出** |
| **一致性** | ✅ 100% 一致<br>- 相同输入 → 相同输出<br>- 可重复验证 | ⚠️ 不确定<br>- 依赖 AI 模型<br>- 可能有误差 | **Skill 胜出** |
| **维护成本** | ✅ 低<br>- 集中管理<br>- 版本控制<br>- 单点更新 | ⚠️ 中等<br>- 分散存储<br>- 需要重新训练/更新 | **Skill 胜出** |
| **学习曲线** | ⚠️ 中等<br>- 需要编写 Skill 脚本<br>- 需要理解框架 | ✅ 低<br>- 自然语言<br>- 易于理解 | **Memory 略胜** |
| **扩展性** | ✅ 强<br>- 模块化设计<br>- 可组合<br>- 可参数化 | ⚠️ 弱<br>- 难以组合<br>- 依赖上下文 | **Skill 胜出** |
| **错误处理** | ✅ 完善<br>- 明确的异常类型<br>- 可预期的回滚 | ⚠️ 弱<br>- 依赖 AI 判断<br>- 不可预期 | **Skill 胜出** |
| **版本管理** | ✅ 原生支持<br>- Git 版本控制<br>- 可追溯历史 | ⚠️ 困难<br>- Memory 更新不透明 | **Skill 胜出** |
| **调试能力** | ✅ 强<br>- 可设置断点<br>- 详细日志<br>- 单步执行 | ❌ 弱<br>- 黑盒执行<br>- 难以定位问题 | **Skill 胜出** |
| **适用场景** | ✅ 标准化流程<br>- 批量操作<br>- 自动化改造 | ✅ 知识库<br>- 指导文档<br>- 人工参考 | **各有所长** |

---

## 3. 具体实现对比

### 3.1 Skill 定义方案

#### 示例：MCP Server 改造 Skill
```python
# skills/mcp_account_context_migration.py
from typing import List, Dict, Any
from pathlib import Path

class MCPAccountContextMigrationSkill:
    """MCP Server 多账号改造 Skill

    自动化完成以下任务：
    1. 复制凭证提取服务层
    2. 创建统一入口
    3. 修改所有 tool 函数
    4. 添加异常处理
    5. 运行测试验证
    """

    def __init__(self, mcp_server_path: Path):
        self.mcp_server_path = mcp_server_path
        self.reference_server = Path("src/billing-cost-management-mcp-server")

    async def execute(self) -> Dict[str, Any]:
        """执行改造流程"""
        results = {
            "steps_completed": [],
            "errors": [],
            "warnings": []
        }

        try:
            # Step 1: 复制凭证提取服务
            await self._copy_cred_services()
            results["steps_completed"].append("cred_services_copied")

            # Step 2: 创建 entrypoint.py
            await self._create_entrypoint()
            results["steps_completed"].append("entrypoint_created")

            # Step 3: 修改 tool 函数
            modified_tools = await self._modify_tools()
            results["steps_completed"].append(f"modified_{len(modified_tools)}_tools")
            results["modified_files"] = modified_tools

            # Step 4: 运行测试
            test_results = await self._run_tests()
            results["test_results"] = test_results

            # Step 5: 生成报告
            report = await self._generate_report(results)
            results["report_path"] = report

            results["status"] = "success"

        except Exception as e:
            results["status"] = "failed"
            results["errors"].append(str(e))

        return results

    async def _copy_cred_services(self):
        """复制凭证提取服务层"""
        import shutil

        source = self.reference_server / "cred_extract_services"
        target = self.mcp_server_path / "cred_extract_services"

        if target.exists():
            raise FileExistsError(f"Directory already exists: {target}")

        shutil.copytree(source, target)
        print(f"✅ Copied cred_extract_services to {target}")

    async def _create_entrypoint(self):
        """创建 entrypoint.py"""
        template = self.reference_server / "entrypoint.py"
        target = self.mcp_server_path / "entrypoint.py"

        if target.exists():
            raise FileExistsError(f"File already exists: {target}")

        # 读取模板并替换包名
        content = template.read_text()
        package_name = self._get_package_name()
        content = content.replace(
            "billing_cost_management_mcp_server",
            package_name
        )

        target.write_text(content)
        print(f"✅ Created entrypoint.py")

    async def _modify_tools(self) -> List[Path]:
        """修改所有 tool 函数"""
        import re

        tools_dir = self.mcp_server_path / "awslabs" / self._get_package_name() / "tools"
        modified_files = []

        for tool_file in tools_dir.glob("*_tools.py"):
            if self._modify_tool_file(tool_file):
                modified_files.append(tool_file)
                print(f"✅ Modified {tool_file.name}")

        return modified_files

    def _modify_tool_file(self, file_path: Path) -> bool:
        """修改单个 tool 文件"""
        content = file_path.read_text()

        # 1. 添加导入
        if "from entrypoint import" not in content:
            import_block = """
# Import account context exceptions
from entrypoint import (
    AccountNotFoundError,
    CredentialDecryptionError,
    AssumeRoleError,
    DatabaseConnectionError,
)
"""
            content = self._add_imports(content, import_block)

        # 2. 修改函数签名
        content = self._add_account_id_param(content)

        # 3. 添加账号上下文初始化
        content = self._add_context_init(content)

        # 4. 添加异常处理
        content = self._add_exception_handling(content)

        # 保存修改
        file_path.write_text(content)
        return True

    async def _run_tests(self) -> Dict[str, Any]:
        """运行测试"""
        import subprocess

        result = subprocess.run(
            ["pytest", "-v", str(self.mcp_server_path / "tests")],
            capture_output=True,
            text=True
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0
        }

    async def _generate_report(self, results: Dict[str, Any]) -> Path:
        """生成改造报告"""
        report_path = self.mcp_server_path / "MIGRATION_REPORT.md"

        report_content = f"""# MCP Server 多账号改造报告

## 改造日期
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 改造路径
{self.mcp_server_path}

## 完成步骤
{chr(10).join(f'- {step}' for step in results["steps_completed"])}

## 修改文件
{chr(10).join(f'- {file}' for file in results.get("modified_files", []))}

## 测试结果
- 状态: {"✅ PASSED" if results.get("test_results", {}).get("passed") else "❌ FAILED"}
- 退出码: {results.get("test_results", {}).get("returncode")}

## 错误/警告
{chr(10).join(f'- {error}' for error in results.get("errors", [])) or '无'}

## 下一步
1. 人工审查所有修改的文件
2. 运行完整的集成测试
3. 更新文档
4. 提交代码到 Git
"""
        report_path.write_text(report_content)
        return report_path

    def _get_package_name(self) -> str:
        """获取包名"""
        # 从 pyproject.toml 或目录结构推断
        pyproject = self.mcp_server_path / "pyproject.toml"
        if pyproject.exists():
            import tomli
            with open(pyproject, 'rb') as f:
                config = tomli.load(f)
                return config["project"]["name"].replace("-", "_")

        # 回退：从目录名推断
        return self.mcp_server_path.name.replace("-", "_")

# 使用示例
async def main():
    skill = MCPAccountContextMigrationSkill(
        mcp_server_path=Path("src/new-mcp-server")
    )
    results = await skill.execute()
    print(f"Migration {'succeeded' if results['status'] == 'success' else 'failed'}")
    print(f"Report: {results.get('report_path')}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**优点**：
✅ 完全自动化
✅ 可重复执行
✅ 详细的错误处理
✅ 自动生成报告
✅ 可集成 CI/CD

**缺点**：
⚠️ 需要编写和维护 Skill 代码
⚠️ 初始开发成本较高

---

### 3.2 Memory 记忆存储方案

#### 示例：Memory 记忆
```python
from save_memory import save_memory

# 保存改造指南到 AI 记忆
await save_memory("""
MCP Server 多账号改造流程：

1. 复制 cred_extract_services 目录
   - 从 billing-cost-management-mcp-server 复制
   - 包含 7 个模块：__init__.py, aws_client.py, context_manager.py,
     credential_extractor.py, crypto.py, database.py, exceptions.py

2. 创建 entrypoint.py
   - 定义 _setup_account_context 函数
   - 实现 main() 函数启动 MCP Server
   - 导出异常类

3. 修改所有 tool 函数
   - 新增参数：target_account_id: Optional[str] = None
   - 添加账号上下文初始化代码
   - 添加异常处理（5 种异常）

4. 运行测试验证
   - 单元测试
   - 集成测试
   - 手动验证清单

详细步骤参考：costq/docs/20250117_MCP多账号改造分析/02_改造步骤指南.md
""")

# AI 使用记忆
# 用户：请帮我改造 new-mcp-server
# AI：根据记忆回忆改造流程，然后逐步执行
```

**优点**：
✅ 易于更新
✅ 自然语言描述
✅ 无需编写代码

**缺点**：
❌ 需要 AI 解释执行
❌ 不可重复（每次可能不同）
❌ 难以自动化
❌ 容易遗漏步骤
❌ 无法版本控制

---

## 4. 混合方案（最佳实践）

### 推荐：Skill + Memory 结合
```
┌─────────────────┐
│  Skill 定义     │  ← 自动化执行（核心流程）
│  (可执行代码)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Memory 记忆    │  ← 知识库/指南（辅助参考）
│  (自然语言)     │
└─────────────────┘
```

### 实现方式
1. **Skill 定义**：实现核心自动化流程
   - 文件复制
   - 代码模板生成
   - 批量修改
   - 测试验证

2. **Memory 记忆**：存储辅助信息
   - 设计原则
   - 常见问题排查
   - 最佳实践
   - 历史经验

### 使用流程
```
用户: 请改造 new-mcp-server

AI (查询 Memory):
  - 回忆改造原则和注意事项
  - 检索常见问题

AI (调用 Skill):
  - 执行自动化改造
  - 生成改造报告

AI (结合 Memory):
  - 检查改造结果
  - 提供额外建议
  - 输出完整报告
```

---

## 5. 最终建议

### 5.1 短期方案（立即可用）
**使用 Memory + 手工改造**
```bash
# 1. 保存改造指南到 Memory
save_memory("MCP Server 改造流程：...")

# 2. AI 辅助手工改造
# 用户：请帮我改造 new-mcp-server
# AI 根据 Memory 指导用户逐步操作
```

**优点**：
- 立即可用
- 无需额外开发
- 灵活性高

**缺点**：
- 需要人工介入
- 容易出错
- 效率较低

---

### 5.2 中期方案（推荐）
**开发 Skill 自动化**
```bash
# 1. 开发 Skill
vim skills/mcp_account_context_migration.py

# 2. 使用 Skill
python skills/mcp_account_context_migration.py --target src/new-mcp-server

# 3. 人工审查
git diff

# 4. 提交
git commit -m "feat: add multi-account support"
```

**优点**：
- 高度自动化
- 可重复执行
- 一致性强
- 易于维护

**缺点**：
- 需要开发时间（估计 1-2 天）

---

### 5.3 长期方案（未来优化）
**Skill + Memory + CI/CD 集成**
```yaml
# .github/workflows/mcp-migration.yml
name: MCP Migration

on:
  workflow_dispatch:
    inputs:
      mcp_server_path:
        description: 'MCP Server Path'
        required: true

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Migration Skill
        run: |
          python skills/mcp_account_context_migration.py \
            --target ${{ github.event.inputs.mcp_server_path }}

      - name: Run Tests
        run: pytest ${{ github.event.inputs.mcp_server_path }}/tests

      - name: Create PR
        uses: peter-evans/create-pull-request@v5
        with:
          commit-message: "feat: add multi-account support"
          title: "[Auto] MCP Migration: ${{ github.event.inputs.mcp_server_path }}"
          body: |
            自动化改造报告：
            - Skill: mcp_account_context_migration
            - Target: ${{ github.event.inputs.mcp_server_path }}

            请人工审查所有修改。
```

**优点**：
- 完全自动化
- 可追溯
- 团队协作友好
- 持续改进

---

## 6. 行动计划

### Phase 1: 立即行动（本周）
- [ ] 将改造指南保存到 Memory
- [ ] 使用 Memory 指导手工改造 1-2 个 MCP Server
- [ ] 收集问题和经验

### Phase 2: 自动化开发（下周）
- [ ] 开发基础 Skill（文件复制、模板生成）
- [ ] 测试 Skill 可用性
- [ ] 优化 Skill 功能

### Phase 3: 全面推广（2 周后）
- [ ] 使用 Skill 改造所有 MCP Servers
- [ ] 文档更新
- [ ] 团队培训

### Phase 4: 持续优化（长期）
- [ ] 集成 CI/CD
- [ ] 监控和告警
- [ ] 定期回顾和改进

---

## 7. 结论

### 7.1 最终推荐
**采用混合方案：Skill（核心）+ Memory（辅助）**

| 场景 | 使用方案 |
|------|---------|
| 批量改造 | ✅ Skill 自动化 |
| 新 MCP Server | ✅ Skill 自动化 |
| 故障排查 | ✅ Memory 查询 |
| 知识沉淀 | ✅ Memory 存储 |
| 团队协作 | ✅ Skill + Git |

### 7.2 投资回报分析
**开发 Skill 的成本**：
- 初始开发：1-2 天
- 维护成本：每月 1-2 小时

**收益**：
- 改造 1 个 MCP Server：从 4 小时 → 10 分钟（节省 ~95%）
- 减少错误率：从 ~20% → <5%
- 提高一致性：100%

**ROI 计算**：
- 改造 10 个 MCP Server → 节省 ~35 小时
- 投资回报周期：<1 周

### 7.3 风险评估
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Skill 开发失败 | 低 | 中 | 回退到 Memory 方案 |
| 自动化引入 Bug | 中 | 高 | 人工审查 + 完善测试 |
| 维护成本高 | 低 | 中 | 文档化 + 模块化 |

**结论**：风险可控，收益显著，**强烈推荐开发 Skill**。
