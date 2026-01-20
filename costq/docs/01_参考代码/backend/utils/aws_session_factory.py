"""AWS Session 工厂 - 支持自动刷新的 AssumeRole 凭证

使用 botocore.credentials.DeferredRefreshableCredentials 实现 AssumeRole 凭证的自动刷新。
这是 AWS SDK 推荐的标准方式，确保长时间运行的应用不会因凭证过期而中断。

参考:
- https://github.com/boto/botocore/blob/develop/botocore/credentials.py
- AWS SDK 最佳实践
"""

import datetime
import threading
from typing import Optional

import boto3
import botocore.credentials
import botocore.session
from dateutil.tz import tzlocal

import logging

logger = logging.getLogger(__name__)


class AWSSessionFactory:
    """AWS Session 工厂类

    为 AssumeRole 创建带自动刷新凭证的 boto3.Session

    核心特性:
    1. 使用 DeferredRefreshableCredentials 实现自动刷新
    2. boto3 会在凭证过期前自动调用 refresh 方法
    3. 线程安全的单例模式
    4. 支持跨账号 AssumeRole

    使用示例:
        factory = AWSSessionFactory.get_instance(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            region="us-west-2"
        )
        session = factory.get_session()
        bedrock_client = session.client('bedrock-runtime')
    """

    _instance: Optional["AWSSessionFactory"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        role_arn: str,
        region: str = "us-west-2",
        role_session_name: str = "bedrock-cross-account-session",
        duration_seconds: int = 3600,
    ):
        """
        Args:
            role_arn: IAM Role ARN (arn:aws:iam::123456789012:role/MyRole)
            region: AWS 区域
            role_session_name: AssumeRole 会话名称
            duration_seconds: 凭证有效期（秒），role chaining 最大 3600
        """
        self.role_arn = role_arn
        self.region = region
        self.role_session_name = role_session_name
        self.duration_seconds = duration_seconds

        # 缓存的 boto3 Session（带自动刷新凭证）
        self._session: boto3.Session | None = None
        self._session_lock = threading.Lock()

        logger.info(
            f"🏭 AWSSessionFactory 初始化 - "
            f"Role: {role_arn}, Region: {region}, Duration: {duration_seconds}s"
        )

    @classmethod
    def get_instance(
        cls,
        role_arn: str,
        region: str = "us-west-2",
        role_session_name: str = "bedrock-cross-account-session",
        duration_seconds: int = 3600,
    ) -> "AWSSessionFactory":
        """获取单例实例

        Args:
            role_arn: IAM Role ARN
            region: AWS 区域
            role_session_name: AssumeRole 会话名称
            duration_seconds: 凭证有效期（秒）

        Returns:
            AWSSessionFactory: 工厂实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(
                        role_arn=role_arn,
                        region=region,
                        role_session_name=role_session_name,
                        duration_seconds=duration_seconds,
                    )
        return cls._instance

    def _create_refreshable_session(self) -> boto3.Session:
        """创建带自动刷新凭证的 boto3 Session

        使用 botocore 的 DeferredRefreshableCredentials 机制。
        boto3 会在凭证过期前自动调用 refresh 方法获取新凭证。

        Returns:
            boto3.Session: 带自动刷新凭证的 Session
        """
        logger.info("🔧 创建 RefreshableSession...")

        # 1. 获取基础 session（使用当前 EKS Pod 的 IAM Role）
        base_session = boto3.Session()._session

        # 2. 获取源凭证（当前 Pod 的 IAM Role 凭证）
        source_credentials = base_session.get_credentials()

        # 3. 准备 AssumeRole 参数
        extra_args = {
            "RoleSessionName": self.role_session_name,
            "DurationSeconds": self.duration_seconds,
        }

        logger.debug(f"  AssumeRole 参数: {extra_args}")

        # 4. 创建 AssumeRoleCredentialFetcher
        #    这个对象知道如何调用 STS AssumeRole API 并解析响应
        fetcher = botocore.credentials.AssumeRoleCredentialFetcher(
            client_creator=base_session.create_client,
            source_credentials=source_credentials,
            role_arn=self.role_arn,
            extra_args=extra_args,
        )

        logger.debug("  ✅ AssumeRoleCredentialFetcher 已创建")

        # 5. 创建 DeferredRefreshableCredentials
        #    这是核心：boto3 会自动调用 refresh_using 刷新凭证
        refreshable_creds = botocore.credentials.DeferredRefreshableCredentials(
            method="assume-role",
            refresh_using=fetcher.fetch_credentials,  # 刷新时调用这个方法
            time_fetcher=lambda: datetime.datetime.now(tzlocal()),
        )

        logger.debug("  ✅ DeferredRefreshableCredentials 已创建")

        # 6. 创建新的 botocore session 并注入可刷新凭证
        botocore_session = botocore.session.Session()
        botocore_session._credentials = refreshable_creds

        # 7. 从 botocore session 创建 boto3 Session
        session = boto3.Session(botocore_session=botocore_session, region_name=self.region)

        logger.info("✅ RefreshableSession 创建成功")
        logger.info(f"   凭证将在过期前自动刷新（Duration: {self.duration_seconds}s）")

        return session

    def get_session(self) -> boto3.Session:
        """获取 boto3 Session（带自动刷新凭证）

        线程安全，单例缓存。

        Returns:
            boto3.Session: boto3 Session
        """
        if self._session is None:
            with self._session_lock:
                if self._session is None:
                    self._session = self._create_refreshable_session()

        return self._session

    def get_client(self, service_name: str, **kwargs):
        """创建 AWS 服务客户端（自动刷新凭证）

        Args:
            service_name: AWS 服务名称（如 'bedrock-runtime', 's3', 'sts'）
            **kwargs: 传递给 client() 的其他参数

        Returns:
            boto3 客户端
        """
        session = self.get_session()
        return session.client(service_name, **kwargs)

    def invalidate_session(self):
        """清除缓存的 Session（强制重新创建）

        用于处理 Session 级别的错误或强制刷新。
        """
        with self._session_lock:
            logger.info("🔄 清除缓存的 Session")
            self._session = None

    @classmethod
    def clear_instance(cls):
        """清除单例实例（用于测试或重新配置）"""
        with cls._lock:
            logger.info("🔄 清除 AWSSessionFactory 单例")
            cls._instance = None
