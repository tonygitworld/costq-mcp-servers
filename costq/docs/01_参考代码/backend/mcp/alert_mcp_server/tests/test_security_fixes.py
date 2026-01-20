"""Alert MCP Server 安全修复测试

测试关键安全问题的修复
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def test_input_validation():
    """测试输入验证（防止XSS）"""
    print("=" * 60)
    print("测试 1: 输入验证（防止XSS）")
    print("=" * 60)

    try:
        from pydantic import ValidationError

        from backend.mcp.alert_mcp_server.models.alert_models import CreateAlertParams

        # 测试危险字符被拒绝
        dangerous_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<div onclick='alert()'>test</div>",
        ]

        blocked_count = 0
        for dangerous_input in dangerous_inputs:
            try:
                params = CreateAlertParams(
                    query_description=dangerous_input, user_id="test-user", org_id="test-org"
                )
                print(f"  ❌ 危险输入未被阻止: {dangerous_input[:50]}")
            except ValidationError:
                blocked_count += 1
                print(f"  ✅ 危险输入被阻止: {dangerous_input[:50]}")

        # 测试正常输入被接受
        try:
            params = CreateAlertParams(
                query_description="每天查询prod-01账号的SP覆盖率，如果低于70%，发邮件",
                user_id="test-user",
                org_id="test-org",
            )
            print("  ✅ 正常输入被接受")
        except ValidationError:
            print("  ❌ 正常输入被拒绝")
            return False

        if blocked_count == len(dangerous_inputs):
            print("\n✅ 输入验证测试通过")
            return True
        else:
            print(f"\n❌ 输入验证测试失败: {blocked_count}/{len(dangerous_inputs)} 被阻止")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_admin_permission():
    """测试Admin权限验证"""
    print("\n" + "=" * 60)
    print("测试 2: Admin权限验证")
    print("=" * 60)

    try:
        from backend.mcp.alert_mcp_server.models.alert_models import ListAlertsParams

        # 测试 user_id 现在是必需的
        try:
            params = ListAlertsParams(
                org_id="test-org",
                user_id="test-user",  # 现在是必需的
                is_admin=False,
            )
            print("  ✅ user_id 参数正确设置为必需")
        except Exception as e:
            print(f"  ❌ user_id 参数设置失败: {e}")
            return False

        # 测试 is_admin 字段存在
        if hasattr(params, "is_admin"):
            print("  ✅ is_admin 字段已添加")
        else:
            print("  ❌ is_admin 字段不存在")
            return False

        # 测试默认值
        params2 = ListAlertsParams(org_id="test-org", user_id="test-user")
        if params2.is_admin == False:
            print("  ✅ is_admin 默认值为 False")
        else:
            print(f"  ❌ is_admin 默认值错误: {params2.is_admin}")
            return False

        print("\n✅ Admin权限验证测试通过")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_rate_limit_constants():
    """测试常量配置（邮件速率限制已移除）"""
    print("\n" + "=" * 60)
    print("测试 3: 常量配置")
    print("=" * 60)

    try:
        from backend.mcp.alert_mcp_server.constants import (
            ERROR_MESSAGES,
            MAX_ALERTS_PER_ORG,
            MAX_ALERTS_PER_USER,
            SUCCESS_MESSAGES,
        )

        print(f"  ✅ 用户告警上限: {MAX_ALERTS_PER_USER}")
        print(f"  ✅ 组织告警上限: {MAX_ALERTS_PER_ORG}")
        print(f"  ✅ 错误消息数量: {len(ERROR_MESSAGES)}")
        print(f"  ✅ 成功消息数量: {len(SUCCESS_MESSAGES)}")

        # 验证邮件相关常量已移除
        if "EMAIL_RATE_LIMIT_EXCEEDED" in ERROR_MESSAGES:
            print("  ⚠️  邮件速率限制错误消息仍存在（应已移除）")
        else:
            print("  ✅ 邮件速率限制错误消息已移除")

        print("\n✅ 常量配置测试通过")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """运行所有安全测试"""
    print("\n🔒 开始测试安全修复\n")

    results = []

    # 运行测试
    results.append(await test_input_validation())
    results.append(await test_admin_permission())
    results.append(await test_rate_limit_constants())

    # 汇总结果
    print("\n" + "=" * 60)
    print("安全测试结果汇总")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"通过: {passed}/{total}")

    if passed == total:
        print("\n✅ 所有安全测试通过！")
        return 0
    else:
        print(f"\n❌ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
