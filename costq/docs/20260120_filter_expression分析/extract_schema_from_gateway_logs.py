#!/usr/bin/env python3
"""从Gateway日志中提取工具schema"""

import json
import re

with open('/tmp/gateway_logs.json', 'r') as f:
    data = json.load(f)

# 查找tools/list的响应
for event in data.get('events', []):
    msg = event.get('message', '')

    if 'tools/list' in msg and 'costq-risp-mcp-production___get_sp_coverage' in msg:
        try:
            log_obj = json.loads(msg)
            body = log_obj.get('body', {})
            response_body = body.get('responseBody', '')

            # 解析响应体（格式是字符串，需要手动解析）
            # 格式：{jsonrpc=2.0, id=1, result={tools=[{...}]}}

            # 提取result部分
            if 'result=' in response_body:
                result_start = response_body.find('result=')
                result_content = response_body[result_start:]

                # 找到tools数组
                if 'tools=' in result_content:
                    # 保存原始响应
                    with open('/tmp/tools_list_response_raw.txt', 'w') as f:
                        f.write(response_body)

                    print("✅ Found tools/list response!")
                    print(f"Response length: {len(response_body)} characters")
                    print("\nSearching for costq-risp-mcp-production tools with filter_expression...")

                    # 搜索所有 costq-risp-mcp-production 工具
                    risp_tools = []

                    # 分割成工具定义
                    parts = response_body.split('name=costq-risp-mcp-production___')

                    for i, part in enumerate(parts[1:], 1):  # 跳过第一个（在name=之前）
                        # 提取工具名称
                        tool_name_end = part.find(',')
                        if tool_name_end > 0:
                            tool_name = 'costq-risp-mcp-production___' + part[:tool_name_end].strip()

                            # 检查是否包含 filter_expression
                            if 'filter_expression=' in part:
                                # 提取filter_expression定义
                                fe_start = part.find('filter_expression=')
                                # 找到下一个逗号或大括号闭合
                                fe_content = part[fe_start:fe_start+500]

                                risp_tools.append({
                                    'name': tool_name,
                                    'has_filter_expression': True,
                                    'filter_expression_def': fe_content[:300]
                                })
                            else:
                                risp_tools.append({
                                    'name': tool_name,
                                    'has_filter_expression': False
                                })

                    print(f"\n找到 {len(risp_tools)} 个 RISP MCP 工具:\n")
                    for tool in risp_tools:
                        if tool['has_filter_expression']:
                            print(f"✓ {tool['name']}")
                            print(f"  filter_expression: {tool['filter_expression_def']}")
                            print()

                    print("\n✅ Raw response saved to: /tmp/tools_list_response_raw.txt")
                    break

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
