"""HTTP API端点

Phase 4: 集成性能监控
"""

import os
import time

from fastapi import HTTPException
from pydantic import BaseModel

from ..agent.agent_manager import AgentManager
from ..agent.prompts import get_aws_intelligent_agent_prompt
from ..mcp.mcp_manager import MCPManager
from ..utils.metrics import get_metrics

import logging

logger = logging.getLogger(__name__)

# 性能统计（简单版）
_query_count = 0
_total_query_time = 0.0
_app_start_time = time.time()


class QueryRequest(BaseModel):
    message: str


class QueryResponse(BaseModel):
    response: str
    status: str = "success"


async def process_query(
    request: QueryRequest, user_id: str = "http_user", account_id: str = "default"
) -> QueryResponse:
    """
    处理查询请求 - 使用动态Agent

    注意: HTTP端点已废弃，建议使用WebSocket API
    此端点使用环境变量中的默认AWS凭证

    Phase 4: 添加性能监控
    """
    # Phase 4: 记录开始时间
    start_time = time.time()

    try:
        # 创建管理器（简化版，无缓存）
        system_prompt = get_aws_intelligent_agent_prompt()
        agent_manager = AgentManager(system_prompt=system_prompt, model_id=None)
        mcp_manager = MCPManager()

        # 设置AWS环境变量（HTTP API使用环境变量中的凭证）
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")

        if not aws_access_key or not aws_secret_key:
            raise HTTPException(
                status_code=503,
                detail="AWS凭证未配置，请设置 AWS_ACCESS_KEY_ID 和 AWS_SECRET_ACCESS_KEY 环境变量",
            )

        # 设置目标账号信息（供MCP使用）
        os.environ["TARGET_ACCOUNT_ID"] = account_id
        os.environ["TARGET_ROLE_NAME"] = "CostQAccessRole"

        # ✅ 串行加载MCP客户端（稳定性优先）
        # 注意：HTTP API环境如资源充足，可改用 create_all_clients_parallel 加速
        mcp_clients_dict = mcp_manager.create_all_clients()

        if not mcp_clients_dict:
            raise HTTPException(status_code=503, detail="无法创建MCP客户端")

        # 提取工具列表
        all_tools = []
        for server_type, client in mcp_clients_dict.items():
            try:
                tools = client.list_tools_sync()
                all_tools.extend(tools)
                logger.info(f"✅ 从 {server_type} 加载了 {len(tools)} 个工具")
            except Exception as e:
                # ✅ 改进：记录详细错误信息
                logger.warning(
                    f"❌ 从 {server_type} 加载工具失败",
                    extra={
                        "server_type": server_type,
                        "error_type": type(e).__name__,
                        "error": str(e),
                    }
                )

        if not all_tools:
            raise HTTPException(status_code=503, detail="没有可用的工具")

        # 创建Agent（支持Memory）
        # HTTP API使用user_id作为session_id（简化处理）
        agent = agent_manager.create_agent_with_memory(
            tools=all_tools,
            user_id=user_id,
            org_id="default_org",  # HTTP API使用默认org
            session_id=f"http_{user_id}",
        )

        # 执行查询
        response = agent(request.message)

        # Phase 4: 记录查询性能
        duration = time.time() - start_time
        metrics = get_metrics()
        metrics.record_query_time(account_id, duration)

        return QueryResponse(response=str(response))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理查询失败: {str(e)}")


async def health_check():
    """基础健康检查"""
    return {
        "status": "healthy",
        "architecture": "dynamic",
        "message": "Application is running with dynamic MCP architecture",
    }


async def detailed_health_check():
    """详细健康检查 - 动态架构"""
    agent_manager = get_dynamic_agent_manager()
    client_manager = get_dynamic_client_manager()

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() - _app_start_time, 2),
        "architecture": "dynamic",
        "components": {
            "mcp": {
                "type": "dynamic",
                "total_accounts": len(client_manager._clients_cache),
                "total_subprocesses": sum(
                    len(clients) for clients in client_manager._clients_cache.values()
                ),
            },
            "agent": {"type": "dynamic", "cached_agents": len(agent_manager._agents_cache)},
        },
        "performance": {
            "queries_processed": _query_count,
            "avg_response_time": round(_total_query_time / _query_count, 2)
            if _query_count > 0
            else 0,
        },
    }


def record_query_time(duration: float):
    """记录查询耗时"""
    global _query_count, _total_query_time
    _query_count += 1
    _total_query_time += duration
