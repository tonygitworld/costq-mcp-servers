# 执行规范

- 当我说“提交到git”、“推送到git”、“提交并推送到git”、“提交”等指令时，提交并推送本地代码到git仓库
- 严禁在没有得到我的明确指示的情况下，修改任何代码
- 严谨的对待工作，不能靠推测，分析问题要有理有据，实事求事，不确定的问题联网搜索解决方案或者和我确认
- 在任何地方的命名使用costq，而不是strands-agent-demo相关的文字
- 按照程序编码最佳实践修改代码，确保没有冗余逻辑，简单问题不复杂化，不侵入任何现有逻辑，不影响现有代码功能，避免过度设计。
- 如果必须要修改现有的逻辑要和我说明潜在影响并和我沟通
- 每次修改后必须按照编程最佳实践立即语法、缩进、代码逻辑等检查
- Always use Context7 MCP when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.
- Always use semgrep MCP to scan code for security vulnerabilities.


# 文档规范

- 将需求文档、任务文档、临时文档、测试脚本等临时文件创建到 costq/docs/ 目录下，需要在 costq/docs/ 下创建和主题相应的以日期戳开头的子目录如：“20261121_流式输出功能”


# 编码规范

- 编程规范参考 CODING_STANDARDS.md
- 零侵入性原则：仅修改目标代码，不改变业务逻辑和函数签名，完美隔离不影响现有功能
- 分步执行验证：将大型重构拆分为独立阶段（Phase 1/2/3），每个阶段都可以独立验证和回滚
- 避免过度设计："少即是多"，使用最简单的方案，避免双重系统和冗余代码
- 基于实际代码而非假设：必须实际验证代码，不要基于猜测分析（如MCP预热机制分析教训）
- 保持谦虚验证假设：要联网搜索验证假设，采纳最佳方案
- 完整验证流程：每步都要验证，代码级验证+部署后验证+功能验证+安全验证
- 详细的执行计划和Checklist：清晰的步骤、预期输出、验证点，失败可快速定位
- 代码批量修改的教训：不要使用sed直接修改文件，因为sed无法精确控制插入位置且容易出错。更好的方案是使用Python脚本先生成diff预览，手动审查确认后再应用修改。loguru迁移到logging时必须检查的特有语法包括：logger.opt(exception=True)要改为exc_info=True、logger.bind()要改为extra={}参数、logger.catch()装饰器要改为标准异常处理。
- 凡是在方案、编码过程遇到任何争议或不确定，必须在第一时间主动告知我由我做决策。
- 对于需要补充的信息，即使向我询问，而不是直接应用修改。
- 每次改动基于最小范围修改原则。


# AWS 命令行调试程序使用的参数

## 通用参数

- ** Profile: 3532 **
- ** Region: ap-northeast-1 **

## agentcore cli

使用命令：aws bedrock-agentcore-control

## 数据库连接通过 Secret Manager 获取:

- 本地开发环境连接的是云上的 dev 数据库，连接信息存储在 costq/rds/postgresql-dev 密钥中，在本地环境即可连接。
- 生产环境连接的是云上的 prod 数据库，连接信息存储在 costq/rds/postgresql 密钥中，**需要登录到 EKS Pod 内执行**。

## 生产环境前端和fastapi部署资源情况：

- EKS 集群：costq-eks-cluster
- namespace: costq-fastapi
- Pod: costq-fastapi

## CostQ MCP 项目 costq/scripts 目录包含部署脚本

当前只构建镜像并上传到 ECR，之后需要手动更新 Runtime，**务必记得刷新 Gateway**


# Git 仓库同步操作规范：

1. 仓库信息：costq-mcp-servers 是从 awslabs/mcp fork 的项目
2. Remote 配置：origin = tonygitworld/costq-mcp-servers (自己的 fork)，upstream = awslabs/mcp.git (原始仓库)
3. 同步 upstream 标准流程：
   - 第一步：git fetch upstream（安全下载，不自动合并）
   - 第二步：git log --oneline HEAD..upstream/main（查看更新）
   - 第三步：git diff HEAD..upstream/main（查看具体改动）
   - 第四步：git rebase upstream/main（推荐）或 git merge upstream/main
   - 第五步：解决冲突（如果有）
   - 第六步：git push origin main（推送到自己的 fork）
4. 提交代码规范：当用户说"提交到git"、"推送到git"、"提交并推送到git"时，执行 git add . && git commit -m "..." && git push origin main
5. 开发分支策略：在 main 分支直接开发（已确认），除非显示说明创建分支。
6. 重要原则：永远先用 git fetch upstream 查看，不直接使用 git pull upstream，确保可控和安全
