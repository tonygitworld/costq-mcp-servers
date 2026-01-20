# CostQ Agent - AgentCore Runtime 部署

将 CostQ Agent 部署到 AWS Bedrock AgentCore Runtime。

---

## 📁 目录结构

```
deployment/agentcore/
├── Dockerfile               # Docker 镜像构建配置
├── requirements.txt         # Python 依赖
├── 01-build_and_push.sh       # 构建和推送脚本
├── test_agent.py           # Agent 测试脚本
├── test_simple.py          # 简单测试脚本
├── TEST.md                 # 测试说明文档
└── README.md               # 本文档

backend/agent/
└── agent_runtime.py        # AgentCore Runtime 入口文件
```

---

## 🚀 快速部署

### 1. 构建并推送镜像

```bash
cd deployment/agentcore
./01-build_and_push.sh
```

脚本会：
- ✅ 登录到 ECR
- ✅ 构建 ARM64 Docker 镜像
- ✅ 推送到 ECR（使用时间戳标签）

### 2. 更新 AgentCore Runtime

在 AWS Console 中：
1. 进入 Bedrock AgentCore
2. 找到 Runtime: `costq_agent`
3. 更新 Container Image URI 为脚本输出的镜像 URI
4. 保存更改

### 3. 测试

```bash
python test_simple.py
```

---

## 📦 镜像构建说明

### 构建上下文

- **构建目录**: 项目根目录（`/Users/.../strands-agent-demo/`）
- **Dockerfile 位置**: `deployment/agentcore/Dockerfile`
- **排除文件**: 使用 `.dockerignore` 排除不必要的文件

### 镜像内容

镜像包含：
- ✅ `backend/` - 完整的后端代码
- ✅ `config/` - 配置文件
- ✅ Python 依赖（从 `requirements.txt`）

镜像**不包含**（通过 `.dockerignore` 排除）：
- ❌ `docs/`, `外部项目研究/` - 文档和研究资料
- ❌ `frontend/`, `node_modules/` - 前端代码
- ❌ `.git/`, `.vscode/` - 开发工具
- ❌ `deployment/k8s`, `deployment/scripts` - 其他部署文件

### 镜像标签策略

- **标签格式**: `v{日期}-{时间}` (例如: `v20251204-021318`)
- **不可变**: ECR 仓库设置为 immutable，每次推送使用新标签
- **查看镜像**:
  ```bash
  aws ecr describe-images \
    --repository-name costq-agentcore \
    --region ap-northeast-1 \
    --profile 3532
  ```

---

## 🧪 本地测试

### 方式1: 直接运行 Runtime

```bash
source venv/bin/activate
python -m backend.agent.agent_runtime --port 8080
```

然后在另一个终端测试：
```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?"}'
```

### 方式2: 测试已部署的 Runtime

```bash
cd deployment/agentcore
python test_simple.py
```

---

## 🔍 故障排查

### 问题1: ModuleNotFoundError: No module named 'backend'

**原因**: Docker 镜像没有包含 `backend` 目录

**解决**:
1. 检查 `.dockerignore` 是否正确
2. 确保 `build_and_push.sh` 从项目根目录构建
3. 重新构建并推送镜像

### 问题2: Tag already exists (immutable)

**原因**: ECR 仓库设置为 immutable，不能覆盖已存在的标签

**解决**:
- ✅ 已修复：`build_and_push.sh` 自动使用时间戳标签
- 每次构建都会生成新的唯一标签

### 问题3: 推送镜像很慢

**原因**: Docker daemon 可能有问题，或网络问题

**解决**:
1. 清理 Docker: `docker system prune -af --volumes`
2. 重启 Docker Desktop
3. 检查网络连接

---

## 📝 技术细节

### AgentCore Runtime 架构

```
Client (boto3)
  ↓
AgentCore Runtime (agent_runtime.py)
  ↓
Agent Manager
  ↓
MCP Servers (stdio 子进程)
```

### 入口函数

```python
@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    接收请求 → 创建 MCP 客户端 → 执行 Agent → 返回结果
    """
```

### 环境变量

Agent 运行时使用的环境变量：
- `AWS_REGION` - AWS 区域
- `TARGET_ACCOUNT_ID` - 目标 AWS 账号 ID（可选）
- `TARGET_ROLE_NAME` - IAM 角色名称（可选）

---

## 📚 相关文档

- [TEST.md](./TEST.md) - 测试说明
- [backend/agent/agent_runtime.py](../../backend/agent/agent_runtime.py) - Runtime 源代码
- [AWS Bedrock AgentCore 文档](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)

---

## 🎯 总结

这个部署方案的特点：
- ✅ **简单**: 一个脚本完成构建和推送
- ✅ **清晰**: 代码结构合理，入口文件在 `backend/agent/`
- ✅ **高效**: 利用 Docker 层缓存，只推送变更的层
- ✅ **安全**: 使用时间戳标签，避免覆盖问题
