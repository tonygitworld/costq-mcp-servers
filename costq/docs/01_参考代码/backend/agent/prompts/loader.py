"""提示词加载器 - 支持模块化提示词的动态加载和组装"""

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


class PromptLoader:
    """提示词加载器（模块化 + 缓存）"""

    def __init__(self, base_dir: Path | None = None):
        """
        初始化加载器

        Args:
            base_dir: 提示词文件的基础目录，默认为当前文件所在目录
        """
        self.base_dir = base_dir or Path(__file__).parent
        logger.info(f"PromptLoader initialized with base_dir: {self.base_dir}")

    @lru_cache(maxsize=50)
    def load_section(self, section_path: str) -> str:
        """
        加载单个提示词片段（带LRU缓存）

        Args:
            section_path: 相对于base_dir的文件路径，如 "core/identity.md"

        Returns:
            文件内容

        Raises:
            FileNotFoundError: 文件不存在
        """
        file_path = self.base_dir / section_path

        if not file_path.exists():
            raise FileNotFoundError(
                f"Prompt section not found: {section_path}\nFull path: {file_path}"
            )

        logger.debug(f"Loading prompt section: {section_path}")
        return file_path.read_text(encoding="utf-8")

    def assemble_prompt(self, sections: list[str], separator: str = "\n\n") -> str:
        """
        组装完整提示词

        Args:
            sections: 要加载的片段列表
            separator: 片段之间的分隔符

        Returns:
            组装后的完整提示词
        """
        parts = []
        for section in sections:
            try:
                content = self.load_section(section)
                parts.append(content)
            except FileNotFoundError:
                logger.error(f"Failed to load section: {section}")
                raise

        return separator.join(parts)

    def get_platform_specific_prompt(
        self, platform: str = "AWS", include_examples: bool = True
    ) -> str:
        """
        获取平台特定的提示词

        Args:
            platform: 平台名称（"AWS", "GCP", "MULTI"）
            include_examples: 是否包含示例

        Returns:
            完整的系统提示词
        """
        sections = [
            "core/identity.md",
            "core/capabilities.md",
            "shared/context_awareness.md",
        ]

        # 平台特定工具
        if platform == "AWS":
            sections.extend(
                [
                    "aws/cost_explorer.md",
                    "aws/risp.md",
                    "aws/cost_optimization.md",
                    "aws/cloudtrail.md",
                    "aws/aws_api.md",
                    "aws/pricing.md",
                    "aws/documentation.md",
                    "aws/knowledge.md",
                ]
            )
        elif platform == "GCP":
            sections.extend(
                [
                    "gcp/cost_management.md",
                    "gcp/cud_analysis.md",
                ]
            )
        else:  # MULTI - 包含所有平台
            sections.extend(
                [
                    "aws/cost_explorer.md",
                    "aws/risp.md",
                    "aws/cost_optimization.md",
                    "aws/cloudtrail.md",
                    "aws/aws_api.md",
                    "aws/pricing.md",
                    "aws/documentation.md",
                    "aws/knowledge.md",
                    "gcp/cost_management.md",
                    "gcp/cud_analysis.md",
                ]
            )

        # 工具选择策略（已删除 tool_selection.md，完全依赖 MCP Server 的工具定义）

        # 平台术语对照
        if platform == "MULTI":
            sections.append("shared/platform_mapping.md")

        # 工作方式
        sections.append("shared/time_handling.md")
        sections.append("core/workflow.md")

        # 回复风格
        sections.append("core/response_style.md")

        # 多账号处理
        sections.append("shared/multi_account.md")

        # 示例（可选）
        if include_examples:
            sections.extend(
                [
                    "examples/cost_analysis.md",
                    "examples/resource_query.md",
                    "examples/mixed_usage.md",
                    "examples/gcp_cud.md",
                    "examples/gcp_cost.md",
                ]
            )

        # 结束语
        sections.append("core/closing.md")

        return self.assemble_prompt(sections)

    def clear_cache(self):
        """清除LRU缓存"""
        self.load_section.cache_clear()
        logger.info("Prompt loader cache cleared")


# 全局加载器实例
_loader = PromptLoader()


def get_aws_intelligent_agent_prompt(platform: str = "AWS", include_examples: bool = True) -> str:
    """
    获取智能助手提示词（向后兼容）

    Args:
        platform: 平台名称（"AWS", "GCP", "MULTI"）
        include_examples: 是否包含示例

    Returns:
        完整的系统提示词
    """
    return _loader.get_platform_specific_prompt(platform, include_examples)
