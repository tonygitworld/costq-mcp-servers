#!/usr/bin/env python3
import json
import re

with open('/tmp/gateway_logs.json', 'r') as f:
    data = json.load(f)

print("="*80)
print("Gateway 日志中的工具调用参数分析")
print("="*80)

# 查找包含参数的日志
for event in data.get('events', []):
    msg = event.get('message', '')

    # 查找包含 requestBody 的日志
    if 'requestBody' in msg and 'costq-risp-mcp-production' in msg:
        try:
            log_obj = json.loads(msg)
            body = log_obj.get('body', {})
            request_body = body.get('requestBody', '')

            if request_body:
                print(f"\n📤 Gateway 请求体:")
                try:
                    req_obj = json.loads(request_body)
                    print(json.dumps(req_obj, indent=2, ensure_ascii=False))
                except:
                    print(request_body[:500])
        except:
            pass

    # 查找错误日志
    if 'Parameter validation failed' in msg and 'filter_expression' in msg:
        try:
            log_obj = json.loads(msg)
            body = log_obj.get('body', {})
            error_log = body.get('log', '')
            timestamp = log_obj.get('event_timestamp', 0)

            print(f"\n❌ Gateway 错误 ({timestamp}):")
            print(error_log)
        except:
            pass

print("\n" + "="*80)
