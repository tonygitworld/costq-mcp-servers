# 🧩 CostQ 项目编码规范与最佳实践

> **适用范围**: CostQ AWS成本分析助手项目
> **版本**: v2.1.0
> **更新日期**: 2025-12-28
> **维护者**: 全栈工程团队

一份适用于团队协作、代码审查与工程质量提升的统一规范。

**🔧 核心原则：规范可执行、代码可验证、安全零容忍**

---

## 🆕 v2.1.0 更新说明（2025-12-28）

**重大变更**：全面迁移到标准 Python logging

1. **日志规范更新**（2.3节）
   - ✅ 使用标准 `import logging`
   - ✅ Logger 定义在模块顶层：`logger = logging.getLogger(__name__)`
   - ✅ 异常处理使用 `exc_info=True`
   - ❌ 禁止使用 loguru（已废弃）

2. **导入清单更新**（附录A）
   - 移除 `from loguru import logger`
   - 添加 `import logging`
   - 添加 `logger = logging.getLogger(__name__)` 示例

3. **异常处理规范更新**（1.6节）
   - 使用 `logger.error(..., exc_info=True)` 代替 `logger.opt(exception=True)`

4. **参考资源更新**
   - 移除 Loguru 文档
   - 添加 Python Logging 官方文档

---

## 📌 目录

