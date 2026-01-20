#!/usr/bin/env python3
"""Gateway 兼容性验证脚本

验证 parse_json_parameter 函数能够正确处理：
1. Gateway 传递的 dict/list 对象
2. 本地 stdio 传递的 JSON 字符串
3. None 值和错误情况
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent / "src" / "costq-risp-mcp-server"
sys.path.insert(0, str(project_root))

from utils.json_parser import parse_json_parameter


def test_gateway_dict_object():
    """测试 Gateway 传递的 dict 对象"""
    print("测试 1: Gateway dict 对象...")

    # 模拟 Gateway 传递的参数
    gateway_filter = {
        "Dimensions": {
            "Key": "SERVICE",
            "Values": ["Amazon Elastic Compute Cloud - Compute"]
        }
    }

    result = parse_json_parameter(gateway_filter, 'filter_expression')
    assert result == gateway_filter
    print("  ✅ 通过 - Gateway dict 对象正确处理")


def test_gateway_list_object():
    """测试 Gateway 传递的 list 对象"""
    print("测试 2: Gateway list 对象...")

    gateway_group_by = [
        {"Type": "DIMENSION", "Key": "SERVICE"},
        {"Type": "DIMENSION", "Key": "REGION"}
    ]

    result = parse_json_parameter(gateway_group_by, 'group_by')
    assert result == gateway_group_by
    print("  ✅ 通过 - Gateway list 对象正确处理")


def test_stdio_json_string():
    """测试本地 stdio 传递的 JSON 字符串"""
    print("测试 3: Stdio JSON 字符串...")

    # 模拟本地调用传递的 JSON 字符串
    stdio_filter = '{"Dimensions": {"Key": "SERVICE", "Values": ["Amazon EC2"]}}'

    result = parse_json_parameter(stdio_filter, 'filter_expression')
    assert result == {"Dimensions": {"Key": "SERVICE", "Values": ["Amazon EC2"]}}
    print("  ✅ 通过 - JSON 字符串正确解析")


def test_none_value():
    """测试 None 值"""
    print("测试 4: None 值...")

    result = parse_json_parameter(None, 'filter_expression')
    assert result is None
    print("  ✅ 通过 - None 值正确处理")


def test_empty_string():
    """测试空字符串"""
    print("测试 5: 空字符串...")

    result = parse_json_parameter('', 'filter_expression')
    assert result is None
    print("  ✅ 通过 - 空字符串正确处理")


def test_invalid_json_string():
    """测试无效的 JSON 字符串"""
    print("测试 6: 无效 JSON 字符串...")

    try:
        parse_json_parameter('{invalid json}', 'filter_expression')
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert 'Invalid JSON format' in str(e)
        assert 'filter_expression' in str(e)
        print("  ✅ 通过 - 无效 JSON 正确抛出 ValueError")


def test_invalid_type():
    """测试不支持的类型"""
    print("测试 7: 不支持的类型...")

    try:
        parse_json_parameter(123, 'filter_expression')
        assert False, "应该抛出 TypeError"
    except TypeError as e:
        assert 'must be a string, dict, list, or None' in str(e)
        print("  ✅ 通过 - 不支持的类型正确抛出 TypeError")


def test_complex_nested_structure():
    """测试复杂嵌套结构"""
    print("测试 8: 复杂嵌套结构...")

    complex_filter = {
        "And": [
            {
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Amazon Elastic Compute Cloud - Compute"]
                }
            },
            {
                "Or": [
                    {"Dimensions": {"Key": "REGION", "Values": ["us-east-1"]}},
                    {"Dimensions": {"Key": "REGION", "Values": ["us-west-2"]}}
                ]
            }
        ]
    }

    result = parse_json_parameter(complex_filter, 'filter_expression')
    assert result == complex_filter
    assert len(result['And']) == 2
    assert len(result['And'][1]['Or']) == 2
    print("  ✅ 通过 - 复杂嵌套结构正确处理")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Gateway 兼容性验证测试")
    print("=" * 60)
    print()

    try:
        test_gateway_dict_object()
        test_gateway_list_object()
        test_stdio_json_string()
        test_none_value()
        test_empty_string()
        test_invalid_json_string()
        test_invalid_type()
        test_complex_nested_structure()

        print()
        print("=" * 60)
        print("✅ 所有测试通过！Gateway 兼容性修复成功！")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ 意外错误: {type(e).__name__}: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
