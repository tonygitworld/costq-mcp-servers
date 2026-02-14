"""数据库操作模块（异步优化版本）

自包含模块，替代 backend.services.account_storage。
通过环境变量获取数据库连接配置。

修复说明：
1. 所有 I/O 操作（boto3 调用、数据库查询）都在线程池中执行，避免阻塞事件循环
2. 使用异步锁保证引擎初始化的线程安全
3. 移除所有敏感信息的日志记录（密码、密钥、连接串等）
"""

import asyncio
import json
import logging
import os
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from .exceptions import AccountNotFoundError, DatabaseConnectionError

logger = logging.getLogger(__name__)

# 全局数据库引擎（单例）
_engine = None
_engine_lock = asyncio.Lock()  # 异步锁


async def _get_database_url() -> str:
    """获取数据库连接 URL（异步版本）

    优先级：
    1. 环境变量 DATABASE_URL
    2. AWS Secrets Manager (RDS_SECRET_NAME) - 异步调用

    Returns:
        数据库连接 URL

    Raises:
        DatabaseConnectionError: 未找到数据库连接信息
    """
    # 优先使用环境变量
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        logger.debug("使用 DATABASE_URL 环境变量")
        return database_url

    # 从 AWS Secrets Manager 读取（异步）
    rds_secret_name = os.getenv("RDS_SECRET_NAME")
    if rds_secret_name:
        try:
            import boto3

            region = os.getenv("AWS_REGION", "ap-northeast-1")

            # 在线程池中执行同步 boto3 调用
            loop = asyncio.get_event_loop()

            def _get_secret():
                client = boto3.client("secretsmanager", region_name=region)
                response = client.get_secret_value(SecretId=rds_secret_name)
                return json.loads(response["SecretString"])

            secret = await loop.run_in_executor(None, _get_secret)

            # 兼容 'database' 和 'dbname' 两种字段名
            dbname = secret.get('database') or secret.get('dbname')
            if not dbname:
                raise DatabaseConnectionError(
                    f"Secret '{rds_secret_name}' 缺少 'database' 或 'dbname' 字段"
                )

            database_url = (
                f"postgresql://{secret['username']}:{secret['password']}"
                f"@{secret['host']}:{secret['port']}/{dbname}"
            )
            # ✅ 只记录密钥名称，不记录连接串（包含密码）
            logger.debug(f"从 Secrets Manager 获取数据库连接: {rds_secret_name}")
            return database_url
        except DatabaseConnectionError:
            # 重新抛出 DatabaseConnectionError，保留原始错误信息
            raise
        except Exception as e:
            raise DatabaseConnectionError(f"读取 Secrets Manager 失败: {e}")

    raise DatabaseConnectionError(
        "未找到数据库连接信息，请设置 DATABASE_URL 或 RDS_SECRET_NAME"
    )


async def _get_engine():
    """获取数据库引擎（单例模式，异步安全）

    Returns:
        SQLAlchemy Engine 实例
    """
    global _engine

    # 使用异步锁保证线程安全
    async with _engine_lock:
        if _engine is None:
            database_url = await _get_database_url()  # 等待异步初始化

            # 在线程池中创建引擎（避免阻塞）
            loop = asyncio.get_event_loop()

            def _create_engine():
                return create_engine(
                    database_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                )

            _engine = await loop.run_in_executor(None, _create_engine)
            logger.info("数据库引擎已初始化")

    return _engine


async def query_account(account_id: str) -> Optional[dict]:
    """查询 AWS 账号信息（异步版本）

    通过 LEFT JOIN organizations 表获取 external_id。

    Args:
        account_id: AWS 账号 ID（数据库主键）

    Returns:
        账号信息字典，不存在则返回 None
        {
            "id": "uuid",
            "account_id": "123456789012",
            "alias": "production",
            "auth_type": "iam_role",  # 或 "aksk"
            "role_arn": "arn:aws:iam::...",  # IAM Role 类型
            "encrypted_secret_key": "...",  # AKSK 类型
            "org_id": "uuid",  # 组织 ID
            "external_id": "org-xxx",  # 从 organizations 表获取（可能为 None）
            "region": "us-east-1"
        }

    Raises:
        DatabaseConnectionError: 数据库查询失败
    """
    try:
        engine = await _get_engine()

        query = text("""
            SELECT
                a.id, a.account_id, a.alias, a.auth_type,
                a.access_key_id, a.secret_access_key_encrypted,
                a.role_arn, a.region, a.org_id,
                o.external_id
            FROM aws_accounts a
            LEFT JOIN organizations o ON a.org_id = o.id
            WHERE a.account_id = :account_id
        """)

        loop = asyncio.get_event_loop()

        def _query_sync():
            with engine.connect() as conn:
                result = conn.execute(query, {"account_id": account_id})
                row = result.fetchone()

                if not row:
                    logger.warning("账号不存在: %s", account_id)
                    return None

                return {
                    "id": str(row.id),
                    "account_id": row.account_id,
                    "alias": row.alias,
                    "auth_type": row.auth_type,
                    "access_key_id": row.access_key_id,
                    "encrypted_secret_key": row.secret_access_key_encrypted,
                    "role_arn": row.role_arn,
                    "region": row.region,
                    "org_id": str(row.org_id) if row.org_id else None,
                    "external_id": row.external_id,
                }

        return await loop.run_in_executor(None, _query_sync)

    except Exception as e:
        if isinstance(e, DatabaseConnectionError):
            raise
        logger.error("数据库查询失败: %s", type(e).__name__)
        raise DatabaseConnectionError(f"查询账号信息失败: {type(e).__name__}")


async def close_connection():
    """关闭数据库连接（异步版本，用于资源清理）"""
    global _engine

    async with _engine_lock:
        if _engine is not None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _engine.dispose)
            _engine = None
            logger.info("数据库连接已关闭")