- [一、Python 编程规范](#一python-编程规范)
  - [1.1 命名规范](#11-命名规范)
  - [1.2 代码格式](#12-代码格式)
  - [1.3 导入规范](#13-导入规范)
  - [1.4 类型注解规范](#14-类型注解规范)
  - [1.5 文档与注释规范](#15-文档与注释规范)
  - [1.6 异常处理规范](#16-异常处理规范)
  - [1.7 Pythonic 编程风格](#17-pythonic-编程风格)
- [二、项目特定规范](#二项目特定规范)
  - [2.1 数据库操作规范](#21-数据库操作规范)
  - [2.2 异步编程规范](#22-异步编程规范)
  - [2.3 日志规范](#23-日志规范)
  - [2.4 安全规范](#24-安全规范)
  - [2.5 性能优化规范](#25-性能优化规范)
  - [2.6 MCP 服务器开发规范](#26-mcp-服务器开发规范)
- [三、通用最佳实践](#三通用最佳实践)
  - [3.1 代码可读性优先](#31-代码可读性优先)
  - [3.2 单一职责原则](#32-单一职责原则)
  - [3.3 DRY 原则](#33-dry-原则)
  - [3.4 可测试性设计](#34-可测试性设计)
  - [3.5 错误处理最佳实践](#35-错误处理最佳实践)
- [四、Git 提交规范](#四git-提交规范)
  - [4.1 提交信息格式](#41-提交信息格式)
  - [4.2 分支命名规范](#42-分支命名规范)
- [五、文档规范](#五文档规范)
  - [5.1 代码文档要求](#51-代码文档要求)
  - [5.2 项目文档管理](#52-项目文档管理)
- [六、部署与发布规范](#六部署与发布规范)
- [附录 A：常用导入清单](#附录-a常用导入清单)

---

## 一、Python 编程规范

### 1.1 命名规范

| 类型 | 命名方式 | 示例 |
|------|----------|------|
| 变量、函数、方法名 | `lower_case_with_underscores` | `get_user_info()` |
| 类名 | `CamelCase` | `DynamicAgentManager` |
| 常量 | `UPPER_CASE_WITH_UNDERSCORES` | `MAX_RETRIES = 3` |
| 模块名 | 全小写，可包含下划线 | `alert_scheduler.py` |
| 包名 | 全小写，不推荐下划线 | `backend.services` |
| 私有变量/方法 | 单下划线开头 | `_internal_method()` |
| 全局单例 | 下划线开头 | `_dynamic_agent_manager` |

**示例**：

```python
# ✅ 正确
MAX_RETRIES = 3
_global_instance = None

class AlertScheduler:
    def __init__(self):
        self._initialized = False

    def start(self) -> None:
        """启动调度器"""
        pass

    def _internal_check(self) -> bool:
        """内部检查方法（私有）"""
        return True

# ❌ 错误
maxRetries = 3  # 应该用大写
class alertScheduler:  # 类名应该用驼峰
    pass
```

---

### 1.2 代码格式

**基本原则**：
- 每行 **≤ 100 字符**（本项目标准，比 PEP-8 的 79 字符更宽松）
- 使用 **4 个空格**缩进（禁止使用 Tab）
- 类、顶层函数之间空 **2 行**
- 方法之间空 **1 行**
- 函数内部逻辑块之间空 **1 行**
- 运算符两侧增加空格（如 `a + b`）

**示例**：

```python
# ✅ 正确
from typing import Optional


class UserService:
    """用户服务类"""

    def __init__(self):
        self.cache = {}

    def get_user(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        if user_id in self.cache:
            return self.cache[user_id]

        user = self._fetch_from_db(user_id)
        self.cache[user_id] = user
        return user

    def _fetch_from_db(self, user_id: str) -> dict:
        """从数据库获取用户"""
        # 实现细节
        pass


def standalone_function():
    """独立函数"""
    pass
```

---

### 1.3 导入规范

**导入顺序**（组之间空 1 行）：
1. 标准库
2. 第三方库
3. 本地模块（从通用到具体）

**示例**（完整导入示例，见[附录A](#附录-a常用导入清单)）：

```python
# ✅ 正确
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException
from loguru import logger
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import Session, relationship

from backend.config.settings import settings
from backend.database import SessionLocal
from backend.models.user import User
from backend.services.alert_scheduler import AlertScheduler


# ❌ 错误
from backend.models.user import User  # 本地导入应该放最后
import os
from fastapi import FastAPI
import sys  # 标准库应该分组放在一起
```

**禁止事项**：
```python
# ❌ 绝对禁止使用通配符导入
from module import *

# ✅ 使用明确的导入
from module import func1, func2, ClassName
```

---

### 1.4 类型注解规范

**原则**：
- **所有公共接口**必须添加类型注解
- 使用 Python 3.9+ 的新式类型注解（`list[str]` 而非 `List[str]`）
- 复杂类型使用 `typing` 模块

**示例**：

```python
from typing import Optional, Dict, List, Any, ClassVar
from datetime import datetime

# ✅ 正确
class DynamicAgentManager:
    """动态 Agent 管理器

    为每个账号创建并缓存独立的 Agent
    """

    # 类级别类型注解
    _shared_bedrock_model: ClassVar[Optional[BedrockModel]] = None

    def __init__(self, system_prompt: str, model_id: str = None):
        self.system_prompt = system_prompt
        self.model_id = model_id
        self._agents_cache: Dict[tuple, Agent] = {}

    def get_or_create_agent(
        self,
        user_id: str,
        account_id: str,
        mcp_clients: Dict[str, MCPClient],
        session_id: Optional[str] = None
    ) -> Agent:
        """获取或创建 Agent

        Args:
            user_id: 用户 ID
            account_id: 账号 ID
            mcp_clients: MCP 客户端字典
            session_id: 会话 ID（可选）

        Returns:
            Agent: Agent 实例
        """
        cache_key = (user_id, account_id, session_id) if session_id else (user_id, account_id)

        if cache_key in self._agents_cache:
            return self._agents_cache[cache_key]

        agent = self.create_agent_for_account(account_id, mcp_clients)
        self._agents_cache[cache_key] = agent
        return agent
```

---

### 1.5 文档与注释规范

#### Docstring 规范

**格式**: Google Style（项目统一标准）

**示例**：

```python
def execute_alert(
    alert_id: str,
    account_info: dict,
    retry_count: int = 0
) -> dict:
    """执行单个告警检查

    使用 AlertAgentManager 执行告警查询，支持失败重试。

    Args:
        alert_id: 告警配置 ID
        account_info: 账号信息字典
            - account_id: AWS 账号 ID
            - credentials: 凭证信息
        retry_count: 当前重试次数（默认0）

    Returns:
        dict: 执行结果
            - success: 是否成功（bool）
            - triggered: 是否触发告警（bool）
            - message: 结果消息（str）
            - error: 错误信息（可选，str）

    Raises:
        ValueError: 如果 alert_id 无效
        RuntimeError: 如果重试次数超过上限

    Examples:
        >>> result = execute_alert("alert-123", {"account_id": "123456789012"})
        >>> print(result["success"])
        True

    Notes:
        - 失败时会自动重试，最多3次
        - 使用指数退避策略（2^retry_count 秒）
    """
    if retry_count > MAX_RETRIES:
        raise RuntimeError(f"重试次数超过上限: {MAX_RETRIES}")

    # 实现细节...
```

#### 注释规范

**原则**：
- 注释解释 **"为什么"**，而不是 **"做了什么"**
- 复杂逻辑必须添加注释
- 使用中文注释（项目团队为中文母语）
- 重要的设计决策需要注释说明

**示例**：

```python
# ✅ 正确：解释为什么这样做
# 使用类级别单例BedrockModel，避免重复初始化导致的内存浪费和启动延迟
_shared_bedrock_model: ClassVar[Optional[BedrockModel]] = None

# ✅ 正确：解释业务逻辑
# 双重检查锁定模式 - 避免多线程并发创建多个实例
if cls._shared_bedrock_model is None:
    with cls._model_lock:
        if cls._shared_bedrock_model is None:
            cls._shared_bedrock_model = BedrockModel(model_id=model_id)

# ❌ 错误：重复代码本身表达的内容
# 创建一个列表
my_list = []

# ❌ 错误：过时或错误的注释（比代码更糟糕）
# 返回用户名（实际上返回的是 user_id）
return user.id
```

**特殊注释标记**：

```python
# ✅ 已修复的问题
# ✅ P0: 修复预热机制设计缺陷 - 使用真实账号预热确保缓存可复用

# ⚠️  警告或需要注意的地方
# ⚠️  Memory ID 为 None，跳过 Hooks 集成

# ❌ 错误或禁止的做法
# ❌ 错误：不要使用通配符导入

# 🔍 调试信息（仅开发环境）
# 🔍 调试：记录输入的mcp_clients

# TODO 待办事项
# TODO: 实现更智能的缓存淘汰策略

# FIXME 需要修复的问题
# FIXME: 并发情况下可能存在竞态条件

# NOTE 重要说明
# NOTE: 此处使用同步方法是为了兼容非异步上下文
```

---

### 1.6 异常处理规范

**原则**：
- **禁止使用裸 `except:`**
- 捕获**具体的异常类型**
- 使用 **loguru** 记录异常详情
- 不向用户暴露敏感的内部细节

**示例**：

```python
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ✅ 正确：捕获具体异常，记录详细日志
try:
    result = await some_operation()
except ValueError as e:
    logger.error("参数验证失败: %s", str(e))
    raise HTTPException(status_code=400, detail="无效的参数")
except ConnectionError as e:
    logger.error("数据库连接失败", exc_info=True)
    raise HTTPException(status_code=503, detail="服务暂时不可用")
except Exception as e:
    # 最后的兜底异常处理
    logger.error("未预期的错误", exc_info=True)
    raise HTTPException(status_code=500, detail="内部服务器错误")

# ❌ 错误：裸 except
try:
    result = some_operation()
except:  # 这会捕获所有异常，包括 KeyboardInterrupt
    pass

# ❌ 错误：泄露敏感信息
try:
    db.execute(query)
except Exception as e:
    # 直接返回数据库错误信息给用户
    return {"error": str(e)}  # 可能包含表结构等敏感信息
```

**异常日志记录最佳实践**：

```python
import logging

logger = logging.getLogger(__name__)

# ✅ 使用 exc_info=True 自动记录堆栈
try:
    risky_operation()
except Exception as e:
    logger.error("操作失败", exc_info=True)
    # 自动包含完整的堆栈跟踪
```

---

### 1.7 Pythonic 编程风格

**资源管理**：

```python
# ✅ 使用 with 管理资源
with open('file.txt', 'r') as f:
    content = f.read()

# ✅ 数据库会话管理
from contextlib import contextmanager

@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

with get_db_session() as db:
    user = db.query(User).first()
```

**迭代优化**：

```python
# ✅ 使用 enumerate() 代替 range(len(...))
for i, item in enumerate(items):
    print(f"{i}: {item}")

# ❌ 不推荐
for i in range(len(items)):
    print(f"{i}: {items[i]}")

# ✅ 使用 zip() 简化多变量循环
for name, age in zip(names, ages):
    print(f"{name}: {age}")

# ✅ 字典推导式
user_map = {user.id: user.name for user in users}

# ✅ 列表推导式（简单场景）
squares = [x**2 for x in range(10)]

# ❌ 避免过于复杂的推导式
# 复杂逻辑应该使用普通循环
```

**使用内置方法和标准库**：

```python
# ✅ 使用 any() 和 all()
has_admin = any(user.is_admin for user in users)
all_verified = all(user.verified for user in users)

# ✅ 使用 collections
from collections import defaultdict, Counter

word_count = Counter(words)
groups = defaultdict(list)

# ✅ 使用 itertools
from itertools import chain, groupby

all_items = list(chain(list1, list2, list3))
```

---

## 二、项目特定规范

### 2.1 数据库操作规范

**模型定义**（完整导入示例）：

```python
# ============ 必要导入（参见附录A） ============
from sqlalchemy import Column, String, DateTime, Boolean, Index, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base
from datetime import datetime, timezone
import uuid

class AlertExecutionLog(Base):
    """告警执行日志表

    记录每次告警检查的详细执行过程
    """
    __tablename__ = "alert_execution_logs"

    # ============ 主键 ============
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="执行日志ID"
    )

    # ============ 关联字段 ============
    alert_id = Column(
        String(36),
        ForeignKey('monitoring_configs.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="关联的告警配置ID"
    )

    # ============ 关系定义 ============
    alert_config = relationship("MonitoringConfig", back_populates="execution_logs")

    # ============ 时间戳 ============
    # 所有时间字段必须使用 timezone-aware datetime
    started_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="开始执行时间"
    )

    # ============ 索引 ============
    __table_args__ = (
        Index('idx_execution_log_alert_time', 'alert_id', 'started_at'),
        Index('idx_execution_log_org_time', 'org_id', 'started_at'),
    )
```

---

#### 🔴 关键：同步 vs 异步数据库会话

> **⚠️  严重错误**：在 `async def` 路由中使用同步 `SessionLocal()` 会**阻塞事件循环**，导致性能灾难！

**同步路由（普通函数）**：

```python
from backend.database import SessionLocal
from sqlalchemy.orm import Session
from fastapi import Depends

# ✅ 正确：同步路由使用同步会话
def get_db() -> Session:
    """同步数据库会话依赖（仅用于同步路由）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users/{user_id}")  # 注意：不是 async def
def read_user(user_id: str, db: Session = Depends(get_db)):
    """同步路由示例"""
    user = db.query(User).filter(User.id == user_id).first()
    return user
```

**异步路由（推荐方式）**：

```python
import asyncio
from backend.database import async_session_maker  # 假设已配置 AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends

# ✅ 方案1：使用 AsyncSession（推荐）
async def get_async_db() -> AsyncSession:
    """异步数据库会话依赖（推荐用于异步路由）"""
    async with async_session_maker() as session:
        yield session

@app.get("/users/{user_id}")
async def read_user_async(user_id: str, db: AsyncSession = Depends(get_async_db)):
    """异步路由示例（推荐）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return user

# ✅ 方案2：使用 asyncio.to_thread 包裹同步调用（可接受）
from backend.database import SessionLocal

@app.get("/users/{user_id}")
async def read_user_with_thread(user_id: str):
    """异步路由中使用同步DB（备选方案）"""
    def sync_db_call():
        with SessionLocal() as db:
            return db.query(User).filter(User.id == user_id).first()

    # 在线程池中执行同步调用，避免阻塞事件循环
    user = await asyncio.to_thread(sync_db_call)
    return user

# ❌ 错误：在异步路由中直接使用同步会话
@app.get("/users/{user_id}")
async def read_user_wrong(user_id: str):
    """❌ 严重错误：阻塞事件循环！"""
    with SessionLocal() as db:  # 这会阻塞整个异步事件循环！
        user = db.query(User).filter(User.id == user_id).first()
    return user
```

**AsyncSession 配置示例（`backend/database.py`）**：

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.config.settings import settings

# 异步引擎（使用 asyncpg 驱动）
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,  # postgresql+asyncpg://...
    echo=False,
    pool_size=20,
    max_overflow=10,
)

# 异步会话工厂
async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

---

**时区处理规范**（强化版）：

```python
from datetime import datetime, timezone

# ✅ 正确：始终使用 UTC 时区
now_utc = datetime.now(timezone.utc)

# ✅ 正确：数据库字段类型与代码严格一致
# 如果数据库是 TIMESTAMP WITH TIME ZONE，代码必须使用 datetime.now(timezone.utc)
# 如果数据库是 TIMESTAMP WITHOUT TIME ZONE，代码必须使用 datetime.now()（无时区）

# ⚠️  验证数据库字段类型（不要假设！）
"""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'your_table' AND column_name = 'created_at';
"""

# ❌ 错误：混用带时区和不带时区的 datetime
aware_dt = datetime.now(timezone.utc)     # 带时区
naive_dt = datetime.now()                 # 不带时区
if aware_dt > naive_dt:  # TypeError: can't compare offset-naive and offset-aware datetimes
    pass

# 🔍 调试技巧：打印 datetime 对象的 tzinfo 属性
print(f"aware_dt.tzinfo: {aware_dt.tzinfo}")  # UTC
print(f"naive_dt.tzinfo: {naive_dt.tzinfo}")  # None
```

---

### 2.2 异步编程规范

**异步函数定义**：

```python
import asyncio
from typing import Optional

# ✅ 正确：异步函数使用 async def
async def fetch_user_data(user_id: str) -> Optional[dict]:
    """异步获取用户数据"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/api/users/{user_id}") as response:
            return await response.json()

# ✅ 正确：同步代码在异步上下文中使用 asyncio.to_thread
async def process_with_sync_code():
    # 将同步的 CPU 密集型操作移到线程池
    result = await asyncio.to_thread(sync_heavy_computation, data)
    return result
```

**异步异常处理**：

```python
# ✅ 正确：异步任务的异常处理
async def safe_task_execution():
    tasks = [
        asyncio.create_task(task1()),
        asyncio.create_task(task2()),
        asyncio.create_task(task3()),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"任务 {i} 失败: {result}")
        else:
            logger.info(f"任务 {i} 成功: {result}")
```

**并发控制**：

```python
# ✅ 正确：使用信号量控制并发数
async def execute_with_limit(tasks: list, max_concurrent: int = 5):
    """限制并发数量执行任务"""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_task(task):
        async with semaphore:
            return await task()

    return await asyncio.gather(*[bounded_task(t) for t in tasks])
```

---

### 2.3 日志规范

> **🔴 重要变更**：项目已全面迁移到标准 Python logging，禁止使用 loguru

#### 日志导入和初始化

**✅ 正确做法**：

```python
# 在模块顶层导入 logging
import logging

# 在模块顶层定义 logger（使用模块名）
logger = logging.getLogger(__name__)

# 示例：backend/api/websocket.py
import logging

logger = logging.getLogger(__name__)  # logger 名称: backend.api.websocket


class WebSocketManager:
    def __init__(self):
        logger.info("WebSocket 管理器初始化")
```

**❌ 错误做法**：

```python
# ❌ 禁止使用 loguru
from loguru import logger  # 已废弃，不要使用

# ❌ 禁止在函数内定义 logger
def my_function():
    logger = logging.getLogger(__name__)  # 应该在模块顶层定义
    logger.info("...")

# ❌ 禁止使用其他 logger 名称
logger = logging.getLogger("custom_name")  # 应该使用 __name__
```

---

#### 日志级别使用

```python
import logging
import os

logger = logging.getLogger(__name__)

# 环境判断
IS_PRODUCTION = os.getenv('ENVIRONMENT') == 'production'

# DEBUG: 详细的调试信息（生产环境不输出）
logger.debug(
    "MCP客户端详情 - account_id: %s, client_count: %d",
    account_id, len(mcp_clients)
)

# INFO: 正常业务流程的关键节点
logger.info(
    "Agent创建完成 - account_id: %s, tool_count: %d, session_id: %s",
    account_id, len(all_tools), session_id
)

# WARNING: 警告信息（不影响主流程，但需要关注）
logger.warning(
    "MCP客户端数量变化，重新创建Agent - cached: %d, current: %d",
    cached, current
)

# ERROR: 错误信息（影响功能，但不致命）
logger.error(
    "从MCP服务器加载工具失败 - server_type: %s, error: %s",
    server_type, str(e)
)

# CRITICAL: 严重错误（系统级问题）
logger.critical(
    "数据库连接池耗尽 - pool_size: %d, overflow: %d",
    pool.size, pool.overflow
)
```

---

#### 异常处理规范

**✅ 正确做法**：使用 `exc_info=True` 记录异常堆栈

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = risky_operation()
except ValueError as e:
    # 记录异常，但不包含堆栈（简单错误）
    logger.error("参数验证失败: %s", str(e))
except Exception as e:
    # 记录异常和完整堆栈（未预期的错误）
    logger.error("操作失败", exc_info=True)
    # 自动包含完整的堆栈跟踪信息
```

**❌ 错误做法**：

```python
# ❌ 禁止使用 loguru 的 opt(exception=True)
logger.opt(exception=True).error("操作失败")  # 已废弃

# ❌ 禁止手动格式化异常
import traceback
logger.error(f"错误: {traceback.format_exc()}")  # 使用 exc_info=True 即可

# ❌ 禁止吞掉异常
try:
    risky_operation()
except Exception:
    pass  # 必须记录日志
```

---

#### 日志格式规范

**标准格式**：使用 `%s` 占位符（不是 f-string）

```python
# ✅ 正确：使用 % 格式化（延迟格式化，性能更好）
logger.info("用户登录 - user_id: %s, ip: %s", user_id, client_ip)
logger.debug("查询结果 - count: %d, elapsed: %.2fs", count, elapsed)

# ✅ 正确：复杂数据使用 extra 参数
logger.info(
    "操作成功",
    extra={
        "operation": "user_login",
        "user_id": user_id,
        "ip": client_ip,
        "request_id": request_id
    }
)

# ❌ 错误：使用 f-string（提前格式化，浪费性能）
logger.info(f"用户登录 - user_id: {user_id}")  # 即使日志级别不够，也会格式化

# ❌ 错误：字符串拼接
logger.info("用户登录 - user_id: " + user_id)  # 性能差
```

**生产环境日志规范**：

```python
import os
import logging

logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv('ENVIRONMENT') == 'production'

if IS_PRODUCTION:
    # 生产环境：简洁、结构化、无 Emoji
    logger.info(
        "用户登录成功",
        extra={
            "user_id": user_id,
            "ip": client_ip,
            "request_id": request_id
        }
    )
else:
    # 开发环境：可以使用 Emoji 增强可读性（可选）
    logger.info("✅ 用户登录成功 - user_id: %s, ip: %s", user_id, client_ip)
```

---

#### 🚨 禁止使用 print

```python
# ❌ 绝对禁止在生产代码中使用 print
print(f"User logged in: {user_id}")  # 无日志级别、无结构化字段、难以追踪

# ✅ 使用 logging
logger = logging.getLogger(__name__)
logger.info("用户登录 - user_id: %s", user_id)

# 📝 例外：仅在脚本/调试工具中临时使用，且必须加注释
if __name__ == "__main__":
    # 临时调试输出，生产环境不会执行此代码
    print(f"Debug: Loading config from {config_path}")
```

---

#### Logging 配置示例（`backend/main.py`）

```python
import logging
import sys
from backend.config.settings import settings

# 配置根 logger
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/app.log")
    ]
)

# 获取模块 logger
logger = logging.getLogger(__name__)

# 根据环境配置不同的日志格式
if settings.ENVIRONMENT == "production":
    # 生产环境：简洁格式，INFO 级别
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # 添加文件 handler（错误日志）
    error_handler = logging.FileHandler("logs/error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logging.getLogger().addHandler(error_handler)
else:
    # 开发环境：详细格式，DEBUG 级别
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)

logger.info("🚀 应用启动 - 环境: %s", settings.ENVIRONMENT)
```

**OpenTelemetry 集成（AgentCore Runtime）**：

```python
# deployment/agentcore/Dockerfile
# Runtime 环境使用 OpenTelemetry 自动仪表化
CMD ["opentelemetry-instrument", "python", "-m", "backend.agent.agent_runtime"]

# backend/agent/agent_runtime.py
import logging

# 标准 logging 会自动集成到 OpenTelemetry
logger = logging.getLogger(__name__)

@app.post("/invocations")
async def invoke_agent(request: InvocationRequest):
    # 日志会自动发送到 CloudWatch + X-Ray
    logger.info("收到调用请求 - session_id: %s", request.session_id)
    try:
        result = await process_request(request)
        logger.info("调用成功 - session_id: %s", request.session_id)
        return result
    except Exception as e:
        logger.error("调用失败", exc_info=True)
        raise
```

---

#### 完整示例

```python
# backend/services/user_service.py
import logging
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.user import User

# 在模块顶层定义 logger
logger = logging.getLogger(__name__)


class UserService:
    """用户服务"""

    def __init__(self, db: Session):
        self.db = db
        logger.debug("UserService 初始化完成")

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户信息"""
        logger.info("查询用户 - user_id: %s", user_id)

        try:
            user = self.db.query(User).filter(User.id == user_id).first()

            if user:
                logger.info("用户查询成功 - user_id: %s", user_id)
            else:
                logger.warning("用户不存在 - user_id: %s", user_id)

            return user

        except Exception as e:
            logger.error("用户查询失败 - user_id: %s", user_id, exc_info=True)
            raise

    def create_user(self, email: str, password: str) -> User:
        """创建用户"""
        logger.info("创建用户 - email: %s", email)

        try:
            user = User(email=email)
            user.set_password(password)  # 密码不记录日志

            self.db.add(user)
            self.db.commit()

            logger.info("用户创建成功 - user_id: %s, email: %s", user.id, email)
            return user

        except Exception as e:
            self.db.rollback()
            logger.error("用户创建失败 - email: %s", email, exc_info=True)
            raise
```

---

#### 敏感信息保护（强化版）

> **🔴 零容忍原则**：完全不记录任何密钥/Token/PII，调试需显式脱敏开关

**敏感字段清单**：

- AWS/GCP 凭证：`AccessKeyId`, `SecretAccessKey`, `SessionToken`, `service_account_key`
- 数据库凭证：连接串中的密码、用户名
- 用户 PII：手机号、身份证号、完整邮箱、详细地址
- 业务敏感信息：银行卡号、支付密钥、内部 API Key

**脱敏规范**：

```python
import logging
import os
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# ✅ 正确：完全不记录敏感信息
logger.info("用户登录成功 - user_id: %s", user_id)  # 只记录 ID，不记录邮箱/手机

# ✅ 调试模式脱敏（仅前 4 位 + 星号）
DEBUG_MODE = os.getenv('DEBUG_SENSITIVE_DATA') == 'true'

if DEBUG_MODE:
    # 显式开启脱敏调试
    masked_key = f"{access_key[:4]}{'*' * 12}"
    logger.debug("AWS Key (masked): %s", masked_key)

# ❌ 错误：记录完整敏感信息
logger.info("用户登录 - Email: %s", email)  # 泄露邮箱
logger.debug("AWS Access Key: %s***", access_key[:8])  # 前8位仍可暴力枚举
logger.info("DB连接: %s", db_url)  # 泄露密码

# ✅ 正确：URL 脱敏
def mask_url_password(url: str) -> str:
    """脱敏 URL 中的密码"""
    parsed = urlparse(url)
    if parsed.password:
        netloc = f"{parsed.username}:***@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url

logger.info("数据库连接: %s", mask_url_password(db_url))
# 输出: postgresql://user:***@localhost:5432/dbname
```

---

### 2.4 安全规范

> **🔴 升级**：统一"完全不记录"策略，调试需显式开关

**凭证管理**：

```python
# ✅ 正确：从环境变量或 Secret Manager 读取
from backend.config.settings import settings

aws_access_key = settings.AWS_ACCESS_KEY_ID  # 从环境变量读取
db_password = get_secret("costq/rds/postgresql")  # 从 AWS Secrets Manager 读取

# ❌ 错误：硬编码凭证
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"  # 绝对禁止
DB_PASSWORD = "mysecretpassword"  # 绝对禁止
```

**敏感信息日志策略**：

```python
# 🚨 统一规则：完全不记录任何密钥/Token/PII

# ❌ 绝对禁止
logger.info(f"Access Key: {access_key}")
logger.info(f"Session Token: {session_token}")
logger.info(f"User email: {email}")
logger.info(f"User phone: {phone}")

# ✅ 正确：只记录非敏感的标识符
logger.info(
    "凭证获取成功",
    extra={
        "account_id": account_id,
        "credential_type": "STS",  # 只记录类型
        "expires_at": expires_at.isoformat()
    }
)

```

**输入验证**：

```python
from pydantic import BaseModel, validator, EmailStr

class UserCreate(BaseModel):
    """用户创建请求"""
    email: EmailStr  # 自动验证邮箱格式
    username: str
    password: str

    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('用户名至少3个字符')
        if not v.isalnum():
            raise ValueError('用户名只能包含字母和数字')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码至少8个字符')
        return v
```

**SQL 注入防护**：

```python
# ✅ 正确：使用 SQLAlchemy ORM（自动防护）
user = db.query(User).filter(User.email == email).first()

# ✅ 正确：使用参数化查询
result = db.execute(
    "SELECT * FROM users WHERE email = :email",
    {"email": email}
)

# ❌ 错误：字符串拼接（SQL注入风险）
query = f"SELECT * FROM users WHERE email = '{email}'"  # 危险！
db.execute(query)
```

---

### 2.5 性能优化规范

**缓存策略**：

```python
from cachetools import TTLCache
import threading

class ServiceManager:
    """服务管理器（带缓存）"""

    def __init__(self):
        # ✅ 使用TTL缓存，防止内存泄漏
        self._cache = TTLCache(maxsize=100, ttl=3600)  # 1小时过期
        self._lock = threading.Lock()

    def get_or_create(self, key: str):
        # 线程安全的缓存访问
        with self._lock:
            if key in self._cache:
                return self._cache[key]

            value = self._create_expensive_resource(key)
            self._cache[key] = value
            return value
```

**数据库查询优化**：

```python
# ✅ 使用索引字段查询
users = db.query(User).filter(User.email == email).all()

# ✅ 使用 join 减少查询次数
users_with_orgs = db.query(User).join(Organization).all()

# ✅ 限制返回数量
recent_logs = db.query(Log).order_by(Log.created_at.desc()).limit(100).all()

# ❌ 避免 N+1 查询问题
for user in users:
    org = db.query(Organization).filter(Organization.id == user.org_id).first()
    # 应该使用 join 或 joinedload
```

**并发控制**：

```python
# ✅ 限制并发数量
self.max_concurrent_alerts = int(os.getenv('ALERT_SCHEDULER_MAX_CONCURRENT', 5))

semaphore = asyncio.Semaphore(self.max_concurrent_alerts)

async def execute_with_limit(alert):
    async with semaphore:
        return await execute_alert(alert)
```

---

### 2.6 MCP 服务器开发规范

**服务器结构**：

```
mcp_server/
├── __init__.py
├── server.py          # MCP 服务器入口
├── constants.py       # 常量定义
├── handlers/          # 业务处理器
│   ├── __init__.py
│   └── main_handler.py
├── models/            # 数据模型
│   ├── __init__.py
│   └── request_models.py
├── utils/             # 工具函数
│   ├── __init__.py
│   └── aws_client.py
└── tests/             # 测试
    ├── __init__.py
    └── test_handler.py
```

**Handler 规范**（完整导入示例）：

```python
# ============ 必要导入 ============
import logging
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

async def handle_get_cost(
    context: Dict[str, Any],
    time_period: Dict[str, str],
    granularity: str = "MONTHLY"
) -> Dict[str, Any]:
    """获取成本数据

    Args:
        context: MCP 上下文（包含凭证等信息）
        time_period: 时间范围 {"start": "2025-01-01", "end": "2025-01-31"}
        granularity: 粒度（DAILY/MONTHLY）

    Returns:
        成本数据字典

    Raises:
        ValueError: 参数无效
        RuntimeError: AWS API 调用失败
    """
    # 参数验证
    if not time_period or 'start' not in time_period:
        raise ValueError("time_period 必须包含 'start' 字段")

    # 获取凭证
    credentials = context.get('credentials')
    if not credentials:
        raise ValueError("缺少 AWS 凭证")

    try:
        # 调用 AWS API
        client = boto3.client('ce', **credentials)
        response = client.get_cost_and_usage(
            TimePeriod=time_period,
            Granularity=granularity,
            Metrics=['UnblendedCost']
        )

        logger.info(
            "成本查询成功 - time_period: %s, granularity: %s, result_count: %d",
            time_period, granularity, len(response.get('ResultsByTime', []))
        )
        return response

    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(
            "AWS API调用失败 - api: get_cost_and_usage, error_code: %s, error: %s",
            error_code, str(e)
        )
        raise RuntimeError(f"AWS API 错误: {error_code}")
```

---

## 三、通用最佳实践

### 3.1 代码可读性优先

**原则**：
- 代码写给人看，不是写给机器的
- 命名语义明确，见名知义
- 函数保持单一职责（SRP）
- 避免大文件（>500行）、大函数（>50行）

**示例**：

```python
# ✅ 好的命名
def calculate_monthly_cost(account_id: str, month: str) -> float:
    """计算指定月份的成本"""
    pass

# ❌ 差的命名
def calc(a: str, m: str) -> float:  # 名称过于简短
    pass

def get_data():  # 名称过于宽泛
    pass
```

---

### 3.2 单一职责原则

**每个函数/类只做一件事**：

```python
# ✅ 正确：职责分离
class UserService:
    def create_user(self, data: dict) -> User:
        """创建用户"""
        pass

    def send_welcome_email(self, user: User) -> None:
        """发送欢迎邮件"""
        pass

# 调用
user = user_service.create_user(data)
user_service.send_welcome_email(user)

# ❌ 错误：一个函数做了太多事
def create_user_and_send_email(data: dict):
    # 验证数据
    # 创建用户
    # 发送邮件
    # 记录日志
    # 更新统计
    pass
```

---

### 3.3 DRY 原则

**Don't Repeat Yourself - 避免重复代码**：

```python
# ✅ 正确：提取公共逻辑
def format_currency(amount: float) -> str:
    """格式化货币"""
    return f"${amount:,.2f}"

def get_monthly_cost():
    cost = calculate_cost()
    return format_currency(cost)

def get_yearly_cost():
    cost = calculate_cost() * 12
    return format_currency(cost)

# ❌ 错误：重复代码
def get_monthly_cost():
    cost = calculate_cost()
    return f"${cost:,.2f}"

def get_yearly_cost():
    cost = calculate_cost() * 12
    return f"${cost:,.2f}"  # 重复的格式化逻辑
```

---

### 3.4 可测试性设计

**编写可测试的代码**：

```python
# ✅ 好的设计：依赖注入
class UserService:
    def __init__(self, db_session, email_service):
        self.db = db_session
        self.email = email_service

    def create_user(self, data: dict):
        user = User(**data)
        self.db.add(user)
        self.db.commit()
        self.email.send_welcome(user)
        return user

# 测试时可以注入 Mock 对象
def test_create_user():
    mock_db = Mock()
    mock_email = Mock()
    service = UserService(mock_db, mock_email)

    user = service.create_user({"email": "test@example.com"})

    mock_db.add.assert_called_once()
    mock_email.send_welcome.assert_called_once()
```

---

### 3.5 错误处理最佳实践

**渐进式错误处理**：

```python
def process_user_request(user_id: str):
    """处理用户请求（多层错误处理）"""
    try:
        # 第一层：参数验证
        if not user_id:
            raise ValueError("用户ID不能为空")

        # 第二层：业务逻辑
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 第三层：外部依赖
        try:
            result = external_api_call(user)
        except ConnectionError:
            logger.warning("外部API暂时不可用，使用缓存数据")
            result = get_cached_data(user)

        return result

    except ValueError as e:
        logger.error(f"参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise  # 重新抛出 HTTP 异常
    except Exception as e:
        logger.opt(exception=True).error("未预期的错误")
        raise HTTPException(status_code=500, detail="内部服务器错误")
```

---

## 四、Git 提交规范

### 4.1 提交信息格式

**使用 Conventional Commits 格式**：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**：

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(alert): 添加告警定时调度功能` |
| `fix` | Bug 修复 | `fix(auth): 修复 JWT token 过期时间计算错误` |
| `docs` | 文档更新 | `docs: 更新 API 文档` |
| `style` | 代码格式（不影响功能） | `style: 统一代码缩进为4空格` |
| `refactor` | 重构 | `refactor(mcp): 重构 MCP 客户端管理器` |
| `perf` | 性能优化 | `perf(db): 优化用户查询索引` |
| `test` | 测试相关 | `test: 添加告警服务单元测试` |
| `chore` | 构建/工具 | `chore: 更新依赖版本` |

**示例**：

```bash
# 好的提交信息
feat(alert): 添加告警定时调度功能

- 实现每天 7:00 自动扫描告警
- 支持并发执行，最多5个同时
- 添加失败重试机制（最多3次）
- 记录详细的执行日志

Closes #123

# 简短提交（小改动）
fix: 修复导入路径错误

# 带 scope 的提交
feat(api): 添加用户管理 REST API
```

---

### 4.2 分支命名规范

**格式**：`<type>/<description>`

```bash
# 功能分支
feature/user-authentication
feature/alert-scheduler

# Bug 修复分支
bugfix/login-timeout
bugfix/database-connection

# 热修复分支（生产环境紧急修复）
hotfix/security-patch
hotfix/memory-leak

# 发布分支
release/v2.0.0

# 主分支
main      # 生产环境
develop   # 开发环境
```

---

## 五、文档规范

### 5.1 代码文档要求

**最少文档要求**：

1. **README.md**（必须）
   - 项目简介
   - 快速开始
   - 配置说明
   - 使用示例

2. **模块/包级别文档**
   - `__init__.py` 中添加模块说明
   - 关键类和函数添加 docstring

3. **API 文档**
   - FastAPI 自动生成（`/docs`）
   - 关键接口添加详细说明

**示例**：

```python
"""
backend.services.alert_scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

告警定时调度服务

职责：
1. 每天上午 7:00 (Asia/Tokyo) 自动扫描并执行告警
2. 批量并发执行，控制并发数（默认5个）
3. 异常处理和指数退避重试（最多3次）
4. 记录详细的执行日志

设计原则：
- 单例模式：确保全局只有一个调度器实例
- 线程安全：使用 BackgroundScheduler 在后台线程运行
- 容错性：失败重试 + 详细日志记录

作者：CostQ 开发团队
日期：2025-11-19
"""
```

---

### 5.2 项目文档管理

**文档组织原则**：

```
docs/
├── README.md                    # 文档索引
├── 功能说明/                    # 功能设计文档
│   ├── 智能报警系统/
│   └── 告警MCP权限问题/
├── 调研报告/                    # 技术调研
├── 问题修复/                    # Bug 修复记录
├── 性能优化/                    # 性能优化记录
└── archive/                     # 历史归档
```

**文档命名规范**：
- 使用中文文件夹名（团队母语）
- 使用描述性的文件名
- 日期前缀（如需要）：`20251201-功能设计.md`

---

## 六、部署与发布规范

### 6.1 环境配置

**环境隔离**：

```python
# backend/config/settings.py
class Settings:
    """应用配置（支持环境变量覆盖）"""

    # 环境标识
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')

    # 数据库（开发环境和生产环境使用不同的密钥）
    def get_db_secret_name(self):
        if self.ENVIRONMENT == 'production':
            return 'costq/rds/postgresql'
        else:
            return 'costq/rds/postgresql-dev'
```

**部署检查清单**：

- [ ] 环境变量已配置
- [ ] 数据库迁移已执行
- [ ] 静态文件已构建
- [ ] 健康检查正常
- [ ] 日志级别正确（生产环境=INFO）
- [ ] 日志格式正确（生产环境=JSON，无 Emoji）
- [ ] 敏感信息脱敏检查
- [ ] Pod 成功启动
- [ ] 启动日志无错误

---

## 附录 A：常用导入清单

### FastAPI 应用

```python
# 标准库
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager

# 第三方库
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

# SQLAlchemy
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Session, relationship
from sqlalchemy.ext.asyncio import AsyncSession

# 本地模块
from backend.config.settings import settings
from backend.database import SessionLocal, async_session_maker
from backend.models.user import User
from backend.services.alert_scheduler import AlertScheduler

# 定义模块 logger
logger = logging.getLogger(__name__)
```

### 数据库模型

```python
# 标准库
from datetime import datetime, timezone
import uuid

# SQLAlchemy
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

# 本地模块
from backend.models.base import Base
```

### MCP Handler

```python
# 标准库
import logging
from typing import Dict, Any, Optional, List

# 第三方库
import boto3
from botocore.exceptions import ClientError

# 本地模块（如需要）
from backend.utils.retry import retry_with_backoff

# 定义模块 logger
logger = logging.getLogger(__name__)
```

### 服务类

```python
# 标准库
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
import threading

# 第三方库
from cachetools import TTLCache

# SQLAlchemy
from sqlalchemy.orm import Session

# 本地模块
from backend.database import SessionLocal
from backend.models.user import User
from backend.config.settings import settings

# 定义模块 logger
logger = logging.getLogger(__name__)
```

---

## 📚 参考资源

- [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 484 – Type Hints](https://peps.python.org/pep-0484/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [SQLAlchemy Best Practices](https://docs.sqlalchemy.org/en/20/orm/index.html)
- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [Ruff Documentation](https://docs.astral.sh/ruff/)

---

## 🔄 文档维护

- **版本**: v2.1.0
- **最后更新**: 2025-12-28
- **下次审查**: 2026-03-28（每3个月审查一次）
- **维护人**: 全栈工程团队
- **更新记录**:
  - v2.1.0 (2025-12-28): 全面迁移到标准 Python logging
  - v2.0.0 (2025-12-02): 初始版本

---

**注意**: 本规范是团队共识，所有成员必须遵守。如有建议，请提交 PR 或在团队会议中讨论。
