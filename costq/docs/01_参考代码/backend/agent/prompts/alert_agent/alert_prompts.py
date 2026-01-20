"""告警 Agent 提示词模块

提供告警执行引擎专用的 System Prompt
"""

from pathlib import Path


def get_alert_execution_system_prompt() -> str:
    """
    获取告警执行引擎的 System Prompt

    这个 Prompt 指导 Agent：
    1. 解析自然语言告警描述
    2. 调用合适的 MCP 工具查询数据
    3. 判断是否满足阈值条件
    4. 条件性发送告警邮件
    5. 返回纯 JSON 格式的结构化结果

    Returns:
        str: 完整的 System Prompt 文本
    """
    prompt_file = Path(__file__).parent / "alert_execution_system.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Alert system prompt file not found: {prompt_file}")

    return prompt_file.read_text(encoding="utf-8")


# 导出 System Prompt 常量（用于快速访问）
ALERT_EXECUTION_SYSTEM_PROMPT = get_alert_execution_system_prompt()


__all__ = [
    "get_alert_execution_system_prompt",
    "ALERT_EXECUTION_SYSTEM_PROMPT",
]
