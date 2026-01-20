"""AWS 凭证提供服务 - 供 MCP 工具使用

该服务负责：
1. 根据 account_id 从数据库获取账号信息
2. 解密 Secret Access Key
3. 创建 boto3 Session 或返回凭证字典
4. 支持生产环境使用 IAM Role（EC2 实例角色）
"""

import boto3
import logging

from backend.config.settings import settings

from .account_storage import get_account_storage
from .credential_manager import get_credential_manager

logger = logging.getLogger(__name__)


class AWSCredentialsProvider:
    """AWS 凭证提供服务

    为 MCP 工具提供解密后的 AWS 凭证。

    支持两种模式：
    1. 本地环境：使用数据库存储的 AKSK
    2. 生产环境（EC2）：使用 IAM Role（自动从实例元数据获取）
    """

    def __init__(self):
        self.credential_manager = get_credential_manager()
        self.account_storage = get_account_storage()
        self.use_iam_role = settings.use_iam_role
        # logger.info("✅ AWS 凭证提供服务初始化完成")  # 已静默 - 每次查询都重复

    def create_session_with_iam_role(self, region: str | None = None) -> boto3.Session:
        """
        使用 IAM Role 创建 boto3 Session（生产环境）

        Args:
            region: AWS 区域，默认使用生产区域配置

        Returns:
            boto3.Session: 使用 IAM Role 的 Session

        Note:
            EC2 实例会自动从实例元数据服务获取临时凭证
        """
        region_name = region or settings.AWS_REGION

        try:
            # 不指定凭证，boto3 会自动使用 IAM Role
            session = boto3.Session(region_name=region_name)

            logger.info(
                f"✅ 使用 IAM Role 创建 Session - "
                f"Region: {region_name}, "
                f"Environment: {settings.ENVIRONMENT}"
            )

            return session

        except Exception as e:
            logger.error(f"❌ IAM Role Session 创建失败: {e}")
            raise

    def get_credentials(self, account_id: str) -> dict[str, str]:
        """获取指定账号的凭证（支持 AKSK 和 IAM Role）

        Args:
            account_id: 账号 ID

        Returns:
            Dict: 凭证字典
                {
                    'access_key_id': 'AKIA...',
                    'secret_access_key': 'wJalr...',
                    'session_token': 'FwoGZXIv...' (IAM Role才有),
                    'region': 'us-east-1',
                    'account_id': '123456789012',
                    'auth_type': 'aksk' | 'iam_role'
                }

        Raises:
            ValueError: 账号不存在或凭证获取失败

        Example:
            >>> provider = AWSCredentialsProvider()
            >>> creds = provider.get_credentials('account-id-123')
            >>> print(creds['region'])
            'us-east-1'
        """
        # 1. 从数据库获取账号
        account = self.account_storage.get_account(account_id)

        if not account:
            logger.error(f"❌ 账号不存在 - ID: {account_id}")
            raise ValueError(f"账号不存在: {account_id}")

        auth_type = account.get("auth_type", "aksk")
        logger.info(
            f"🔍 获取凭证 - Account: {account.get('alias')} "
            f"({account.get('account_id')}), Type: {auth_type}"
        )

        # 2. 根据认证类型获取凭证
        if auth_type == "iam_role":
            # IAM Role: 使用 SessionFactory 获取自动刷新的凭证
            try:
                from backend.services.iam_role_session_factory import (
                    IAMRoleSessionFactory,
                )
                from backend.services.user_storage_postgresql import (
                    UserStoragePostgreSQL,
                )

                user_storage = UserStoragePostgreSQL()

                # 获取 External ID
                external_id = user_storage.get_organization_external_id(
                    account["org_id"]
                )

                # 获取或创建 SessionFactory（自动刷新凭证）
                factory = IAMRoleSessionFactory.get_instance(
                    account_id=account_id,
                    role_arn=account["role_arn"],
                    external_id=external_id,
                    region=account["region"],
                    duration_seconds=account.get("session_duration", 3600),
                )

                # ⭐ 关键：从 Session 中获取当前有效凭证（自动刷新）
                credentials = factory.get_current_credentials()

                # 补充账号信息
                credentials["account_id"] = account.get("account_id")
                credentials["alias"] = account.get("alias")

                logger.info(
                    f"✅ IAM Role 凭证获取成功（自动刷新）- Account: {account.get('alias')}"
                )

            except Exception as e:
                logger.error(
                    f"❌ IAM Role 凭证获取失败 - Account: {account.get('alias')}, Error: {e}"
                )
                raise ValueError(f"IAM Role 凭证获取失败: {str(e)}")

        else:
            # AKSK: 解密 Secret Access Key
            try:
                secret_access_key = self.credential_manager.decrypt_secret_key(
                    account["secret_access_key_encrypted"]
                )
            except Exception as e:
                logger.error(
                    f"❌ AKSK 凭证解密失败 - Account: {account.get('alias')}, Error: {e}"
                )
                raise ValueError(f"凭证解密失败: {str(e)}")

            credentials = {
                "access_key_id": account["access_key_id"],
                "secret_access_key": secret_access_key,
                "region": account["region"],
                "account_id": account.get("account_id"),
                "alias": account.get("alias"),
                "auth_type": "aksk",
            }

            logger.debug(
                f"✅ AKSK 凭证获取成功 - Account: {account.get('alias')}, "
                f"Region: {account['region']}"
            )

        return credentials

    def create_session(self, account_id: str) -> boto3.Session:
        """为指定账号创建 boto3 Session

        Args:
            account_id: 账号 ID

        Returns:
            boto3.Session: AWS Session 对象

        Raises:
            ValueError: 账号不存在或凭证无效

        Example:
            >>> provider = AWSCredentialsProvider()
            >>> session = provider.create_session('account-id-123')
            >>> ce_client = session.client('ce')

        Note:
            生产环境（EC2）: 使用 IAM Role，忽略 account_id
            本地环境: 使用数据库中的 AKSK
        """
        # 生产环境使用 IAM Role
        if self.use_iam_role:
            logger.info(f"🔐 生产环境 - 使用 IAM Role (忽略 account_id: {account_id})")
            # 获取账号信息仅用于记录
            try:
                account = self.account_storage.get_account(account_id)
                region = account.region if account else settings.AWS_REGION
            except:
                region = settings.AWS_REGION

            return self.create_session_with_iam_role(region)

        # 本地环境使用 AKSK
        credentials = self.get_credentials(account_id)

        try:
            session = boto3.Session(
                aws_access_key_id=credentials["access_key_id"],
                aws_secret_access_key=credentials["secret_access_key"],
                region_name=credentials["region"],
            )

            logger.debug(
                f"✅ Session 创建成功（AKSK）- Account: {credentials['alias']}, "
                f"Region: {credentials['region']}"
            )

            return session

        except Exception as e:
            logger.error(
                f"❌ Session 创建失败 - Account: {credentials['alias']}, Error: {e}"
            )
            raise ValueError(f"Session 创建失败: {str(e)}")

    def create_client(
        self,
        service_name: str,
        account_id: str | None = None,
        region_name: str | None = None,
    ):
        """
        创建 AWS 服务客户端（自动适配 IAM Role 或 AKSK）

        Args:
            service_name: AWS 服务名称（如 's3', 'secretsmanager', 'ce'）
            account_id: 账号 ID（本地环境需要，生产环境可选）
            region_name: AWS 区域（可选，默认使用账号配置或生产区域）

        Returns:
            boto3 客户端对象

        Example:
            >>> provider = get_credentials_provider()
            >>> # 生产环境（自动使用 IAM Role）
            >>> s3_client = provider.create_client('s3')
            >>> # 本地环境
            >>> s3_client = provider.create_client('s3', account_id='xxx')
        """
        # 生产环境使用 IAM Role
        if self.use_iam_role:
            region = region_name or settings.AWS_REGION
            session = self.create_session_with_iam_role(region)
            client = session.client(service_name)
            logger.debug(
                f"✅ 客户端创建成功（IAM Role）- Service: {service_name}, Region: {region}"
            )
            return client

        # 本地环境使用 AKSK
        if not account_id:
            raise ValueError("本地环境必须提供 account_id")

        session = self.create_session(account_id)

        # 使用指定区域或账号默认区域
        if region_name:
            client = session.client(service_name, region_name=region_name)
        else:
            client = session.client(service_name)

        logger.debug(
            f"✅ 客户端创建成功（AKSK）- Service: {service_name}, Account: {account_id}"
        )
        return client

    def get_batch_credentials(
        self, account_ids: list[str]
    ) -> dict[str, dict[str, str]]:
        """批量获取多个账号的凭证

        Args:
            account_ids: 账号 ID 列表

        Returns:
            Dict: 账号 ID -> 凭证字典的映射
                {
                    'account-id-1': {'access_key_id': '...', ...},
                    'account-id-2': {'access_key_id': '...', ...}
                }

        Note:
            如果某个账号获取失败，会记录错误但继续处理其他账号

        Example:
            >>> provider = AWSCredentialsProvider()
            >>> creds = provider.get_batch_credentials(['id1', 'id2'])
            >>> for acc_id, cred in creds.items():
            ...     print(f"{acc_id}: {cred['region']}")
        """
        logger.info(f"📋 批量获取凭证 - 共 {len(account_ids)} 个账号")

        credentials_map = {}

        for account_id in account_ids:
            try:
                credentials = self.get_credentials(account_id)
                credentials_map[account_id] = credentials
            except Exception as e:
                logger.error(f"⚠️  账号 {account_id} 凭证获取失败，跳过: {e}")
                # 继续处理其他账号
                continue

        logger.info(
            f"✅ 批量获取完成 - 成功: {len(credentials_map)}/{len(account_ids)}"
        )

        return credentials_map

    def validate_account(self, account_id: str) -> bool:
        """验证账号凭证是否有效

        Args:
            account_id: 账号 ID

        Returns:
            bool: 凭证是否有效

        Example:
            >>> provider = AWSCredentialsProvider()
            >>> if provider.validate_account('account-id-123'):
            ...     print("凭证有效")
        """
        try:
            credentials = self.get_credentials(account_id)

            # 使用凭证管理器验证
            validation = self.credential_manager.validate_credentials(
                credentials["access_key_id"],
                credentials["secret_access_key"],
                credentials["region"],
            )

            if validation["valid"]:
                logger.info(f"✅ 账号凭证有效 - Account: {credentials['alias']}")
                return True
            else:
                logger.error(
                    f"❌ 账号凭证无效 - Account: {credentials['alias']}, "
                    f"Error: {validation['error']}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ 账号验证失败 - ID: {account_id}, Error: {e}")
            return False

    def get_account_info(self, account_id: str) -> dict | None:
        """获取账号基本信息（不包含敏感凭证）

        Args:
            account_id: 账号 ID

        Returns:
            Optional[Dict]: 账号信息
                {
                    'id': 'account-id-123',
                    'alias': 'Production Account',
                    'account_id': '123456789012',
                    'region': 'us-east-1'
                }

        Example:
            >>> provider = AWSCredentialsProvider()
            >>> info = provider.get_account_info('account-id-123')
            >>> print(info['alias'])
            'Production Account'
        """
        account = self.account_storage.get_account(account_id)

        if not account:
            return None

        return {
            "id": account["id"],
            "alias": account.get("alias"),
            "account_id": account.get("account_id"),
            "region": account["region"],
            "description": account.get("description"),
            "is_verified": account.get("is_verified", False),
        }


# 全局单例
_credentials_provider: AWSCredentialsProvider | None = None


def get_credentials_provider() -> AWSCredentialsProvider:
    """获取全局凭证提供服务单例

    Returns:
        AWSCredentialsProvider: 凭证提供服务实例

    Example:
        >>> provider = get_credentials_provider()
        >>> creds = provider.get_credentials('account-id-123')
    """
    global _credentials_provider

    if _credentials_provider is None:
        _credentials_provider = AWSCredentialsProvider()

    return _credentials_provider


# ========== IAM Role 相关功能 ==========


def validate_iam_role(
    role_arn: str, external_id: str, region: str = "us-east-1"
) -> dict[str, any]:
    """验证 IAM Role（通过尝试 AssumeRole）

    Args:
        role_arn: IAM Role ARN (例如: arn:aws:iam::123456789012:role/CostQRole)
        external_id: External ID（用于防止混淆代理人攻击）
        region: AWS 区域

    Returns:
        Dict: 验证结果
            {
                'valid': bool,
                'account_id': str,  # 如果成功
                'arn': str,         # 如果成功
                'error': str        # 如果失败
            }
    """
    try:
        # 创建 STS 客户端（使用平台自己的凭证）
        sts = boto3.client("sts", region_name=region)

        # 尝试 AssumeRole
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="costq-validation",
            ExternalId=external_id,
            DurationSeconds=900,  # 15 分钟，仅用于验证
        )

        # 从 AssumedRole ARN 提取 Account ID
        # 格式: arn:aws:sts::123456789012:assumed-role/RoleName/SessionName
        assumed_role_arn = response["AssumedRoleUser"]["Arn"]
        account_id = assumed_role_arn.split(":")[4]

        logger.info(f"✅ IAM Role 验证成功 - ARN: {role_arn}, Account: {account_id}")

        return {"valid": True, "account_id": account_id, "arn": role_arn}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ IAM Role 验证失败 - ARN: {role_arn}, Error: {error_msg}")

        return {"valid": False, "error": error_msg}


