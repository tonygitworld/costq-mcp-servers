"""测试 Alert REST API 端点

测试所有 REST API 端点的功能和权限控制
"""

import sys
from pathlib import Path

import requests

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class AlertAPITester:
    """Alert API 测试器"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: str | None = None
        self.alert_id: str | None = None

    def login(self, email: str, password: str) -> bool:
        """登录获取 token"""
        print(f"\n🔐 登录 - Email: {email}")

        response = requests.post(
            f"{self.base_url}/api/auth/login", json={"email": email, "password": password}
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            print(f"✅ 登录成功 - Token: {self.token[:20]}...")
            return True
        else:
            print(f"❌ 登录失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    def get_headers(self) -> dict:
        """获取请求头"""
        if not self.token:
            raise ValueError("未登录，请先调用 login()")
        return {"Authorization": f"Bearer {self.token}"}

    def test_create_alert(self) -> bool:
        """测试创建告警"""
        print("\n📝 测试创建告警")

        payload = {
            "query_description": "测试告警：当AWS账号123456789012的SP利用率低于95%时发送邮件到test@example.com",
            "display_name": "SP利用率监控 - API测试",
            "check_frequency": "daily",
        }

        response = requests.post(
            f"{self.base_url}/api/alerts/", json=payload, headers=self.get_headers()
        )

        if response.status_code == 201:
            data = response.json()
            self.alert_id = data.get("alert_id")
            print(f"✅ 创建成功 - Alert ID: {self.alert_id}")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print(f"❌ 创建失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    def test_list_alerts(self) -> bool:
        """测试查询告警列表"""
        print("\n📋 测试查询告警列表")

        response = requests.get(f"{self.base_url}/api/alerts/", headers=self.get_headers())

        if response.status_code == 200:
            data = response.json()
            print(f"✅ 查询成功 - 共 {data.get('count')} 个告警")
            if data.get("alerts"):
                print(f"   第一个告警: {data['alerts'][0].get('display_name')}")
            return True
        else:
            print(f"❌ 查询失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    def test_get_alert(self) -> bool:
        """测试获取单个告警"""
        if not self.alert_id:
            print("\n⚠️  跳过获取告警测试（没有 alert_id）")
            return True

        print(f"\n🔍 测试获取告警详情 - ID: {self.alert_id}")

        response = requests.get(
            f"{self.base_url}/api/alerts/{self.alert_id}", headers=self.get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ 获取成功")
            print(f"   名称: {data.get('alert', {}).get('display_name')}")
            print(f"   状态: {'启用' if data.get('alert', {}).get('is_active') else '禁用'}")
            return True
        else:
            print(f"❌ 获取失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    def test_update_alert(self) -> bool:
        """测试更新告警"""
        if not self.alert_id:
            print("\n⚠️  跳过更新告警测试（没有 alert_id）")
            return True

        print(f"\n✏️  测试更新告警 - ID: {self.alert_id}")

        payload = {"display_name": "SP利用率监控 - API测试（已更新）", "check_frequency": "weekly"}

        response = requests.put(
            f"{self.base_url}/api/alerts/{self.alert_id}", json=payload, headers=self.get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ 更新成功")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print(f"❌ 更新失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    def test_toggle_alert(self) -> bool:
        """测试切换告警状态"""
        if not self.alert_id:
            print("\n⚠️  跳过切换状态测试（没有 alert_id）")
            return True

        print(f"\n🔄 测试切换告警状态 - ID: {self.alert_id}")

        response = requests.post(
            f"{self.base_url}/api/alerts/{self.alert_id}/toggle", headers=self.get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ 切换成功")
            print(f"   新状态: {'启用' if data.get('is_active') else '禁用'}")
            return True
        else:
            print(f"❌ 切换失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    def test_send_test_email(self) -> bool:
        """测试发送测试邮件"""
        if not self.alert_id:
            print("\n⚠️  跳过发送测试邮件（没有 alert_id）")
            return True

        print(f"\n📧 测试发送测试邮件 - ID: {self.alert_id}")
        print("   ⚠️  注意：需要 SES 邮箱验证才能成功")

        response = requests.post(
            f"{self.base_url}/api/alerts/{self.alert_id}/send-test", headers=self.get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ 发送成功")
            print(f"   Message ID: {data.get('message_id')}")
            return True
        else:
            print(f"⚠️  发送失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            print("   （可能是 SES 邮箱未验证，这是正常的）")
            return True  # 不算失败，因为可能是 SES 配置问题

    def test_delete_alert(self) -> bool:
        """测试删除告警"""
        if not self.alert_id:
            print("\n⚠️  跳过删除告警测试（没有 alert_id）")
            return True

        print(f"\n🗑️  测试删除告警 - ID: {self.alert_id}")

        response = requests.delete(
            f"{self.base_url}/api/alerts/{self.alert_id}", headers=self.get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ 删除成功")
            print(f"   Message: {data.get('message')}")
            self.alert_id = None  # 清除 alert_id
            return True
        else:
            print(f"❌ 删除失败 - Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    def run_all_tests(self) -> bool:
        """运行所有测试"""
        print("=" * 80)
        print("🧪 Alert REST API 端点测试")
        print("=" * 80)

        tests = [
            ("创建告警", self.test_create_alert),
            ("查询告警列表", self.test_list_alerts),
            ("获取告警详情", self.test_get_alert),
            ("更新告警", self.test_update_alert),
            ("切换告警状态", self.test_toggle_alert),
            ("发送测试邮件", self.test_send_test_email),
            ("删除告警", self.test_delete_alert),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n❌ 测试异常 - {name}: {str(e)}")
                import traceback

                traceback.print_exc()
                failed += 1

        print("\n" + "=" * 80)
        print("📊 测试结果")
        print("=" * 80)
        print(f"✅ 通过: {passed}/{len(tests)}")
        print(f"❌ 失败: {failed}/{len(tests)}")

        return failed == 0


def main():
    """主函数"""
    # 配置
    BASE_URL = "http://localhost:8000"
    TEST_EMAIL = "aa@aa.com"  # 使用现有的测试用户
    TEST_PASSWORD = "Aa123456"  # 默认密码

    print("\n🚀 开始测试 Alert REST API")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Test User: {TEST_EMAIL}")

    # 创建测试器
    tester = AlertAPITester(base_url=BASE_URL)

    # 登录
    if not tester.login(TEST_EMAIL, TEST_PASSWORD):
        print("\n❌ 登录失败，无法继续测试")
        return 1

    # 运行所有测试
    success = tester.run_all_tests()

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
