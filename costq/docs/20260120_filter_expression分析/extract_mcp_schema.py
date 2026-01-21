#!/usr/bin/env python3
"""提取 RISP MCP Server 的工具 Schema

这个脚本会导入 server 并提取工具的 MCP Schema 定义
"""

import sys
import os
import json

# 添加 RISP MCP Server 到 Python 路径
risp_server_path = "/Users/liyuguang/data/gitworld/tonygithub/costq-mcp-servers/src/costq-risp-mcp-server"
sys.path.insert(0, risp_server_path)

try:
    # 导入 server
    from server import app

    print("✅ Successfully imported RISP MCP Server\n")
    print("="*80)
    print("Registered Tools:")
    print("="*80)

    # 获取所有工具
    tools = app.list_tools()

    print(f"\nTotal Tools: {len(tools)}\n")

    # 查找包含 filter_expression 的工具
    tools_with_filter = []

    for tool in tools:
        tool_name = tool.name
        input_schema = tool.inputSchema

        # 检查是否有 filter_expression 参数
        properties = input_schema.get('properties', {})
        if 'filter_expression' in properties:
            tools_with_filter.append({
                'name': tool_name,
                'description': tool.description[:100] + "..." if len(tool.description) > 100 else tool.description,
                'filter_expression_schema': properties['filter_expression']
            })

    print("="*80)
    print(f"Tools with filter_expression parameter: {len(tools_with_filter)}")
    print("="*80)

    for tool_info in tools_with_filter:
        print(f"\n📋 Tool: {tool_info['name']}")
        print(f"   Description: {tool_info['description']}")
        print(f"   filter_expression schema:")
        print(json.dumps(tool_info['filter_expression_schema'], indent=6, ensure_ascii=False))

    # 保存完整的 schema 到文件
    output_file = "/Users/liyuguang/data/gitworld/tonygithub/costq-mcp-servers/costq/docs/20260120_filter_expression分析/risp_mcp_schemas.json"

    schemas = {}
    for tool in tools:
        schemas[tool.name] = {
            'description': tool.description,
            'inputSchema': tool.inputSchema
        }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schemas, f, indent=2, ensure_ascii=False)

    print(f"\n\n✅ Complete schemas saved to: {output_file}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
