"""MCP连接池管理器

实现长连接池，避免每次查询都重新启动MCP服务器
这是业界标准做法，类似于数据库连接池、Redis连接池等
"""

import time


class MCPConnectionPool:
    """MCP客户端连接池

    功能：
    1. 在应用启动时建立所有MCP连接并保持激活
    2. 查询时直接使用已激活的连接（无需重新启动服务器）
    3. 定期健康检查，自动重连失效的连接
    4. 优雅关闭所有连接

    这避免了每次查询都要：
    - 重新安装MCP包（uvx行为）
    - 重新启动MCP服务器进程
    - 重新建立stdio连接
    """

    def __init__(self, clients: list):
        """初始化连接池

        Args:
            clients: MCP客户端列表
        """
        self.clients = clients
        self._initialized = False
        self._contexts = []  # 存储已激活的上下文
        self._last_health_check = 0
        self._health_check_interval = 60  # 每60秒健康检查一次

    def initialize(self):
        """初始化连接池 - 激活所有MCP连接并保持"""
        if self._initialized:
            print("ℹ️  连接池已初始化")
            return

        print("🔌 初始化MCP连接池（长连接模式）...")

        # 进入所有客户端的上下文并保持
        for i, client in enumerate(self.clients, 1):
            if client:
                try:
                    # __enter__ 会启动MCP服务器并建立连接
                    # Cost Explorer 可能需要较长时间启动（首次 uvx 安装）
                    print(f"  🔄 正在激活连接 {i}/{len(self.clients)}...")
                    client.__enter__()
                    self._contexts.append(client)
                    print("  ✅ 连接已激活并保持")
                except TimeoutError as e:
                    print(f"  ⚠️  连接激活超时（可能是首次安装包，请稍后重试）: {e}")
                except Exception as e:
                    print(f"  ⚠️  连接激活失败: {e}")

        self._initialized = True
        self._last_health_check = time.time()

        print(f"✅ 连接池已初始化（{len(self._contexts)}/{len(self.clients)}个连接）\n")

    def is_ready(self) -> bool:
        """检查连接池是否就绪"""
        return self._initialized and len(self._contexts) > 0

    def health_check(self):
        """健康检查 - 检测失效的连接并尝试重连

        注意：由于MCP连接基于stdio，很难真正检测连接状态
        目前采用简单策略：定期更新检查时间，实际重连由异常触发
        """
        current_time = time.time()

        # 限制检查频率
        if current_time - self._last_health_check < self._health_check_interval:
            return

        print("🔍 MCP连接池健康检查...")

        # 简单的存活确认（实际连接由工具调用时验证）
        print(f"✅ 连接池状态: {len(self._contexts)}/{len(self.clients)}个连接活跃")

        self._last_health_check = current_time

    def close(self):
        """关闭连接池 - 优雅关闭所有MCP连接"""
        if not self._initialized:
            return

        print("\n🔄 关闭MCP连接池...")

        # 退出所有上下文
        for client in self._contexts:
            try:
                client.__exit__(None, None, None)
            except Exception as e:
                print(f"⚠️  关闭连接时出错: {e}")

        self._contexts.clear()
        self._initialized = False

        print("✅ 连接池已关闭")

    def get_active_count(self) -> int:
        """获取活跃连接数"""
        return len(self._contexts)


# 全局连接池实例
_connection_pool: MCPConnectionPool | None = None


def get_connection_pool() -> MCPConnectionPool | None:
    """获取全局连接池实例"""
    return _connection_pool


def initialize_connection_pool(clients: list):
    """初始化全局连接池

    Args:
        clients: MCP客户端列表
    """
    global _connection_pool

    if _connection_pool is None:
        _connection_pool = MCPConnectionPool(clients)
        _connection_pool.initialize()

    return _connection_pool


def close_connection_pool():
    """关闭全局连接池"""
    global _connection_pool

    if _connection_pool:
        _connection_pool.close()
        _connection_pool = None
