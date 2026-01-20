#!/usr/bin/env python3
"""
AgentCore Runtime 部署验证脚本
"""

import boto3
import json
from datetime import datetime, timedelta

# 配置
RUNTIME_ID = "cosq_agentcore_runtime_development-49gbDzHm0G"
REGION = "ap-northeast-1"
PROFILE = "3532"

def main():
    print("=" * 60)
    print("🔍 AgentCore Runtime 部署验证")
    print("=" * 60)
    print(f"Runtime ID: {RUNTIME_ID}")
    print(f"Region: {REGION}\n")

    # 创建客户端
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    agentcore = session.client('bedrock-agentcore-runtime')
    logs = session.client('logs')

    # 1. 验证 Runtime 状态（通过 Invoke 测试）
    print("📊 Step 1: 测试 Runtime 连接...")
    try:
        response = agentcore.invoke_agent(
            runtimeId=RUNTIME_ID,
            inputText="ping",
            sessionId="test-verification-" + datetime.now().strftime("%Y%m%d%H%M%S")
        )
        print("✅ Runtime 可访问")
        print(f"  Session ID: {response.get('sessionId', 'N/A')}")
    except Exception as e:
        print(f"❌ Runtime 访问失败: {e}")
        return

    print()

    # 2. 检查最近的日志
    print("📝 Step 2: 检查最近的日志（最近 5 分钟）...")
    log_group = f"/aws/bedrock-agentcore/runtimes/{RUNTIME_ID}-DEFAULT"

    try:
        # 获取最近的日志流
        streams_response = logs.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )

        if not streams_response['logStreams']:
            print("⚠️  没有找到日志流")
        else:
            stream_name = streams_response['logStreams'][0]['logStreamName']

            # 获取最近 5 分钟的日志
            start_time = int((datetime.now() - timedelta(minutes=5)).timestamp() * 1000)

            events_response = logs.get_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                startTime=start_time,
                limit=10
            )

            if not events_response['events']:
                print("⚠️  最近 5 分钟没有新日志")
            else:
                print(f"✅ 发现 {len(events_response['events'])} 条日志:")
                for event in events_response['events'][:5]:
                    timestamp = datetime.fromtimestamp(event['timestamp']/1000).strftime('%H:%M:%S')
                    message = event['message'][:100]
                    print(f"  [{timestamp}] {message}")

    except Exception as e:
        print(f"⚠️  无法读取日志: {e}")

    print()

    # 3. 检查错误日志
    print("🔍 Step 3: 检查最近的错误日志...")
    try:
        start_time = int((datetime.now() - timedelta(minutes=10)).timestamp() * 1000)

        filter_response = logs.filter_log_events(
            logGroupName=log_group,
            startTime=start_time,
            filterPattern="ERROR",
            limit=5
        )

        if not filter_response['events']:
            print("✅ 最近 10 分钟没有错误日志")
        else:
            print(f"⚠️  发现 {len(filter_response['events'])} 条错误日志:")
            for event in filter_response['events']:
                timestamp = datetime.fromtimestamp(event['timestamp']/1000).strftime('%H:%M:%S')
                message = event['message'][:150]
                print(f"  [{timestamp}] {message}")

    except Exception as e:
        print(f"⚠️  无法检查错误日志: {e}")

    print()

    # 4. 总结
    print("=" * 60)
    print("✅ 部署验证完成！")
    print("=" * 60)
    print("\n📝 下一步:")
    print("  1. 访问前端界面创建新会话（点击 'New Chat'）")
    print("  2. 发送测试查询（如：'查询 AWS 账单'）")
    print("  3. 观察日志输出格式（应包含 traceId/spanId）")
    print("=" * 60)

if __name__ == "__main__":
    main()