def create_session_with_customer_iam_role(
    role_arn: str,
    external_id: str,
    session_duration: int = 3600,
    region: str = "us-east-1",
) -> boto3.Session:
    """使用客户的 IAM Role 创建 boto3 Session

    通过 AssumeRole 获取临时凭证，创建 Session。

    Args:
        role_arn: IAM Role ARN
        external_id: External ID
        session_duration: 会话时长（秒），范围 900-43200
        region: AWS 区域

    Returns:
        boto3.Session: 使用临时凭证的 Session

    Raises:
        Exception: AssumeRole 失败时抛出
    """
    import time

    try:
        # 创建 STS 客户端
        sts = boto3.client("sts", region_name=region)

        # AssumeRole
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"costq-session-{int(time.time())}",
            ExternalId=external_id,
            DurationSeconds=session_duration,
        )

        # 提取临时凭证
        credentials = response["Credentials"]

        # 创建 Session
        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=region,
        )

        logger.info(
            f"✅ IAM Role Session 创建成功 - "
            f"ARN: {role_arn}, "
            f"Duration: {session_duration}s, "
            f"Expires: {credentials['Expiration']}"
        )

        return session

    except Exception as e:
        logger.error(f"❌ IAM Role Session 创建失败 - ARN: {role_arn}, Error: {e}")
        raise
