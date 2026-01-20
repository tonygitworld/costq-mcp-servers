"""FastAPI主应用"""

import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .api.accounts import router as accounts_router

import logging

logger = logging.getLogger(__name__)
from .api.alerts import router as alerts_router  # Alert MCP Server REST API
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.gcp_accounts import router as gcp_accounts_router
from .api.http import QueryRequest, detailed_health_check, health_check, process_query

# P2-3: 禁用监控 API（安全考虑）
from .api.monitoring import router as monitoring_router  # Phase 4: 监控路由（简化版）
from .api.ops import ops_router  # 运营后台路由
from .api.profile import router as profile_router
from .api.prompt_templates import router as prompt_templates_router
from .api.users import router as users_router
from .api.websocket import websocket_endpoint
from .config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 - 启动时初始化所有资源

    Phase 2 优化: 启用 MCP 预热机制
    - 使用默认凭证预热高优先级 MCP 服务器
    - 预热失败不影响应用启动
    """

    # ✅ P0: 禁用 OpenTelemetry 详细日志（避免刷新页面时的 context 警告）
    import logging

    logging.getLogger("opentelemetry").setLevel(logging.ERROR)
    logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

    print("\n" + "=" * 60)
    print("🚀 启动 AWS CostQ Agent (动态架构)")
    print("=" * 60)
    print("✅ 核心组件已就绪")
    print("📝 MCP客户端将在首次查询时按需创建")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 告警调度器启动
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    alert_scheduler_started = False
    try:
        from .services.alert_scheduler import alert_scheduler

        alert_scheduler.start()
        alert_scheduler_started = True
        print("✅ AlertScheduler 已启动")
        # 获取下次执行时间
        status = alert_scheduler.get_status()
        if status.get("next_run_time"):
            print(f"⏰ 下次执行: {status['next_run_time']}")
    except Exception as e:
        print(f"❌ AlertScheduler 启动失败（不影响其他功能）: {e}")
        import traceback

        traceback.print_exc()
        alert_scheduler_started = False

    # Phase 3: 健康检查（新架构简化版）
    # 注意：新架构无MCP缓存，无需健康检查
    health_check_task = None

    # 简化的健康检查（仅日志记录）
    try:

        async def health_check_loop():
            """简化的健康检查（新架构）

            新架构说明：
            - 无MCP客户端缓存，无需检查客户端状态
            - 只记录基本的运行状态
            """
            while True:
                try:
                    await asyncio.sleep(60)  # 每60秒检查一次

                    # ━━━━━━━━━━ MCP 客户端健康检查（已移除）━━━━━━━━━━
                    # 新架构无MCP缓存，跳过此检查
                    # client_manager = get_dynamic_client_manager()
                    # stats = client_manager.get_stats()

                    # 新架构：MCP检查已移除（无缓存）
                    # health_result = await asyncio.to_thread(...)
                    # （已移除MCP健康检查相关代码）

                    # ━━━━━━━━━━ WebSocket 连接状态检查 ━━━━━━━━━━
                    from .api.websocket import manager

                    connection_count = len(manager.active_connections)
                    if connection_count > 0:
                        now = time.time()
                        idle_connections = []
                        stale_heartbeats = []

                        for user_id, session_info in manager.user_sessions.items():
                            username = session_info.get("username", user_id)

                            # 检查心跳
                            last_heartbeat = manager.last_heartbeat.get(user_id, now)
                            heartbeat_age = now - last_heartbeat

                            # 检查查询活跃度
                            last_query = manager.last_query_time.get(user_id, now)
                            idle_time = now - last_query

                            # 心跳超过5分钟 - 可能是僵尸连接
                            if heartbeat_age > 300:
                                stale_heartbeats.append(
                                    {
                                        "username": username,
                                        "heartbeat_age": heartbeat_age,
                                        "idle_time": idle_time,
                                    }
                                )

                            # 空闲超过1小时 - 长时间未活动
                            if idle_time > 3600:
                                idle_connections.append(
                                    {"username": username, "idle_time": idle_time}
                                )

                        # 记录异常连接
                        if stale_heartbeats:
                            for conn in stale_heartbeats:
                                logger.warning(
                                    f"⚠️  检测到可疑连接 - User: {conn['username']}, "
                                    f"心跳丢失: {conn['heartbeat_age'] / 60:.1f}分钟, "
                                    f"空闲: {conn['idle_time'] / 60:.1f}分钟"
                                )

                        if idle_connections and not stale_heartbeats:  # 避免重复日志
                            logger.info(f"💤 检测到长时间空闲连接 - 数量: {len(idle_connections)}")

                        # 正常情况也记录概要（debug级别）
                        if not stale_heartbeats and not idle_connections:
                            logger.debug(f"🔌 WebSocket连接健康 - 总连接数: {connection_count}")

                    # ━━━━━━━━━━ 数据库连接池监控 ━━━━━━━━━━
                    from .database import get_engine

                    try:
                        engine = get_engine()
                        pool = engine.pool
                        pool_size = pool.size()
                        checked_out = pool.checkedout()
                        overflow = pool.overflow()

                        # 连接池使用率
                        if pool_size > 0:
                            usage_rate = (checked_out / pool_size) * 100

                            # 高使用率告警（>80%）
                            if usage_rate > 80:
                                logger.warning(
                                    f"⚠️  数据库连接池使用率过高 - "
                                    f"活跃: {checked_out}/{pool_size} ({usage_rate:.0f}%), "
                                    f"溢出: {overflow}"
                                )
                            else:
                                logger.debug(
                                    f"🔌 数据库连接池 - "
                                    f"活跃: {checked_out}/{pool_size} ({usage_rate:.0f}%), "
                                    f"溢出: {overflow}"
                                )
                    except Exception as pool_err:
                        logger.debug(f"数据库连接池状态检查失败: {pool_err}")

                except Exception as e:
                    logger.warning(f"⚠️  健康检查失败（不影响服务）: {e}")

        # 启动后台健康检查
        health_check_task = asyncio.create_task(health_check_loop())
        logger.info("✅ Phase 3: MCP 健康检查已启动（每60秒）")

    except Exception as e:
        logger.warning(f"⚠️  健康检查启动失败（不影响服务）: {e}")

    print("⚡ 启动时间: <3秒")
    print("=" * 60 + "\n")

    yield

    # 关闭时清理资源
    print("\n🔄 应用关闭，清理资源...")

    # 停止告警调度器
    if alert_scheduler_started:
        try:
            from .services.alert_scheduler import alert_scheduler

            alert_scheduler.stop()
            print("✅ AlertScheduler 已停止")
        except Exception as e:
            print(f"⚠️  AlertScheduler 停止失败: {e}")

    # 取消健康检查任务
    if health_check_task:
        health_check_task.cancel()
        try:
            await health_check_task
        except asyncio.CancelledError:
            pass

    # 新架构：无MCP缓存，无需清理
    # from .mcp.dynamic_clients import get_dynamic_client_manager
    # （已移除MCP清理代码）
    print("✅ 清理完成（新架构无需清理MCP缓存）")


# 初始化速率限制器
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="最懂AWS的智能助手",
    description="智能AWS分析和优化建议",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# 添加全局验证异常处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """捕获并记录详细的验证错误"""
    errors = exc.errors()
    logger.error(f"❌ 请求验证失败 - URL: {request.url}, 错误: {errors}")

    # 转换错误为可序列化的格式
    serializable_errors = []
    for error in errors:
        error_dict = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "input": error.get("input"),
        }
        # 如果有 ctx，转换为字符串
        if "ctx" in error and error["ctx"]:
            error_dict["ctx"] = {k: str(v) for k, v in error["ctx"].items()}
        serializable_errors.append(error_dict)

    return JSONResponse(
        status_code=422,
        content={
            "detail": serializable_errors,
            "body": str(exc.body) if hasattr(exc, "body") else None,
        },
    )


# 添加请求日志中间件（用于调试403）
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求和响应"""
    if request.url.path.startswith("/api/gcp-accounts"):
        logger.debug(
            f"🔍 GCP请求 - Method: {request.method}, Path: {request.url.path}, Headers: {dict(request.headers)}"
        )

    response = await call_next(request)

    if request.url.path.startswith("/api/gcp-accounts") and response.status_code == 403:
        logger.error(
            f"❌ GCP 403错误 - Method: {request.method}, Path: {request.url.path}, Status: {response.status_code}"
        )

    return response


# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),  # 从配置读取允许的来源
    allow_credentials=True,  # 允许携带认证信息（cookies, authorization headers）
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # 允许的HTTP方法
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],  # 允许的请求头
    expose_headers=["Content-Length", "X-Request-ID"],  # 暴露给前端的响应头
    max_age=600,  # 预检请求的缓存时间（秒）
)

# 注册路由
app.include_router(auth_router)  # 认证路由
app.include_router(profile_router)  # 个人信息路由
app.include_router(users_router)  # 用户管理路由
app.include_router(chat_router)  # 聊天历史路由
app.include_router(accounts_router)  # AWS 账号管理
app.include_router(gcp_accounts_router)  # GCP 账号管理
app.include_router(prompt_templates_router)  # 提示词模板路由
app.include_router(alerts_router)  # 告警管理路由 (Alert MCP Server)
# P2-3: 禁用监控 API（安全考虑）
app.include_router(monitoring_router)  # Phase 4: 监控路由（简化版）
app.include_router(ops_router)  # 运营后台路由

# 挂载静态文件（开发环境禁用缓存）
class NoCacheStaticFiles(StaticFiles):
    """开发环境下禁用缓存的静态文件服务"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        """拦截响应，添加禁用缓存的响应头"""
        if scope["type"] == "http":

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers", []))
                    # 开发环境禁用缓存
                    if settings.ENVIRONMENT == "local":
                        headers[b"cache-control"] = b"no-cache, no-store, must-revalidate"
                        headers[b"pragma"] = b"no-cache"
                        headers[b"expires"] = b"0"
                    message["headers"] = list(headers.items())
                await send(message)

            await super().__call__(scope, receive, send_wrapper)
        else:
            await super().__call__(scope, receive, send)


app.mount("/static", NoCacheStaticFiles(directory="static"), name="static")


@app.get("/")
async def get_index(response: Response):
    """返回React应用"""
    react_index = "static/react-build/index.html"

    if os.path.exists(react_index):
        with open(react_index, encoding="utf-8") as f:
            html_content = f.read()

        # 🚨 禁用缓存，确保加载最新代码
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        # 修正静态资源路径
        html_content = html_content.replace('href="/assets/', 'href="/static/react-build/assets/')
        html_content = html_content.replace('src="/assets/', 'src="/static/react-build/assets/')
        html_content = html_content.replace(
            'href="/vite.svg"', 'href="/static/react-build/vite.svg"'
        )
        html_content = html_content.replace(
            'href="/cloud-icon.svg"', 'href="/static/react-build/cloud-icon.svg"'
        )

        return HTMLResponse(content=html_content)

    return {
        "error": "Frontend not built",
        "message": "Please run 'npm run build' in the frontend directory",
    }


@app.get("/health")
async def health():
    """基础健康检查"""
    return await health_check()


@app.get("/health/detailed")
async def health_detailed():
    """详细健康检查"""
    return await detailed_health_check()


@app.get("/api/stats")
async def get_resource_stats():
    """
    获取资源使用统计

    Returns:
        dict: 包含资源使用情况的统计信息
    """
    from .services.resource_manager import get_resource_manager
    # 新架构：移除dynamic_clients和dynamic_agent
    # from .mcp.dynamic_clients import get_dynamic_client_manager
    # from .agent.dynamic_agent import get_dynamic_agent_manager

    resource_manager = get_resource_manager()

    return {
        "timestamp": time.time(),
        "resources": resource_manager.get_stats(),
        "architecture": "simplified",  # 标识新架构
        "note": "新架构无MCP/Agent缓存",
    }


@app.post("/api/query")
async def query(request: QueryRequest):
    """处理查询"""
    return await process_query(request)


@app.post("/api/ws/cancel/{query_id}")
async def cancel_query(query_id: str, request: Request):
    """
    取消正在进行的查询

    支持 sendBeacon 调用（页面刷新时）
    """
    try:
        from .api.websocket import manager

        # 获取请求体（可能为空）
        try:
            body = await request.json()
            reason = body.get("reason", "user_cancelled")
        except Exception:
            reason = "user_cancelled"

        # 触发取消事件
        if query_id in manager.cancel_events:
            manager.cancel_events[query_id].set()
            logger.info(f"📡 收到取消请求 - Query: {query_id}, Reason: {reason}")
            return {"success": True, "message": "Query cancelled"}
        else:
            logger.warning(f"⚠️  查询ID不存在或已完成 - Query: {query_id}")
            return {"success": False, "message": "Query not found or already completed"}

    except Exception as e:
        logger.error(f"❌ 取消查询失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.websocket("/ws")
async def websocket(websocket: WebSocket, token: str):
    """WebSocket端点 - 需要JWT Token认证"""
    await websocket_endpoint(websocket, token)


@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """
    Catch-all route for SPA client-side routing

    Returns the React app index.html for any non-API/non-static route.
    This allows React Router to handle client-side routing.
    Must be placed LAST to avoid catching API routes.
    """
    import os

    from fastapi.responses import HTMLResponse

    # ✅ 排除静态文件路径 - 防止拦截 JS/CSS 等资源
    if full_path.startswith("static/") or full_path.startswith("api/"):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not Found")

    react_index = "static/react-build/index.html"

    if os.path.exists(react_index):
        with open(react_index, encoding="utf-8") as f:
            html_content = f.read()

        # Fix static asset paths
        html_content = html_content.replace('href="/assets/', 'href="/static/react-build/assets/')
        html_content = html_content.replace('src="/assets/', 'src="/static/react-build/assets/')
        html_content = html_content.replace(
            'href="/vite.svg"', 'href="/static/react-build/vite.svg"'
        )
        html_content = html_content.replace(
            'href="/cloud-icon.svg"', 'href="/static/react-build/cloud-icon.svg"'
        )

        return HTMLResponse(content=html_content)

    # If React build doesn't exist, return 404
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="Frontend not built")
