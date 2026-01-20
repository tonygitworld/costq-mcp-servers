"""Test script for Common Tools MCP Server

测试 get_today_date 工具的功能
"""

import asyncio
import json

from .server import get_today_date


async def test_get_today_date():
    """测试 get_today_date 工具"""
    print("=" * 60)
    print("测试 Common Tools MCP Server - get_today_date 工具")
    print("=" * 60)
    print()

    # 调用工具
    result_json = await get_today_date()
    result = json.loads(result_json)

    # 打印结果
    print("📅 当前日期信息：")
    print(f"  - date (API格式):     {result['date']}")
    print(f"  - year (年份):        {result['year']}")
    print(f"  - month (月份):       {result['month']}")
    print(f"  - day (日期):         {result['day']}")
    print(f"  - year_month:        {result['year_month']}")
    print(f"  - formatted (格式化): {result['formatted']}")
    print(f"  - iso_format:        {result['iso_format']}")
    print(f"  - month_name:        {result['month_name']}")
    print(f"  - weekday:           {result['weekday']}")
    print(f"  - weekday_cn:        {result['weekday_cn']}")
    print(f"  - quarter (季度):     Q{result['quarter']}")
    print()

    # 验证数据类型
    print("✅ 数据类型验证：")
    assert isinstance(result["date"], str), "date 应该是字符串"
    assert isinstance(result["year"], int), "year 应该是整数"
    assert isinstance(result["month"], int), "month 应该是整数"
    assert isinstance(result["day"], int), "day 应该是整数"
    assert isinstance(result["quarter"], int), "quarter 应该是整数"
    print("  - 所有字段类型正确 ✓")
    print()

    # 验证值范围
    print("✅ 值范围验证：")
    assert 1 <= result["month"] <= 12, "month 应该在 1-12 之间"
    assert 1 <= result["day"] <= 31, "day 应该在 1-31 之间"
    assert 1 <= result["quarter"] <= 4, "quarter 应该在 1-4 之间"
    print("  - 所有字段值范围正确 ✓")
    print()

    # 验证日期格式
    print("✅ 日期格式验证：")
    assert len(result["date"]) == 10, "date 格式应该是 YYYY-MM-DD"
    assert result["date"][4] == "-" and result["date"][7] == "-", "date 分隔符应该是 -"
    assert len(result["year_month"]) == 7, "year_month 格式应该是 YYYY-MM"
    print("  - 日期格式正确 ✓")
    print()

    # 示例：计算本月日期范围
    print("📊 示例：计算本月日期范围")
    start_date = f"{result['year']}-{result['month']:02d}-01"
    end_date = result["date"]
    print(f"  - start_date: {start_date}")
    print(f"  - end_date:   {end_date}")
    print(f"  - 用途：查询本月成本数据")
    print()

    print("=" * 60)
    print("✅ 所有测试通过！Common Tools MCP Server 工作正常")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_get_today_date())
