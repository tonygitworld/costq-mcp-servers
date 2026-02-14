"""Database connection helpers for GCP MCP server.

Provides a synchronous SQLAlchemy session factory using DATABASE_URL or
RDS_SECRET_NAME from AWS Secrets Manager.
"""

import json
import logging
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None
_ScopedSession = None


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        logger.info("✅ 使用 DATABASE_URL 环境变量连接数据库")
        return database_url

    rds_secret_name = os.getenv("RDS_SECRET_NAME")
    if not rds_secret_name:
        raise RuntimeError("未找到数据库连接信息，请设置 DATABASE_URL 或 RDS_SECRET_NAME")

    region = os.getenv("AWS_REGION", "ap-northeast-1")
    try:
        import boto3

        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=rds_secret_name)
        secret = json.loads(response["SecretString"])
        dbname = secret.get("database") or secret.get("dbname")
        if not dbname:
            raise RuntimeError(f"Secret '{rds_secret_name}' 缺少 'database' 或 'dbname' 字段")

        database_url = (
            f"postgresql://{secret['username']}:{secret['password']}"
            f"@{secret['host']}:{secret['port']}/{dbname}"
        )
        logger.info("✅ 使用 Secrets Manager 获取数据库连接")
        return database_url
    except Exception as e:
        raise RuntimeError(f"读取 Secrets Manager 失败: {e}")


def _init_engine() -> None:
    global _engine, _SessionLocal, _ScopedSession

    if _engine is not None:
        return

    database_url = _get_database_url()
    _engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    _ScopedSession = scoped_session(_SessionLocal)
    logger.info("✅ 数据库引擎初始化完成")


def get_db() -> Generator:
    _init_engine()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
