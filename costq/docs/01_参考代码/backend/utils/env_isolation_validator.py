"""
环境变量隔离验证工具

用于验证主进程的环境变量未被查询账号凭证污染。
"""

import os
import logging

logger = logging.getLogger(__name__)


def verify_env_isolation(phase: str = "") -> bool:
    """验证主进程环境变量未被污染

    Args:
        phase: 验证阶段标记（例如："before_mcp_creation", "after_mcp_creation"）

    Returns:
        bool: True 表示环境变量隔离正常，False 表示发生泄漏

    Notes:
        - 检查敏感的 AWS 凭证环境变量
        - 如果发现泄漏，记录 ERROR 级别日志
        - 可以在关键点多次调用，确保隔离一直有效
    """
    sensitive_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ]

    leaked = [v for v in sensitive_vars if v in os.environ]

    if leaked:
        logger.error(
            "⚠️ 环境变量隔离失败！主进程环境被污染",
            extra={
                "phase": phase,
                "leaked_variables": leaked,
                "expected": [],
                "reason": "查询账号凭证不应该出现在主进程环境变量中（应该仅在 additional_env 字典中）"
            }
        )
        return False

    logger.info(
        "✅ 环境变量隔离验证通过",
        extra={
            "phase": phase,
            "sensitive_vars_checked": sensitive_vars,
            "leaked_count": 0,
            "isolation_ok": True
        }
    )
    return True


def get_sensitive_env_status() -> dict[str, bool]:
    """获取敏感环境变量的存在状态

    Returns:
        dict: 环境变量名 -> 是否存在的映射
    """
    sensitive_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ]

    return {var: var in os.environ for var in sensitive_vars}
