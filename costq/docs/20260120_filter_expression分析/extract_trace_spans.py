#!/usr/bin/env python3
import json
from datetime import datetime

# 读取Gateway日志
with open('/tmp/gateway_logs.json', 'r') as f:
    gateway_data = json.load(f)

# 找到错误相关的trace_id
error_traces = set()
for event in gateway_data.get('events', []):
    msg = event.get('message', '')
    if 'Parameter validation failed' in msg and 'filter_expression' in msg:
        try:
            log_obj = json.loads(msg)
            trace_id = log_obj.get('trace_id', '')
            if trace_id:
                error_traces.add(trace_id)
        except:
            pass

print(f"找到 {len(error_traces)} 个错误相关的 trace_id:")
for trace_id in error_traces:
    print(f"  - {trace_id}")

# 对于每个错误trace，提取完整的调用链
for trace_id in list(error_traces)[:2]:  # 只分析前2个
    print(f"\n{'='*80}")
    print(f"Trace ID: {trace_id}")
    print('='*80)

    trace_events = []
    for event in gateway_data.get('events', []):
        msg = event.get('message', '')
        try:
            log_obj = json.loads(msg)
            if log_obj.get('trace_id') == trace_id:
                timestamp = log_obj.get('event_timestamp', 0)
                span_id = log_obj.get('span_id', '')
                request_id = log_obj.get('request_id', '')
                body = log_obj.get('body', {})
                is_error = body.get('isError', False)
                log_msg = body.get('log', '')
                request_body = body.get('requestBody', '')
                response_body = body.get('responseBody', '')

                trace_events.append({
                    'timestamp': timestamp,
                    'span_id': span_id,
                    'request_id': request_id,
                    'is_error': is_error,
                    'log': log_msg,
                    'request_body': request_body,
                    'response_body': response_body
                })
        except:
            pass

    # 按时间排序
    trace_events.sort(key=lambda x: x['timestamp'])

    print(f"\n找到 {len(trace_events)} 个事件:")
    for i, evt in enumerate(trace_events):
        dt = datetime.fromtimestamp(evt['timestamp']/1000).strftime('%H:%M:%S.%f')[:-3]
        error_flag = "❌" if evt['is_error'] else "✓"
        print(f"\n[{i+1}] {error_flag} {dt} - Span: {evt['span_id'][:8]}...")
        print(f"    Request ID: {evt['request_id']}")
        if evt['log']:
            print(f"    Log: {evt['log'][:200]}")
        if evt['request_body'] and len(evt['request_body']) < 500:
            print(f"    Request: {evt['request_body'][:400]}")
        if evt['response_body'] and len(evt['response_body']) < 300:
            print(f"    Response: {evt['response_body'][:300]}")
