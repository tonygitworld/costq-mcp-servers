"""Send Email MCP Server 单元测试

测试邮件发送功能的各种场景
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def test_send_email_success():
    """测试成功发送邮件"""
    print("=" * 60)
    print("测试 1: 成功发送邮件")
    print("=" * 60)

    try:
        from backend.mcp.send_email_mcp_server.handlers.email_handler import send_email

        # Mock SES 客户端
        with patch("backend.mcp.send_email_mcp_server.utils.ses_client.send_email") as mock_send:
            mock_send.return_value = {
                "success": True,
                "message_id": "test-message-123",
                "to_emails": ["test@example.com"],
            }

            result = await send_email(
                to_emails=["test@example.com"],
                subject="测试邮件",
                body_html="<h1>测试</h1>",
                body_text="测试",
            )

            assert result["success"] == True, "发送应该成功"
            assert "message_id" in result, "应该包含 message_id"
            assert result["to_emails"] == ["test@example.com"], "收件人应该正确"

            print("✅ 成功发送邮件测试通过")
            print(f"   - message_id: {result['message_id']}")
            print(f"   - to_emails: {result['to_emails']}")
            return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_send_email_validation():
    """测试参数验证"""
    print("\n" + "=" * 60)
    print("测试 2: 参数验证")
    print("=" * 60)

    try:
        from backend.mcp.send_email_mcp_server.handlers.email_handler import send_email

        # 测试空收件人列表
        try:
            await send_email(to_emails=[], subject="测试", body_html="测试")
            print("❌ 应该抛出 ValueError（空收件人列表）")
            return False
        except ValueError as e:
            if "收件人列表不能为空" in str(e):
                print("✅ 空收件人列表验证通过")
            else:
                print(f"❌ 错误消息不正确: {e}")
                return False

        # 测试空主题
        try:
            await send_email(to_emails=["test@example.com"], subject="", body_html="测试")
            print("❌ 应该抛出 ValueError（空主题）")
            return False
        except ValueError as e:
            if "邮件主题不能为空" in str(e):
                print("✅ 空主题验证通过")
            else:
                print(f"❌ 错误消息不正确: {e}")
                return False

        # 测试空邮件正文
        try:
            await send_email(
                to_emails=["test@example.com"], subject="测试", body_html="", body_text=""
            )
            print("❌ 应该抛出 ValueError（空邮件正文）")
            return False
        except ValueError as e:
            if "邮件正文不能为空" in str(e):
                print("✅ 空邮件正文验证通过")
            else:
                print(f"❌ 错误消息不正确: {e}")
                return False

        print("\n✅ 所有参数验证测试通过")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_send_email_failure():
    """测试发送失败场景"""
    print("\n" + "=" * 60)
    print("测试 3: 发送失败场景")
    print("=" * 60)

    try:
        from backend.mcp.send_email_mcp_server.handlers.email_handler import send_email

        # Mock SES 客户端返回失败
        with patch("backend.mcp.send_email_mcp_server.utils.ses_client.send_email") as mock_send:
            mock_send.return_value = {
                "success": False,
                "error": "MessageRejected: Email address is not verified",
                "to_emails": ["test@example.com"],
            }

            result = await send_email(
                to_emails=["test@example.com"], subject="测试邮件", body_html="<h1>测试</h1>"
            )

            assert result["success"] == False, "应该返回失败"
            assert "error" in result, "应该包含错误信息"
            assert result["to_emails"] == ["test@example.com"], "收件人应该正确"

            print("✅ 发送失败场景测试通过")
            print(f"   - success: {result['success']}")
            print(f"   - error: {result['error']}")
            return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_server_import():
    """测试服务器导入"""
    print("\n" + "=" * 60)
    print("测试 4: 服务器导入")
    print("=" * 60)

    try:
        from backend.mcp.send_email_mcp_server import server

        print("✅ Send Email MCP Server 导入成功")
        print(f"   - 模块路径: {server.__file__}")
        return True

    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_tools_registration():
    """测试工具注册"""
    print("\n" + "=" * 60)
    print("测试 5: 工具注册")
    print("=" * 60)

    try:
        from backend.mcp.send_email_mcp_server import server

        # 获取工具列表
        tools = await server.mcp.list_tools()

        print(f"✅ 已注册 {len(tools)} 个工具:")

        expected_tools = ["send_email_tool"]
        registered_tool_names = [tool.name for tool in tools]

        for tool_name in registered_tool_names:
            print(f"   - {tool_name}")

        # 验证工具是否注册
        if "send_email_tool" in registered_tool_names:
            print("\n✅ send_email_tool 工具已注册")
            return True
        else:
            print("\n❌ send_email_tool 未注册")
            print(f"   实际注册的工具: {registered_tool_names}")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n🚀 开始测试 Send Email MCP Server\n")

    results = []

    # 运行测试
    results.append(await test_server_import())
    results.append(await test_tools_registration())
    results.append(await test_send_email_success())
    results.append(await test_send_email_validation())
    results.append(await test_send_email_failure())

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
