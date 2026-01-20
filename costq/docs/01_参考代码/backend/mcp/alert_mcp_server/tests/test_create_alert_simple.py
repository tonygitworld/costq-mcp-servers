"""简化的告警创建测试

使用现有的组织和用户测试告警创建功能
测试场景：123456789012账号的SP利用率低于95%时向 aaa@aaa.com 发送告警
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def main():
    """测试创建告警"""
    print("=" * 80)
    print("🧪 测试创建告警：123456789012账号的SP利用率低于95%时发送告警")
    print("=" * 80)

    try:
        from mcp.server.fastmcp import Context

        from backend.mcp.alert_mcp_server.handlers.alert_handler import create_alert
        from backend.mcp.alert_mcp_server.models.alert_models import CreateAlertParams
        from backend.mcp.alert_mcp_server.utils.db_helper import AlertDBHelper, get_db_session

        # 获取现有的组织和用户
        print("\n📋 获取现有的组织和用户...")
        db = SessionLocal()
        result = db.execute(text("SELECT id, name FROM organizations LIMIT 1"))
        org_row = result.first()

        result2 = db.execute(text("SELECT id, username, org_id FROM users LIMIT 1"))
        user_row = result2.first()
        db.close()

        if not org_row or not user_row:
            print("❌ 没有找到组织或用户，请先创建")
            return 1

        org_id = org_row[0]
        org_name = org_row[1]
        user_id = user_row[0]
        username = user_row[1]

        print(f"  ✅ 组织: {org_name} (ID: {org_id})")
        print(f"  ✅ 用户: {username} (ID: {user_id})")

        # 创建告警参数
        print("\n📋 创建告警参数...")
        params = CreateAlertParams(
            query_description="123456789012账号的SP利用率低于95%的时候向 aaa@aaa.com 发送告警",
            display_name="SP利用率监控 - 123456789012",
            user_id=user_id,
            org_id=org_id,
            check_frequency="daily",
        )

        print(f"  ✅ query_description: {params.query_description}")
        print(f"  ✅ display_name: {params.display_name}")
        print(f"  ✅ check_frequency: {params.check_frequency}")

        # 创建模拟的 Context
        context = Context()

        # 调用创建告警函数
        print("\n🚀 开始创建告警...")
        result = await create_alert(context, params)

        # 检查结果
        if result.get("success"):
            alert_id = result.get("alert_id")
            print("\n✅ 告警创建成功！")
            print(f"  - 告警ID: {alert_id}")
            print(f"  - 显示名称: {result.get('display_name')}")
            print(f"  - 消息: {result.get('message')}")

            # 验证告警是否真的保存到数据库
            print("\n🔍 验证数据库记录...")
            with get_db_session() as db:
                alert = AlertDBHelper.get_alert_by_id(db=db, alert_id=alert_id, org_id=org_id)

                if alert:
                    print("✅ 数据库验证成功")
                    print(f"  - ID: {alert.id}")
                    print(f"  - 显示名称: {alert.display_name}")
                    print(f"  - 查询描述: {alert.query_description}")
                    print(f"  - 检查频率: {alert.check_frequency}")
                    print(f"  - 是否启用: {alert.is_active}")
                    print(f"  - 创建时间: {alert.created_at}")
                    print(f"  - 用户ID: {alert.user_id}")
                    print(f"  - 组织ID: {alert.org_id}")

                    # 询问是否删除测试数据
                    print("\n❓ 是否删除测试数据？")
                    print(f"   告警ID: {alert_id}")
                    print("   如需删除，请运行:")
                    print('   python3 -c "')
                    print(
                        "from backend.mcp.alert_mcp_server.utils.db_helper import AlertDBHelper, get_db_session"
                    )
                    print("with get_db_session() as db:")
                    print(
                        f"    AlertDBHelper.delete_alert(db, '{alert_id}', '{org_id}', '{user_id}')"
                    )
                    print("print('✅ 告警已删除')")
                    print('   "')
                else:
                    print("❌ 数据库验证失败：未找到告警记录")
                    return 1

            print("\n✅ 测试完成！")
            return 0
        else:
            print("\n❌ 告警创建失败")
            print(f"  - 错误: {result.get('error')}")
            return 1

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
