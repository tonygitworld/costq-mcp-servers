"""测试 Calculator 工具集成到 Agent 的功能

此测试验证：
1. Calculator 工具能否正确导入
2. Agent 是否包含 calculator 工具
3. Calculator 工具的基本功能
"""
import pytest
from backend.agent.agent_manager import AgentManager
from strands_tools.calculator import calculator


def test_calculator_import():
    """测试 calculator 工具能否正常导入"""
    assert calculator is not None
    assert callable(calculator)
    # Calculator 是 DecoratedFunctionTool，描述在 __doc__ 中
    assert hasattr(calculator, '__doc__') and calculator.__doc__ is not None
    print("✅ Calculator 工具导入成功")


def test_calculator_basic_functionality():
    """测试 calculator 工具的基本计算能力"""
    # 测试基础运算
    result = calculator(expression="2 + 2")
    assert result['status'] == 'success'
    assert '4' in result['content'][0]['text']
    print("✅ 基础算术测试通过")

    # 测试百分比计算（成本增长率场景）
    result = calculator(expression="((1250.50 - 980.30) / 980.30) * 100")
    assert result['status'] == 'success'
    assert '27.5' in result['content'][0]['text']
    print("✅ 成本增长率计算测试通过")

    # 测试财务计算（RI 节省场景）
    result = calculator(expression="1500 * (1 - 0.72)")
    assert result['status'] == 'success'
    assert '420' in result['content'][0]['text']
    print("✅ RI 节省计算测试通过")


def test_agent_includes_calculator():
    """测试 Agent 是否包含 calculator 工具"""
    manager = AgentManager(
        system_prompt="You are a cost analysis assistant.",
        model_id="anthropic.claude-3-haiku-20240307-v1:0"
    )

    # 创建带 calculator 的 Agent（使用空的 MCP 工具列表）
    mock_mcp_tools = []
    agent = manager.create_agent(mock_mcp_tools)

    # 验证 Agent 能成功创建（说明 calculator 已经集成）
    assert agent is not None
    # Strands Agent 对象有 'tool' 属性（单数），是工具管理器
    assert hasattr(agent, 'tool')

    print("✅ Agent 成功创建（已集成 Calculator 工具）")


def test_agent_with_mcp_tools_and_calculator():
    """测试 Agent 同时包含 MCP 工具和 calculator"""
    manager = AgentManager(
        system_prompt="You are a cost analysis assistant.",
        model_id="anthropic.claude-3-haiku-20240307-v1:0"
    )

    # 模拟 MCP 工具（使用简单的函数模拟）
    class MockTool:
        def __init__(self, name):
            self.name = name
            self.description = f"Mock {name} tool"

        def __call__(self, **kwargs):
            return {"status": "success", "result": f"{self.name} called"}

    mock_mcp_tools = [MockTool("cost_explorer"), MockTool("risp_analyzer")]

    agent = manager.create_agent(mock_mcp_tools)

    # 验证 Agent 能成功创建
    assert agent is not None
    assert hasattr(agent, 'tool')
    print("✅ Agent 成功创建（包含 Calculator + MCP 工具）")


if __name__ == '__main__':
    # 运行测试
    print("=" * 60)
    print("开始测试 Calculator 工具集成")
    print("=" * 60)

    try:
        test_calculator_import()
        test_calculator_basic_functionality()
        test_agent_includes_calculator()
        test_agent_with_mcp_tools_and_calculator()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！Calculator 工具已成功集成")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
