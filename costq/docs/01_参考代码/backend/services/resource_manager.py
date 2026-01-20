"""全局资源管理器

功能:
- 限制WebSocket连接数（全局+单用户）
- 限制并发查询数（全局+单用户）
- 内存监控和保护
- 资源使用统计
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import HTTPException

import logging

logger = logging.getLogger(__name__)

# psutil是可选依赖，用于内存监控
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("⚠️  psutil未安装，内存监控功能将被禁用")


class ResourceManager:
    """
    全局资源管理器

    提供系统级资源限制和监控，防止资源耗尽和OOM崩溃
    """

    # ========== 资源限制配置 ==========
    MAX_WEBSOCKET_CONNECTIONS = 1000  # 全局最多1000个WebSocket连接
    MAX_CONNECTIONS_PER_USER = 10  # 单用户最多10个连接
    MAX_CONCURRENT_QUERIES = 100  # 全局最多100个并发查询
    MAX_CONCURRENT_QUERIES_PER_USER = 5  # 单用户最多5个并发查询
    MAX_MEMORY_MB = 1800  # 最大内存占用1800MB（留200MB buffer）

    def __init__(self):
        # WebSocket连接跟踪
        self._websocket_connections: dict[str, object] = {}
        self._connection_lock = asyncio.Lock()

        # 查询跟踪
        self._active_queries: set[str] = set()
        self._query_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_QUERIES)
        self._query_lock = asyncio.Lock()

        logger.info(
            f"资源管理器初始化: WebSocket={self.MAX_WEBSOCKET_CONNECTIONS}, "
            f"查询={self.MAX_CONCURRENT_QUERIES}, 内存={self.MAX_MEMORY_MB}MB"
        )

    # ========== WebSocket连接管理 ==========

    async def check_websocket_limit(self, user_id: str) -> bool:
        """
        检查是否可以建立新的WebSocket连接

        Args:
            user_id: 用户ID

        Returns:
            bool: True表示可以建立连接，False表示已达上限
        """
        async with self._connection_lock:
            # 检查全局连接数
            total_connections = len(self._websocket_connections)
            if total_connections >= self.MAX_WEBSOCKET_CONNECTIONS:
                logger.warning(
                    f"⚠️  WebSocket连接数达到全局上限: "
                    f"{total_connections}/{self.MAX_WEBSOCKET_CONNECTIONS}"
                )
                return False

            # 检查单用户连接数
            user_connections = sum(
                1
                for conn_id in self._websocket_connections.keys()
                if conn_id.startswith(f"{user_id}:")
            )
            if user_connections >= self.MAX_CONNECTIONS_PER_USER:
                logger.warning(
                    f"⚠️  用户 {user_id} 连接数达到上限: "
                    f"{user_connections}/{self.MAX_CONNECTIONS_PER_USER}"
                )
                return False

            return True

    async def register_websocket(self, connection_id: str, websocket: object):
        """
        注册WebSocket连接

        Args:
            connection_id: 连接ID（格式: user_id:uuid）
            websocket: WebSocket对象
        """
        async with self._connection_lock:
            self._websocket_connections[connection_id] = websocket
            total = len(self._websocket_connections)
            logger.info(f"✅ 注册WebSocket: {connection_id}, 总连接数: {total}")

    async def unregister_websocket(self, connection_id: str):
        """
        注销WebSocket连接

        Args:
            connection_id: 连接ID
        """
        async with self._connection_lock:
            if connection_id in self._websocket_connections:
                del self._websocket_connections[connection_id]
                total = len(self._websocket_connections)
                logger.info(f"🔌 注销WebSocket: {connection_id}, 剩余连接数: {total}")

    # ========== 查询并发管理 ==========

    async def check_query_limit(self, user_id: str) -> bool:
        """
        检查是否可以执行新查询

        Args:
            user_id: 用户ID

        Returns:
            bool: True表示可以执行，False表示已达上限
        """
        # 检查全局并发数
        total_queries = len(self._active_queries)
        if total_queries >= self.MAX_CONCURRENT_QUERIES:
            logger.warning(
                f"⚠️  并发查询数达到全局上限: {total_queries}/{self.MAX_CONCURRENT_QUERIES}"
            )
            return False

        # 检查单用户并发数
        user_queries = sum(
            1 for query_id in self._active_queries if query_id.startswith(f"{user_id}:")
        )
        if user_queries >= self.MAX_CONCURRENT_QUERIES_PER_USER:
            logger.warning(
                f"⚠️  用户 {user_id} 并发查询数达到上限: "
                f"{user_queries}/{self.MAX_CONCURRENT_QUERIES_PER_USER}"
            )
            return False

        return True

    @asynccontextmanager
    async def acquire_query_slot(self, user_id: str, query_id: str):
        """
        获取查询槽位（context manager）

        使用方式:
            async with resource_manager.acquire_query_slot(user_id, query_id):
                # 执行查询
                result = await execute_query(...)

        Args:
            user_id: 用户ID
            query_id: 查询ID（格式: user_id:uuid）

        Raises:
            HTTPException: 当并发数超限时抛出429错误
        """
        # 检查限制
        if not await self.check_query_limit(user_id):
            raise HTTPException(
                status_code=429, detail="Too many concurrent queries, please try again later"
            )

        # 获取全局semaphore（限制总并发数）
        async with self._query_semaphore:
            # 注册查询
            async with self._query_lock:
                self._active_queries.add(query_id)
                logger.debug(f"🔄 开始查询: {query_id}, 活跃查询数: {len(self._active_queries)}")

            try:
                yield
            finally:
                # 清理查询
                async with self._query_lock:
                    self._active_queries.discard(query_id)
                    logger.debug(
                        f"✅ 完成查询: {query_id}, 剩余查询数: {len(self._active_queries)}"
                    )

    # ========== 内存监控 ==========

    def get_memory_usage_mb(self) -> float:
        """
        获取当前进程内存使用量(MB)

        Returns:
            float: 内存使用量（MB），如果psutil未安装则返回0
        """
        if not PSUTIL_AVAILABLE:
            return 0.0

        try:
            return psutil.Process().memory_info().rss / 1024 / 1024
        except Exception as e:
            logger.error(f"获取内存使用量失败: {e}")
            return 0.0

    def check_memory_limit(self, required_mb: int = 0) -> bool:
        """
        检查内存是否充足

        Args:
            required_mb: 需要的额外内存(MB)

        Returns:
            bool: True表示内存充足，False表示不足
        """
        current_mem = self.get_memory_usage_mb()
        available = self.MAX_MEMORY_MB - current_mem

        if available < required_mb:
            logger.warning(
                f"⚠️  内存不足: 当前={current_mem:.0f}MB, "
                f"需要={required_mb}MB, "
                f"可用={available:.0f}MB, "
                f"上限={self.MAX_MEMORY_MB}MB"
            )
            return False

        return True

    # ========== 状态查询 ==========

    def get_stats(self) -> dict:
        """
        获取资源使用统计

        Returns:
            dict: 资源统计信息
        """
        return {
            "websocket_connections": len(self._websocket_connections),
            "active_queries": len(self._active_queries),
            "memory_mb": round(self.get_memory_usage_mb(), 2),
            "limits": {
                "max_connections": self.MAX_WEBSOCKET_CONNECTIONS,
                "max_connections_per_user": self.MAX_CONNECTIONS_PER_USER,
                "max_queries": self.MAX_CONCURRENT_QUERIES,
                "max_queries_per_user": self.MAX_CONCURRENT_QUERIES_PER_USER,
                "max_memory_mb": self.MAX_MEMORY_MB,
            },
            "utilization": {
                "connections_pct": round(
                    len(self._websocket_connections) / self.MAX_WEBSOCKET_CONNECTIONS * 100, 1
                ),
                "queries_pct": round(
                    len(self._active_queries) / self.MAX_CONCURRENT_QUERIES * 100, 1
                ),
                "memory_pct": round(self.get_memory_usage_mb() / self.MAX_MEMORY_MB * 100, 1),
            },
        }


# ========== 全局单例 ==========

_resource_manager: "ResourceManager" = None


def get_resource_manager() -> ResourceManager:
    """
    获取全局资源管理器单例

    Returns:
        ResourceManager: 全局资源管理器实例
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager
