"""Common Tools MCP Server implementation.

提供跨平台的通用工具，包括时间日期处理等基础功能。
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Define server instructions
SERVER_INSTRUCTIONS = """
# Common Tools MCP Server - 通用工具集服务器

## 🎯 核心功能

提供跨平台的通用工具，为 AWS 和 GCP 成本分析提供统一的基础能力：
- ✅ UTC 时区的日期获取
- ✅ 日期范围计算辅助
- ✅ 时区感知的日期处理

## 🔧 核心工具

### 1. get_today_date - 获取当前日期（UTC时区）

获取当前 UTC 时间的日期信息，用于 AWS/GCP 成本查询的日期范围计算。

**使用场景：**
- 用户查询包含 "今天"、"本月"、"最近N天" 等相对时间词汇时
- 需要计算日期范围作为 AWS Cost Explorer API 的参数时
- 在查询成本数据之前确定正确的时间范围

**参数：**
无参数

**返回格式：**
```json
{
  "today_date_UTC": "2025-01-12",  // 今天的日期（UTC时区），YYYY-MM-DD格式
  "current_month": "2025-01",      // 当前月份，YYYY-MM格式
  "year": 2025,                    // 年份（整数）
  "month": 1,                      // 月份（1-12）
  "day": 12                        // 日期（1-31）
}
```

**重要规则（必读）：**

1. **today_date_UTC 表示今天的日期**
   - 这是 UTC 时区的今天，不是其他日期
   - 用作 AWS Cost Explorer API 的 end_date 时，**直接使用，不要加1天**

2. **AWS Cost Explorer API 的 end_date 是 INCLUSIVE（包含的）**
   - 示例：start_date="2025-01-10", end_date="2025-01-12" 会返回 1月10日、11日、12日 三天的数据
   - ❌ 错误理解：认为 end_date 是 exclusive（不包含），所以需要设置为"明天"
   - ✅ 正确理解：end_date 是 inclusive（包含），所以直接使用 today_date_UTC

3. **禁止使用未来日期**
   - AWS Cost Explorer 只提供历史数据，不能查询未来的成本
   - end_date 必须是 today_date_UTC 或更早的日期
   - ❌ 错误：end_date = "2025-01-13"（如果今天是 2025-01-12）
   - ✅ 正确：end_date = "2025-01-12"（今天）

## 📋 最佳实践

### 标准工作流（查询"最近N天"）

**示例：用户查询"最近5天的成本"**

```
步骤1: 调用 get_today_date()
返回: {"today_date_UTC": "2025-01-12", "current_month": "2025-01", ...}

步骤2: 计算日期范围
- today = "2025-01-12"（从返回值获取）
- end_date = "2025-01-12"（直接使用 today_date_UTC，不要加1天）
- start_date = "2025-01-08"（今天往前推 5-1=4 天）

步骤3: 调用成本查询 API
- get_cost_and_usage(start_date="2025-01-08", end_date="2025-01-12")
```

**示例：用户查询"本月成本"**

```
步骤1: 调用 get_today_date()
返回: {"today_date_UTC": "2025-01-12", "current_month": "2025-01", ...}

步骤2: 计算日期范围
- start_date = "2025-01-01"（本月第一天，从 current_month 计算）
- end_date = "2025-01-12"（今天，直接使用 today_date_UTC）

步骤3: 调用成本查询 API
- get_cost_and_usage(start_date="2025-01-01", end_date="2025-01-12")
```

## ⚠️ 关键注意事项

1. **时区一致性**：
   - 工具返回的是 **UTC 时区**的日期
   - AWS Cost Explorer API 使用 UTC 时区
   - 确保时区一致，避免日期偏差

2. **日期计算规则**：
   - **最近N天** = start_date = today - (N-1), end_date = today
   - **本月** = start_date = 本月第一天, end_date = today
   - **上月** = start_date = 上月第一天, end_date = 上月最后一天

3. **常见错误（必须避免）**：
   - ❌ 认为需要 end_date = today + 1 才能包含今天
   - ❌ 使用未来日期作为 end_date
   - ❌ 混淆本地时区和 UTC 时区

## 🔄 与其他 MCP Server 的配合

- **AWS Cost Explorer MCP**: 使用 today_date_UTC 作为查询的 end_date
- **GCP Cost MCP**: 使用 today_date_UTC 作为查询的 end_date
- **RISP MCP**: 使用 today_date_UTC 确定 RI/SP 查询的日期范围
- **Alert MCP**: 使用 today_date_UTC 判断是否应该执行告警检查
"""

# Initialize FastMCP server
mcp = FastMCP(
    "common-tools",
    instructions=SERVER_INSTRUCTIONS,
)


# ============================================================================
# Register Utility Tools
# ============================================================================


@mcp.tool()
async def get_today_date() -> Dict[str, str | int]:
    """Get current date in UTC timezone.

    Returns today's date in UTC timezone for use in AWS/GCP cost query date ranges.
    This tool should be called BEFORE any cost query that involves relative time
    references (e.g., "today", "this month", "last 7 days").

    **CRITICAL RULES:**
    1. The returned 'today_date_UTC' field represents TODAY's date in UTC timezone
    2. Use 'today_date_UTC' directly as end_date for AWS Cost Explorer API
    3. DO NOT add 1 day to today_date_UTC - AWS Cost Explorer's end_date is INCLUSIVE
    4. AWS Cost Explorer only provides historical data - end_date cannot be in the future

    Returns:
        Dict[str, str | int]: Dictionary containing today's date information:
            - today_date_UTC (str): Today's date in YYYY-MM-DD format (UTC timezone)
                                    Use this as end_date for cost queries
            - current_month (str): Current month in YYYY-MM format
            - year (int): Current year (integer)
            - month (int): Current month (1-12)
            - day (int): Current day of month (1-31)

    Examples:
        Example 1: Query "last 5 days of cost"

        Step 1: Call get_today_date()
        Returns: {
            "today_date_UTC": "2025-01-12",
            "current_month": "2025-01",
            "year": 2025,
            "month": 1,
            "day": 12
        }

        Step 2: Calculate date range
        - end_date = "2025-01-12" (use today_date_UTC directly, DO NOT add 1 day)
        - start_date = "2025-01-08" (today minus 4 days, since we want 5 days total)

        Step 3: Call cost query API
        - get_cost_and_usage(start_date="2025-01-08", end_date="2025-01-12")
        - This will return data for Jan 8, 9, 10, 11, 12 (5 days total)

        Example 2: Query "this month's cost"

        Step 1: Call get_today_date()
        Returns: {"today_date_UTC": "2025-01-12", "current_month": "2025-01", ...}

        Step 2: Calculate date range
        - start_date = "2025-01-01" (first day of current_month)
        - end_date = "2025-01-12" (use today_date_UTC directly)

        Step 3: Call cost query API
        - get_cost_and_usage(start_date="2025-01-01", end_date="2025-01-12")

    Common Mistakes to Avoid:
        ❌ WRONG: end_date = today_date_UTC + 1 day (thinking end_date is exclusive)
        ✅ CORRECT: end_date = today_date_UTC (AWS API's end_date is inclusive)

        ❌ WRONG: end_date = "2025-01-13" (future date when today is 2025-01-12)
        ✅ CORRECT: end_date = "2025-01-12" (today or past dates only)

    Notes:
        - Always call this tool when user mentions time-related keywords
        - The returned date is in UTC timezone to match AWS/GCP API expectations
        - Use 'today_date_UTC' for API calls, not any other date format
    """
    # Get current UTC time
    now_utc = datetime.now(timezone.utc)

    # Build result dictionary with clear field names
    result = {
        "today_date_UTC": now_utc.strftime("%Y-%m-%d"),  # Primary field for API calls
        "current_month": now_utc.strftime("%Y-%m"),  # For month-based queries
        "year": now_utc.year,  # For year-based calculations
        "month": now_utc.month,  # For month-based calculations
        "day": now_utc.day,  # For day-based calculations
    }

    logger.info(f"get_today_date called: today_date_UTC={result['today_date_UTC']}")

    return result


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()