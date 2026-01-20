"""测试邮件发送功能

测试 AWS SES 邮件发送是否正常工作
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def test_email_sending():
    """测试邮件发送"""
    print("=" * 80)
    print("🧪 测试 AWS SES 邮件发送功能")
    print("=" * 80)

    try:
        # 使用公共 SES 客户端（不再使用 Alert MCP 的 ses_client）
        from backend.services.aws_ses_client import SES_REGION, SES_SENDER_EMAIL, send_email

        print("\n📋 SES 配置:")
        print(f"  - 区域: {SES_REGION}")
        print(f"  - 发件人: {SES_SENDER_EMAIL}")

        # 测试邮件参数
        test_to_emails = ["yuguang.li@hotmail.com"]  # 使用实际的测试邮箱
        test_subject = "CostQ 告警测试邮件"
        # 准备邮件内容
        test_time = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

        test_body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #FF9900; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; margin-top: 20px; }}
        .alert-info {{ background-color: white; padding: 15px; margin: 10px 0; border-left: 4px solid #FF9900; }}
        .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ CostQ 告警测试</h1>
        </div>
        <div class="content">
            <h2>SP利用率监控测试</h2>
            <div class="alert-info">
                <p><strong>告警描述：</strong></p>
                <p>这是一封测试邮件，用于验证 AWS SES 邮件发送功能是否正常。</p>
                <p>如果您收到这封邮件，说明邮件发送功能已经正常工作！</p>
            </div>
            <div class="alert-info">
                <p><strong>测试时间：</strong> {test_time}</p>
                <p><strong>发件人：</strong> {SES_SENDER_EMAIL}</p>
                <p><strong>区域：</strong> {SES_REGION}</p>
            </div>
        </div>
        <div class="footer">
            <p>此邮件由 CostQ 自动发送，请勿回复。</p>
            <p>© 2024 CostQ. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        test_body_text = f"""
CostQ 告警测试邮件

这是一封测试邮件，用于验证 AWS SES 邮件发送功能是否正常。
如果您收到这封邮件，说明邮件发送功能已经正常工作！

测试时间: {test_time}
发件人: {SES_SENDER_EMAIL}
区域: {SES_REGION}

---
此邮件由 CostQ 自动发送，请勿回复。
© 2024 CostQ. All rights reserved.
"""

        print("\n📧 邮件参数:")
        print(f"  - 收件人: {', '.join(test_to_emails)}")
        print(f"  - 主题: {test_subject}")

        # 发送邮件
        print("\n🚀 开始发送邮件...")
        result = await send_email(
            to_emails=test_to_emails,
            subject=test_subject,
            body_html=test_body_html,
            body_text=test_body_text,
        )

        # 检查结果
        if result.get("success"):
            print("\n✅ 邮件发送成功！")
            print(f"  - MessageId: {result.get('message_id')}")
            print(f"  - 消息: {result.get('message')}")
            print(f"\n📬 请检查收件箱: {', '.join(test_to_emails)}")
            print("   （可能在垃圾邮件文件夹中）")
            return True
        else:
            print("\n❌ 邮件发送失败")
            print(f"  - 错误: {result.get('error')}")

            # 提供故障排查建议
            print("\n🔍 故障排查建议:")
            print("  1. 检查 SES 邮箱验证状态:")
            print("     aws ses get-identity-verification-attributes \\")
            print(f"         --identities {SES_SENDER_EMAIL} \\")
            print(f"         --region {SES_REGION}")
            print("")
            print("  2. 验证发件人邮箱:")
            print("     aws ses verify-email-identity \\")
            print(f"         --email-address {SES_SENDER_EMAIL} \\")
            print(f"         --region {SES_REGION}")
            print("")
            print("  3. 检查 AWS 凭证配置:")
            print("     aws sts get-caller-identity")
            print("")
            print("  4. 检查 SES 沙盒状态:")
            print(f"     aws ses get-account-sending-enabled --region {SES_REGION}")

            return False

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """运行测试"""
    print("\n🚀 开始测试邮件发送功能\n")

    success = await test_email_sending()

    print("\n" + "=" * 80)
    print("📊 测试结果")
    print("=" * 80)

    if success:
        print("✅ 邮件发送测试通过！")
        return 0
    else:
        print("❌ 邮件发送测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
