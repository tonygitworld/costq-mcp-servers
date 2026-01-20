"""AWS 账号存储服务 - PostgreSQL 实现（生产环境）"""

from datetime import datetime

import logging
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.database import get_db
from backend.models.aws_account import AWSAccount

logger = logging.getLogger(__name__)


class AccountStoragePostgreSQL:
    """AWS 账号存储服务 - PostgreSQL 实现

    用于生产环境，使用 SQLAlchemy 连接 RDS PostgreSQL
    """

    def __init__(self):
        """初始化存储服务"""
        logger.info("✅ AWS账号存储初始化完成 - PostgreSQL (生产环境)")

    def _get_db(self):
        """获取数据库会话"""
        return next(get_db())

    def create_account(self, account: AWSAccount) -> AWSAccount:
        """创建AWS账号

        Args:
            account: AWS账号对象

        Returns:
            AWSAccount: 创建后的账号对象

        Raises:
            ValueError: 如果账号别名已存在
        """
        db = self._get_db()
        try:
            # 检查别名是否已存在
            existing = db.execute(
                text(
                    "SELECT id FROM aws_accounts WHERE org_id = :org_id AND alias = :alias"
                ),
                {"org_id": account.org_id, "alias": account.alias},
            ).fetchone()

            if existing:
                raise ValueError(f"账号别名 '{account.alias}' 在当前组织内已存在")

            # 插入新账号
            db.execute(
                text(
                    """
                INSERT INTO aws_accounts (
                    id, org_id, alias, access_key_id, secret_access_key_encrypted,
                    region, description, account_id, arn,
                    auth_type, role_arn, session_duration,
                    created_at, updated_at, is_verified
                ) VALUES (
                    :id, :org_id, :alias, :access_key_id, :secret_access_key_encrypted,
                    :region, :description, :account_id, :arn,
                    :auth_type, :role_arn, :session_duration,
                    :created_at, :updated_at, :is_verified
                )
            """
                ),
                {
                    "id": account.id,
                    "org_id": account.org_id,
                    "alias": account.alias,
                    "access_key_id": account.access_key_id,
                    "secret_access_key_encrypted": account.secret_access_key_encrypted,
                    "region": account.region,
                    "description": account.description,
                    "account_id": account.account_id,
                    "arn": account.arn,
                    "auth_type": (
                        account.auth_type.value if account.auth_type else "aksk"
                    ),
                    "role_arn": account.role_arn,
                    "session_duration": account.session_duration or 3600,
                    "created_at": account.created_at,
                    "updated_at": account.updated_at,
                    "is_verified": account.is_verified,
                },
            )

            db.commit()
            logger.info(
                f"✅ 账号创建成功 - Org: {account.org_id}, ID: {account.id}, Alias: {account.alias}"
            )
            return account

        except IntegrityError as e:
            db.rollback()
            logger.error(f"❌ 账号创建失败: {e}")
            raise ValueError(f"账号创建失败: {str(e)}")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 账号创建失败: {e}")
            raise
        finally:
            db.close()

    def list_accounts(self, org_id: str, user_id: str | None = None) -> list[dict]:
        """获取账号列表

        Args:
            org_id: 组织ID
            user_id: 用户ID（可选，用于权限过滤）

        Returns:
            List[dict]: 账号列表
        """
        db = self._get_db()
        try:
            # 查询该组织的所有账号
            result = db.execute(
                text(
                    "SELECT * FROM aws_accounts WHERE org_id = :org_id ORDER BY created_at DESC"
                ),
                {"org_id": org_id},
            )

            accounts = []
            for row in result:
                row_dict = dict(row._mapping)
                # 转换UUID为字符串
                for key, value in row_dict.items():
                    if hasattr(value, "hex"):  # UUID对象
                        row_dict[key] = str(value)
                accounts.append(row_dict)

            logger.debug(f"📋 获取账号列表 - Org: {org_id}, 共 {len(accounts)} 个账号")
            return accounts

        finally:
            db.close()

    def get_account(self, account_id: str, org_id: str | None = None) -> dict | None:
        """获取单个账号

        Args:
            account_id: 账号ID
            org_id: 组织ID（可选，用于验证）

        Returns:
            Optional[dict]: 账号信息，如果不存在返回None
        """
        db = self._get_db()
        try:
            query = "SELECT * FROM aws_accounts WHERE id = :id"
            params = {"id": account_id}

            if org_id:
                query += " AND org_id = :org_id"
                params["org_id"] = org_id

            result = db.execute(text(query), params)
            row = result.fetchone()

            if not row:
                return None

            row_dict = dict(row._mapping)
            # 转换UUID为字符串
            for key, value in row_dict.items():
                if hasattr(value, "hex"):
                    row_dict[key] = str(value)

            return row_dict

        finally:
            db.close()

    def get_account_by_alias(self, org_id: str, alias: str) -> dict | None:
        """根据别名获取账号

        Args:
            org_id: 组织ID
            alias: 账号别名

        Returns:
            Optional[dict]: 账号信息，如果不存在返回None
        """
        db = self._get_db()
        try:
            result = db.execute(
                text(
                    "SELECT * FROM aws_accounts WHERE org_id = :org_id AND alias = :alias"
                ),
                {"org_id": org_id, "alias": alias},
            )
            row = result.fetchone()

            if not row:
                return None

            row_dict = dict(row._mapping)
            # 转换UUID为字符串
            for key, value in row_dict.items():
                if hasattr(value, "hex"):
                    row_dict[key] = str(value)

            return row_dict

        finally:
            db.close()

    def update_account(
        self,
        account_id: str,
        org_id: str,
        alias: str | None = None,
        access_key_id: str | None = None,
        secret_access_key_encrypted: str | None = None,
        region: str | None = None,
        description: str | None = None,
        is_verified: bool | None = None,
    ) -> dict | None:
        """更新账号信息

        Args:
            account_id: 账号ID
            org_id: 组织ID
            alias: 新的别名
            access_key_id: 新的Access Key ID
            secret_access_key_encrypted: 新的加密Secret Key
            region: 新的默认区域
            description: 新的描述
            is_verified: 新的验证状态

        Returns:
            Optional[dict]: 更新后的账号信息

        Raises:
            ValueError: 如果账号不存在或别名冲突
        """
        db = self._get_db()
        try:
            # 检查账号是否存在
            account = self.get_account(account_id, org_id)
            if not account:
                raise ValueError(f"账号不存在: {account_id}")

            # 如果更新别名，检查是否冲突
            if alias and alias != account.get("alias"):
                existing = self.get_account_by_alias(org_id, alias)
                if existing and existing["id"] != account_id:
                    raise ValueError(f"账号别名 '{alias}' 在当前组织内已存在")

            # 构建更新语句
            updates = []
            params = {
                "id": account_id,
                "org_id": org_id,
                "updated_at": datetime.utcnow(),
            }

            if alias:
                updates.append("alias = :alias")
                params["alias"] = alias
            if access_key_id:
                updates.append("access_key_id = :access_key_id")
                params["access_key_id"] = access_key_id
            if secret_access_key_encrypted:
                updates.append(
                    "secret_access_key_encrypted = :secret_access_key_encrypted"
                )
                params["secret_access_key_encrypted"] = secret_access_key_encrypted
            if region:
                updates.append("region = :region")
                params["region"] = region
            if description is not None:
                updates.append("description = :description")
                params["description"] = description
            if is_verified is not None:
                updates.append("is_verified = :is_verified")
                params["is_verified"] = is_verified

            if not updates:
                return account

            updates.append("updated_at = :updated_at")

            query = f"UPDATE aws_accounts SET {', '.join(updates)} WHERE id = :id AND org_id = :org_id"
            db.execute(text(query), params)
            db.commit()

            logger.info(f"✅ 账号更新成功 - ID: {account_id}")
            return self.get_account(account_id, org_id)

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 账号更新失败: {e}")
            raise
        finally:
            db.close()

    def delete_account(self, account_id: str, org_id: str) -> bool:
        """删除账号

        Args:
            account_id: 账号ID
            org_id: 组织ID

        Returns:
            bool: 是否删除成功
        """
        db = self._get_db()
        try:
            result = db.execute(
                text("DELETE FROM aws_accounts WHERE id = :id AND org_id = :org_id"),
                {"id": account_id, "org_id": org_id},
            )
            db.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"✅ 账号删除成功 - ID: {account_id}")
            else:
                logger.warning(f"⚠️  账号不存在或无权限删除 - ID: {account_id}")

            return deleted

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 账号删除失败: {e}")
            raise
        finally:
            db.close()

    def get_statistics(self) -> dict:
        """获取统计信息

        Returns:
            dict: 统计数据
        """
        db = self._get_db()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM aws_accounts"))
            total = result.scalar()

            result = db.execute(text("SELECT COUNT(DISTINCT org_id) FROM aws_accounts"))
            orgs = result.scalar()

            return {"total_accounts": total, "total_organizations": orgs}

        finally:
            db.close()
