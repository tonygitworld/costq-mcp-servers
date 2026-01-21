#!/usr/bin/env python3
import json
from datetime import datetime

with open('/tmp/agentcore_logs.json', 'r') as f:
    data = json.load(f)

print(f"📊 总共 {len(data.get('events', []))} 条日志事件\n")

# 搜索 filter_expression 相关
filter_expr_logs = []
error_logs = []
sp_coverage_logs = []

for event in data.get('events', []):
    msg = event.get('message', '')
    timestamp = event.get('timestamp', 0)
    dt = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')

    if 'filter_expression' in msg.lower():
        filter_expr_logs.append((dt, msg))
    if 'jsonschemaexception' in msg.lower() or 'invalid type' in msg.lower():
        error_logs.append((dt, msg))
    if 'get_sp_coverage' in msg.lower():
        sp_coverage_logs.append((dt, msg))

print("🔍 filter_expression 相关日志:")
for dt, msg in filter_expr_logs[:10]:
    print(f"{dt} - {msg[:300]}")

print("\n\n❌ 错误相关日志:")
for dt, msg in error_logs[:10]:
    print(f"{dt} - {msg[:300]}")

print("\n\n📞 get_sp_coverage 调用日志:")
for dt, msg in sp_coverage_logs[:10]:
    print(f"{dt} - {msg[:300]}")
