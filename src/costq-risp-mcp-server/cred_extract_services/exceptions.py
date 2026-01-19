"""凭证提取服务异常定义

自包含模块，不依赖项目代码。
"""


class CredentialExtractionError(Exception):
    """凭证提取基础异常"""

    pass


class AccountNotFoundError(CredentialExtractionError):
    """账号不存在异常"""

    pass


class CredentialDecryptionError(CredentialExtractionError):
    """凭证解密失败异常"""

    pass


class AssumeRoleError(CredentialExtractionError):
    """AssumeRole 失败异常"""

    pass


class DatabaseConnectionError(CredentialExtractionError):
    """数据库连接失败异常"""

    pass
