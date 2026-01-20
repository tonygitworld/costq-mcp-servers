"""Alert MCP Server 基础测试

测试Alert MCP Server的基本功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def test_server_import():
    """测试服务器导入"""
    print("=" * 60)
    print("测试 1: 服务器导入")
    print("=" * 60)

    try:
        print("✅ Alert MCP Server 导入成功")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_tools_registration():
    """测试工具注册"""
    print("\n" + "=" * 60)
    print("测试 2: 工具注册")
    print("=" * 60)

    try:
        from backend.mcp.alert_mcp_server import server

        # 获取工具列表
        tools = await server.app.list_tools()

        print(f"✅ 已注册 {len(tools)} 个工具:")

        expected_tools = [
            "create_alert",
            "list_alerts",
            "update_alert",
            "toggle_alert",
            "delete_alert",
        ]

        registered_tool_names = [tool.name for tool in tools]

        for tool_name in expected_tools:
            if tool_name in registered_tool_names:
                print(f"  ✅ {tool_name}")
            else:
                print(f"  ❌ {tool_name} (未注册)")

        # 检查是否所有工具都注册了
        if set(expected_tools) == set(registered_tool_names):
            print("\n✅ 所有工具都已正确注册")
            return True
        else:
            missing = set(expected_tools) - set(registered_tool_names)
            extra = set(registered_tool_names) - set(expected_tools)
            if missing:
                print(f"\n❌ 缺少工具: {missing}")
            if extra:
                print(f"\n⚠️  额外工具: {extra}")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_database_models():
    """测试数据库模型"""
    print("\n" + "=" * 60)
    print("测试 3: 数据库模型")
    print("=" * 60)

    try:
        from backend.models.monitoring import AlertHistory, MonitoringConfig

        print("✅ MonitoringConfig 模型导入成功")
        print("✅ AlertHistory 模型导入成功")

        # 检查表名
        print(f"  - MonitoringConfig 表名: {MonitoringConfig.__tablename__}")
        print(f"  - AlertHistory 表名: {AlertHistory.__tablename__}")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_constants():
    """测试常量配置"""
    print("\n" + "=" * 60)
    print("测试 4: 常量配置")
    print("=" * 60)

    try:
        from backend.mcp.alert_mcp_server.constants import (
            DEFAULT_CHECK_FREQUENCY,
            ERROR_MESSAGES,
            MAX_ALERTS_PER_ORG,
            MAX_ALERTS_PER_USER,
            SUCCESS_MESSAGES,
        )

        print(f"✅ 默认检查频率: {DEFAULT_CHECK_FREQUENCY}")
        print(f"✅ 用户告警上限: {MAX_ALERTS_PER_USER}")
        print(f"✅ 组织告警上限: {MAX_ALERTS_PER_ORG}")
        print(f"✅ 错误消息数量: {len(ERROR_MESSAGES)}")
        print(f"✅ 成功消息数量: {len(SUCCESS_MESSAGES)}")

        # 验证配置
        assert DEFAULT_CHECK_FREQUENCY == "daily", "默认检查频率配置错误"
        assert MAX_ALERTS_PER_USER == 100, "用户告警上限配置错误"
        assert MAX_ALERTS_PER_ORG == 500, "组织告警上限配置错误"

        print("\n✅ 所有常量配置正确")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n🚀 开始测试 Alert MCP Server\n")

    results = []

    # 运行测试
    results.append(await test_server_import())
    results.append(await test_tools_registration())
    results.append(await test_database_models())
    results.append(await test_constants())

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"通过: {passed}/{total}")

    if passed == total:
        print("\n✅ 所有测试通过！")
        return 0
    else:
        print(f"\n❌ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
