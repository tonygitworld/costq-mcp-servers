"""用户存储服务 - PostgreSQL 实现（生产环境）"""

import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from backend.database import get_db
from backend.models.permission import AWSAccountPermission, GCPAccountPermission
from backend.models.user import Organization, User

import logging

logger = logging.getLogger(__name__)


class UserStoragePostgreSQL:
    """用户存储服务 - PostgreSQL 实现

    用于生产环境，使用 SQLAlchemy ORM 连接 RDS PostgreSQL
    """

    def __init__(self):
        """初始化存储服务"""
        logger.info("✅ 用户存储初始化完成 - PostgreSQL (生产环境)")

    def _get_db(self):
        """获取数据库会话"""
        return next(get_db())

    # ==================== 组织管理 ====================

    def create_organization(self, name: str, description: str = None, is_active: bool = False) -> dict:
        """创建组织

        Args:
            name: 组织名称
            description: 组织描述（可选）
            is_active: 是否激活（默认False，需要管理员审核）
        """
        db = self._get_db()
        try:
            org = Organization(
                id=str(uuid.uuid4()),
                name=name,
                is_active=is_active,  # ✅ 直接在创建时设置状态
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(org)
            db.commit()
            db.refresh(org)

            return org.to_dict()  # ✅ 使用 to_dict() 确保数据一致性
        except IntegrityError:
            db.rollback()
            raise ValueError(f"组织已存在: {name}")
        finally:
            db.close()

    def get_organization_by_id(self, org_id: str) -> dict | None:
        """根据ID获取组织"""
        db = self._get_db()
        try:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if not org:
                return None
            return org.to_dict()
        finally:
            db.close()

    def get_organization_count(self) -> int:
        """获取组织总数"""
        db = self._get_db()
        try:
            return db.query(Organization).count()
        finally:
            db.close()

    def get_organization_external_id(self, org_id: str) -> str:
        """获取或创建组织的 External ID（用于 IAM Role AssumeRole）

        External ID 用于防止混淆代理人攻击，是 AWS IAM Role 信任策略的安全机制。
        每个组织有唯一的 External ID。

        Args:
            org_id: 组织ID

        Returns:
            str: External ID (格式: org-{org_id})

        Raises:
            ValueError: 如果组织不存在
        """
        db = self._get_db()
        try:
            org = db.query(Organization).filter(Organization.id == org_id).first()

            if not org:
                raise ValueError(f"组织不存在: {org_id}")

            # ⚠️ 临时方案：数据库模型中 external_id 字段被注释，使用组织 ID 生成固定的 External ID
            # 这样可以保证同一个组织的 External ID 始终一致
            external_id = f"org-{org_id}"
            logger.debug(f"🔑 生成 External ID: {external_id} for org: {org_id}")

            return external_id
        finally:
            db.close()

    # ==================== 用户管理 ====================

    def create_user(
        self,
        org_id: str,
        username: str,
        password_hash: str,
        email: str = None,
        full_name: str = None,
        role: str = "user",
    ) -> dict:
        """创建用户"""
        db = self._get_db()
        try:
            # 如果没有提供 email，使用 username 作为默认值
            if not email:
                email = f"{username}@example.com"

            user = User(
                id=str(uuid.uuid4()),
                org_id=org_id,
                username=username,
                email=email,
                hashed_password=password_hash,
                # full_name 字段在数据库中不存在，已移除
                role=role,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            return user.to_dict()
        except IntegrityError as e:
            db.rollback()
            if "email" in str(e):
                raise ValueError(f"邮箱已存在: {email}")
            raise ValueError(f"用户名已存在: {username}")
        finally:
            db.close()

    def get_user_by_id(self, user_id: str) -> dict | None:
        """根据ID获取用户"""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            return user.to_dict()
        finally:
            db.close()

    def get_user_by_username(self, org_id: str, username: str) -> dict | None:
        """根据组织ID和用户名获取用户"""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.org_id == org_id, User.username == username).first()
            if not user:
                return None
            return user.to_dict()
        finally:
            db.close()

    def get_users_by_org(self, org_id: str) -> list[dict]:
        """获取组织下的所有用户"""
        db = self._get_db()
        try:
            users = db.query(User).filter(User.org_id == org_id).all()
            return [user.to_dict() for user in users]
        finally:
            db.close()

    def get_all_users(self) -> list[dict]:
        """获取所有用户"""
        db = self._get_db()
        try:
            users = db.query(User).all()
            return [user.to_dict() for user in users]
        finally:
            db.close()

    def get_user_count(self, org_id: str = None) -> int:
        """获取用户数量"""
        db = self._get_db()
        try:
            query = db.query(User)
            if org_id:
                query = query.filter(User.org_id == org_id)
            return query.count()
        finally:
            db.close()

    def update_user(self, user_id: str, **kwargs) -> dict:
        """更新用户信息"""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"用户不存在: {user_id}")

            for key, value in kwargs.items():
                if hasattr(user, key) and key != "id":
                    setattr(user, key, value)

            user.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)

            return user.to_dict()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_password(self, user_id: str, new_password_hash: str):
        """更新密码"""
        return self.update_user(user_id, hashed_password=new_password_hash)

    def update_last_login(self, user_id: str):
        """更新最后登录时间"""
        from datetime import datetime

        db = self._get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.last_login_at = datetime.utcnow()
                db.commit()
                logger.debug(f"✅ 更新用户最后登录时间 - User ID: {user_id}")
        except Exception as e:
            logger.error(f"❌ 更新最后登录时间失败 - User ID: {user_id}, Error: {e}")
            db.rollback()
        finally:
            db.close()

    def delete_user(self, user_id: str):
        """删除用户"""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"用户不存在: {user_id}")

            db.delete(user)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ==================== AWS 权限管理 ====================

    def grant_aws_account(self, user_id: str, account_id: str, granted_by: str):
        """授予 AWS 账号权限"""
        db = self._get_db()
        try:
            # 检查是否已存在
            existing = (
                db.query(AWSAccountPermission)
                .filter(
                    AWSAccountPermission.user_id == user_id,
                    AWSAccountPermission.account_id == account_id,
                )
                .first()
            )

            if existing:
                return  # 已存在，跳过

            permission = AWSAccountPermission(
                id=str(uuid.uuid4()),
                user_id=user_id,
                account_id=account_id,
                created_at=datetime.utcnow(),
            )
            db.add(permission)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def revoke_aws_account(self, user_id: str, account_id: str):
        """撤销 AWS 账号权限"""
        db = self._get_db()
        try:
            permission = (
                db.query(AWSAccountPermission)
                .filter(
                    AWSAccountPermission.user_id == user_id,
                    AWSAccountPermission.account_id == account_id,
                )
                .first()
            )

            if permission:
                db.delete(permission)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_user_aws_accounts(self, user_id: str) -> list[str]:
        """获取用户的 AWS 账号权限列表"""
        db = self._get_db()
        try:
            permissions = (
                db.query(AWSAccountPermission).filter(AWSAccountPermission.user_id == user_id).all()
            )
            return [str(p.account_id) for p in permissions]
        finally:
            db.close()

    # ==================== GCP 权限管理 ====================

    def grant_gcp_account(self, user_id: str, account_id: str, granted_by: str):
        """授予 GCP 账号权限"""
        db = self._get_db()
        try:
            # 检查是否已存在
            existing = (
                db.query(GCPAccountPermission)
                .filter(
                    GCPAccountPermission.user_id == user_id,
                    GCPAccountPermission.account_id == account_id,
                )
                .first()
            )

            if existing:
                return  # 已存在，跳过

            permission = GCPAccountPermission(
                id=str(uuid.uuid4()),
                user_id=user_id,
                account_id=account_id,
                created_at=datetime.utcnow(),
            )
            db.add(permission)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def revoke_gcp_account(self, user_id: str, account_id: str):
        """撤销 GCP 账号权限"""
        db = self._get_db()
        try:
            permission = (
                db.query(GCPAccountPermission)
                .filter(
                    GCPAccountPermission.user_id == user_id,
                    GCPAccountPermission.account_id == account_id,
                )
                .first()
            )

            if permission:
                db.delete(permission)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_user_gcp_accounts(self, user_id: str) -> list[str]:
        """获取用户的 GCP 账号权限列表"""
        db = self._get_db()
        try:
            permissions = (
                db.query(GCPAccountPermission).filter(GCPAccountPermission.user_id == user_id).all()
            )
            return [str(p.account_id) for p in permissions]
        finally:
            db.close()
