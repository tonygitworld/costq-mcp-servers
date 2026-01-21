#!/usr/bin/env python3
import json
from datetime import datetime

with open('/tmp/agentcore_logs.json', 'r') as f:
    data = json.load(f)

# 找到所有09:28之后的日志（北京时间09:28 = UTC 01:28）
target_logs = []
for event in data.get('events', []):
    msg = event.get('message', '')
    timestamp = event.get('timestamp', 0)
    dt = datetime.fromtimestamp(timestamp/1000)

    # 只看01:18之后的日志
    if dt.hour == 1 and dt.minute >= 18:
        if any(keyword in msg.lower() for keyword in ['filter_expression', 'jsonschema', 'invalid type', 'get_sp_coverage']):
            target_logs.append((dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], msg))

print(f"找到 {len(target_logs)} 条相关日志\n")
print("="*80)

for i, (dt, msg) in enumerate(target_logs[:30]):
    print(f"\n⏰ [{i+1}] {dt}")
    # 如果是JSON格式，尝试美化输出
    try:
        if msg.strip().startswith('{'):
            obj = json.loads(msg)
            if 'body' in obj:
                body_str = obj.get('body', '')
                print(f"Body: {body_str[:600]}")
            elif 'scopeLogs' in obj.get('resource', {}).get('attributes', {}):
                print(f"Raw: {msg[:600]}")
            else:
                print(json.dumps(obj, indent=2, ensure_ascii=False)[:600])
        else:
            print(msg[:600])
    except Exception as e:
        print(msg[:600])
    print("-"*80)

# 保存完整日志到文件
with open('/tmp/agentcore_detailed_logs.txt', 'w') as f:
    for dt, msg in target_logs:
        f.write(f"\n{'='*80}\n")
        f.write(f"⏰ {dt}\n")
        f.write(f"{msg}\n")

print(f"\n✅ 完整日志已保存到 /tmp/agentcore_detailed_logs.txt")
