"""IAM Role Session 工厂 - 为客户 IAM Role 创建可自动刷新凭证的 Session

基于 backend/utils/aws_session_factory.py 的成熟实现，适配客户 IAM Role 的多账号场景。

核心特性：
1. 使用 DeferredRefreshableCredentials 实现自动刷新
2. boto3 会在凭证过期前自动调用 refresh 方法
3. 支持多账号（每个 account_id 独立实例）
4. 支持 ExternalId 安全验证
5. 线程安全

与 Bedrock SessionFactory 的区别：
- Bedrock: 单例模式，一个 Role（平台 Bedrock 账号）
- IAM Role: 多实例，多个 Role（客户账号），需要 ExternalId

参考：
- backend/utils/aws_session_factory.py
- https://github.com/boto/botocore/blob/develop/botocore/credentials.py
- AWS SDK 最佳实践
"""

import datetime
import threading

import boto3
import botocore.credentials
import botocore.session
from dateutil.tz import tzlocal
import logging

logger = logging.getLogger(__name__)


class IAMRoleSessionFactory:
    """为客户 IAM Role 创建可自动刷新凭证的 Session

    每个客户账号有独立的 SessionFactory 实例，Session 内部自动刷新凭证。

    使用示例：
        factory = IAMRoleSessionFactory.get_instance(
            account_id="account-123",
            role_arn="arn:aws:iam::123456789012:role/CostQRole",
            external_id="unique-external-id",
            region="us-east-1"
        )

        # 获取当前有效凭证（自动刷新）
        credentials = factory.get_current_credentials()

        # 或直接获取 Session
        session = factory.get_session()
        ce_client = session.client('ce')
    """

    # 多账号实例缓存：{account_id: IAMRoleSessionFactory}
    _instances: dict[str, "IAMRoleSessionFactory"] = {}
    _instances_lock = threading.Lock()

    def __init__(
        self,
        account_id: str,
        role_arn: str,
        external_id: str,
        region: str = "us-east-1",
        duration_seconds: int = 3600,
    ):
        """初始化 IAM Role Session Factory

        Args:
            account_id: 账号 ID（数据库唯一标识）
            role_arn: 客户的 IAM Role ARN
            external_id: 组织的 External ID（防止混淆代理人攻击）
            region: AWS 区域
            duration_seconds: 凭证有效期（秒），默认 3600（1小时）
        """
        self.account_id = account_id
        self.role_arn = role_arn
        self.external_id = external_id
        self.region = region
        self.duration_seconds = duration_seconds

        # 缓存的 boto3 Session（带自动刷新凭证）
        self._session: boto3.Session | None = None
        self._session_lock = threading.Lock()

        logger.info(
            f"🏭 IAMRoleSessionFactory 初始化 - "
            f"Account: {account_id}, Role: {role_arn}, "
            f"Region: {region}, Duration: {duration_seconds}s"
        )

    @classmethod
    def get_instance(
        cls,
        account_id: str,
        role_arn: str,
        external_id: str,
        region: str = "us-east-1",
        duration_seconds: int = 3600,
    ) -> "IAMRoleSessionFactory":
        """获取指定账号的 SessionFactory 实例（多实例模式）

        每个 account_id 有独立的实例，线程安全。

        Args:
            account_id: 账号 ID
            role_arn: IAM Role ARN
            external_id: External ID
            region: AWS 区域
            duration_seconds: 凭证有效期（秒）

        Returns:
            IAMRoleSessionFactory: 工厂实例
        """
        if account_id not in cls._instances:
            with cls._instances_lock:
                # Double-check locking
                if account_id not in cls._instances:
                    cls._instances[account_id] = cls(
                        account_id=account_id,
                        role_arn=role_arn,
                        external_id=external_id,
                        region=region,
                        duration_seconds=duration_seconds,
                    )
        return cls._instances[account_id]

    @classmethod
    def clear_instance(cls, account_id: str):
        """清除指定账号的实例（用于账号删除或更新）

        Args:
            account_id: 账号 ID
        """
        with cls._instances_lock:
            if account_id in cls._instances:
                logger.info(
                    f"🔄 清除 IAMRoleSessionFactory 实例 - Account: {account_id}"
                )
                del cls._instances[account_id]

    @classmethod
    def clear_all_instances(cls):
        """清除所有实例（用于测试或重新配置）"""
        with cls._instances_lock:
            logger.info("🔄 清除所有 IAMRoleSessionFactory 实例")
            cls._instances.clear()

    def _create_refreshable_session(self) -> boto3.Session:
        """创建带自动刷新凭证的 boto3 Session

        核心逻辑完全复用 backend/utils/aws_session_factory.py，
        唯一区别是在 extra_args 中增加 ExternalId 参数。

        Returns:
            boto3.Session: 带自动刷新凭证的 Session
        """
        logger.info(f"🔧 创建 RefreshableSession - Account: {self.account_id}...")

        # 1. 获取基础 session（使用当前 EKS Pod 的 IAM Role）
        base_session = boto3.Session()._session

        # 2. 获取源凭证（当前 Pod 的 IAM Role 凭证）
        source_credentials = base_session.get_credentials()

        # 3. 准备 AssumeRole 参数（与 Bedrock 的区别：增加 ExternalId）
        extra_args = {
            "RoleSessionName": f"costq-{self.account_id}",
            "DurationSeconds": self.duration_seconds,
            "ExternalId": self.external_id,  # ⭐ 客户 IAM Role 必须的安全参数
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
        #    默认在凭证过期前 10 分钟自动刷新
        refreshable_creds = botocore.credentials.DeferredRefreshableCredentials(
            method="assume-role",
            refresh_using=fetcher.fetch_credentials,  # boto3 自动调用
            time_fetcher=lambda: datetime.datetime.now(tzlocal()),
        )

        logger.debug("  ✅ DeferredRefreshableCredentials 已创建")

        # 6. 创建新的 botocore session 并注入可刷新凭证
        botocore_session = botocore.session.Session()
        botocore_session._credentials = refreshable_creds

        # 7. 从 botocore session 创建 boto3 Session
        session = boto3.Session(
            botocore_session=botocore_session, region_name=self.region
        )

        logger.info(
            f"✅ RefreshableSession 创建成功 - Account: {self.account_id}, "
            f"凭证将在过期前自动刷新（Duration: {self.duration_seconds}s）"
        )

        return session

    def get_session(self) -> boto3.Session:
        """获取 boto3 Session（带自动刷新凭证）

        线程安全，懒加载。Session 内部会自动刷新凭证。

        Returns:
            boto3.Session: boto3 Session
        """
        if self._session is None:
            with self._session_lock:
                # Double-check locking
                if self._session is None:
                    self._session = self._create_refreshable_session()

        return self._session

    def get_current_credentials(self) -> dict:
        """获取当前有效的凭证（自动刷新）

        从 Session 中提取当前快照的凭证。如果 boto3 已自动刷新，
        返回的就是新凭证。

        这是关键方法：用于设置环境变量给 MCP Server。

        Returns:
            dict: 凭证字典
                {
                    'access_key_id': str,
                    'secret_access_key': str,
                    'session_token': str,  # 临时凭证
                    'region': str,
                    'auth_type': 'iam_role'
                }
        """
        session = self.get_session()

        # ⭐ 关键：boto3 会自动刷新凭证
        # get_credentials() 返回的是当前有效凭证对象
        creds = session.get_credentials()

        # get_frozen_credentials() 返回当前快照
        # 如果 boto3 已刷新凭证，这里拿到的就是新凭证
        frozen = creds.get_frozen_credentials()

        logger.debug(
            f"📋 获取当前凭证 - Account: {self.account_id}, "
            f"Token: {frozen.token[:20] if frozen.token else 'None'}..."
        )

        return {
            "access_key_id": frozen.access_key,
            "secret_access_key": frozen.secret_key,
            "session_token": frozen.token,  # 自动刷新后的最新 token
            "region": self.region,
            "auth_type": "iam_role",
        }

    def invalidate_session(self):
        """清除缓存的 Session（强制重新创建）

        用于处理 Session 级别的错误或强制刷新。
        """
        with self._session_lock:
            logger.info(f"🔄 清除缓存的 Session - Account: {self.account_id}")
            self._session = None

    def get_client(self, service_name: str, **kwargs):
        """创建 AWS 服务客户端（自动刷新凭证）

        Args:
            service_name: AWS 服务名称（如 'ce', 's3', 'sts'）
            **kwargs: 传递给 client() 的其他参数

        Returns:
            boto3 客户端
        """
        session = self.get_session()
        return session.client(service_name, **kwargs)
