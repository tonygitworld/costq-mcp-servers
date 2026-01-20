"""告警 Agent 管理器

通过调用 AgentCore Runtime 执行告警检查。
使用告警专用的 System Prompt (ALERT_EXECUTION_SYSTEM_PROMPT)。
"""

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any

from backend.agent.prompts.alert_agent import ALERT_EXECUTION_SYSTEM_PROMPT
from backend.api.agentcore_response_parser import AgentCoreResponseParser
from backend.config.settings import settings
from backend.database import get_db
from backend.models.alert_execution_log import AlertExecutionLog
from backend.services.account_storage_postgresql import AccountStoragePostgreSQL
from backend.services.agentcore_client import AgentCoreClient

logger = logging.getLogger(__name__)


class AlertAgentManager:
    """告警执行 Agent 管理器（简化版）

    核心职责：
    1. 创建专用的 Agent（使用告警专用 System Prompt）
    2. 执行告警检查（调用 Agent + 解析响应 + 记录日志）
    3. 复用 MCPManager 创建MCP客户端（无缓存）

    设计理念：
    - 与 websocket.py 逻辑一致，只是 prompt 不同
    - 无缓存，每次创建新的 Agent 和 MCP 客户端
    - 简化代码，易于维护
    """

    def __init__(self):
        """初始化告警 Agent 管理器"""
        logger.info("🚀 初始化 AlertAgentManager...")

        # 账号存储服务
        self.account_storage = AccountStoragePostgreSQL()

        logger.info("✅ AlertAgentManager 已初始化")
        logger.info(f"   - 调用方式: AgentCore Runtime")
        logger.info(f"   - Runtime ARN: {settings.AGENTCORE_RUNTIME_ARN}")
        logger.info(f"   - Prompt Type: alert")
        logger.info(f"   - 告警提示词长度: {len(ALERT_EXECUTION_SYSTEM_PROMPT)} 字符")

    async def execute_alert_check(
        self,
        alert_id: str,
        alert_name: str,
        query_description: str,
        org_id: str,
        account_id: str,
        account_type: str,
        user_id: str | None = None,
        is_test: bool = False,
    ) -> dict[str, Any]:
        """执行告警检查（90秒超时）

        Args:
            alert_id: 告警ID
            alert_name: 告警显示名称（用于邮件主题）
            query_description: 自然语言告警描述
            org_id: 组织ID
            account_id: 账号ID（AWS或GCP账号的UUID）
            account_type: 账号类型（aws/gcp）
            user_id: 触发用户ID（测试时有值）
            is_test: 是否为测试模式

        Returns:
            Dict: 执行结果
        """
        start_time = time.time()
        log_id = None
        agent_response_raw = None

        # ============ P0: 参数验证 - 空值检查 ============
        if not alert_name or not alert_name.strip():
            logger.warning(f"⚠️  告警名称为空，使用降级默认值 - Alert ID: {alert_id}")
            alert_name = f"告警-{str(alert_id)[:8]}"  # 降级为 ID 前8位

        logger.info(
            f"🚀 开始执行告警检查 - "
            f"Alert: {alert_id}, "
            f"Name: {alert_name}, "
            f"Account: {account_id} ({account_type}), "
            f"Test: {is_test}"
        )

        try:
            # 1. 创建执行日志（初始状态）
            log_id = await self._create_execution_log(
                alert_id=alert_id,
                org_id=org_id,
                user_id=user_id,
                account_id=account_id,
                account_type=account_type,
                is_test=is_test,
            )
            logger.info(f"✅ 创建执行日志 - Log ID: {log_id}")

            # 2. 获取账号信息和凭证
            account_info = await self._get_account_info(
                account_id=account_id, account_type=account_type, org_id=org_id
            )
            logger.info(
                f"✅ 账号信息获取成功 - Account: {account_info.get('alias', account_id)}"
            )

            # 3. 构造增强查询（参考 websocket.py）
            enhanced_query = self._build_enhanced_query(
                query_description=query_description,
                alert_name=alert_name,
                account_info=account_info,
                alert_id=alert_id,
                org_id=org_id,
                is_test=is_test,
            )
            logger.debug(f"📝 增强查询已构造 - 长度: {len(enhanced_query)} 字符")

            # 4. 初始化 Runtime 客户端和解析器
            client = AgentCoreClient(
                runtime_arn=settings.AGENTCORE_RUNTIME_ARN,
                region=settings.AGENTCORE_REGION,
            )
            parser = AgentCoreResponseParser(session_id=None)  # 告警不需要 session_id

            # 5. 调用 Runtime 并收集响应（600秒超时）
            logger.info("⏳ 开始调用 AgentCore Runtime（告警场景，600秒超时）...")
            assistant_response = []
            event_count = 0
            timeout_seconds = 600

            try:
                # 使用 asyncio.timeout (Python 3.11+)
                async with asyncio.timeout(timeout_seconds):
                    async for event in client.invoke_streaming(
                        prompt=enhanced_query,
                        account_id=str(account_info.get("id")),  # ✅ 转换UUID为字符串
                        session_id=None,  # 告警不需要 Memory
                        user_id=(
                            str(user_id) if user_id else None
                        ),  # ✅ 转换UUID为字符串
                        org_id=str(org_id) if org_id else None,  # ✅ 转换UUID为字符串
                        prompt_type="alert",  # ✅ 关键：传入告警标识
                        account_type=account_type,  # ✅ 传递账号类型
                    ):
                        event_count += 1

                        # 解析 SSE 事件 → WebSocket 消息格式
                        ws_messages = parser.parse_event(event)

                        # 收集文本内容
                        for ws_msg in ws_messages:
                            if ws_msg.get("type") == "chunk":
                                assistant_response.append(ws_msg["content"])
                            elif ws_msg.get("type") == "error":
                                assistant_response.append(ws_msg["content"])

                        # 每处理 20 个事件打印一次日志
                        if event_count % 20 == 0:
                            logger.info(f"📊 已处理 {event_count} 个事件")

                agent_response_raw = (
                    "".join(assistant_response) if assistant_response else ""
                )
                logger.info(
                    f"✅ Runtime 执行完成（告警场景）- "
                    f"事件数: {event_count}, "
                    f"响应长度: {len(agent_response_raw)} 字符"
                )

            except asyncio.TimeoutError:
                raise TimeoutError("Runtime 调用超时（240秒）")

            # 8. 解析响应
            result = self._parse_agent_response(agent_response_raw)
            logger.info(
                f"✅ 响应解析完成 - "
                f"Success: {result.get('success')}, "
                f"Triggered: {result.get('triggered')}, "
                f"Email Sent: {result.get('email_sent')}"
            )

            # 9. 计算执行时间并更新日志
            execution_time = int((time.time() - start_time) * 1000)
            result["execution_duration_ms"] = execution_time

            await self._update_execution_log(
                log_id=log_id,
                result=result,
                agent_response=agent_response_raw,
                execution_time=execution_time,
            )

            logger.info(
                f"✅ 告警检查完成 - "
                f"Alert: {alert_id}, "
                f"Triggered: {result.get('triggered')}, "
                f"Time: {execution_time}ms"
            )

            return result

        except TimeoutError:
            logger.error(f"❌ 告警检查超时（600秒）- Alert: {alert_id}")
            execution_time = int((time.time() - start_time) * 1000)
            error_result = {
                "success": False,
                "triggered": False,
                "email_sent": False,
                "message": "执行超时（600秒）",
                "error": "Timeout",
                "execution_duration_ms": execution_time,
            }

            if log_id:
                await self._update_execution_log(
                    log_id=log_id,
                    result=error_result,
                    agent_response=None,
                    execution_time=execution_time,
                )

            return error_result

        except Exception as e:
            logger.error(f"❌ 告警检查失败: {str(e)}", exc_info=True)
            execution_time = int((time.time() - start_time) * 1000)
            error_result = {
                "success": False,
                "triggered": False,
                "email_sent": False,
                "message": f"执行失败: {str(e)}",
                "error": str(e),
                "execution_duration_ms": execution_time,
            }

            if log_id:
                await self._update_execution_log(
                    log_id=log_id,
                    result=error_result,
                    agent_response=agent_response_raw,
                    execution_time=execution_time,
                )

            return error_result

    async def _get_account_info(
        self, account_id: str, account_type: str, org_id: str
    ) -> dict[str, Any]:
        """获取账号信息和凭证"""
        logger.debug(f"🔍 查询账号信息 - ID: {account_id}, Type: {account_type}")

        # 只支持 AWS 账号（目前 Alert Agent 只支持 AWS）
        if account_type != "aws":
            raise ValueError(f"当前只支持 AWS 账号，不支持: {account_type}")

        # 从数据库查询账号
        account_dict = self.account_storage.get_account(
            account_id=account_id, org_id=org_id
        )

        if not account_dict:
            raise ValueError(f"账号不存在或无权限访问: {account_id}")

        logger.debug(f"✅ 账号查询成功 - Alias: {account_dict.get('alias')}")

        # 解密凭证（如果使用 AKSK 认证）
        auth_type = account_dict.get("auth_type", "aksk")
        secret_access_key = None

        if auth_type == "aksk":
            from backend.services.credential_manager import CredentialManager

            encrypted_key = account_dict.get("secret_access_key_encrypted")
            if encrypted_key:
                try:
                    credential_manager = CredentialManager()
                    secret_access_key = credential_manager.decrypt_secret_key(
                        encrypted_key
                    )
                    logger.debug("✅ Secret Access Key 解密成功")
                except Exception as e:
                    logger.error(f"❌ Secret Access Key 解密失败: {e}")
                    raise ValueError(f"凭证解密失败: {str(e)}")
            else:
                logger.warning("⚠️  账号未配置 Secret Access Key")

        return {
            "id": account_dict["id"],
            "alias": account_dict.get("alias", ""),
            "account_id": account_dict.get("account_id", ""),
            "org_id": org_id,
            "account_type": "aws",
            "auth_type": auth_type,
            "access_key_id": account_dict.get("access_key_id"),
            "secret_access_key": secret_access_key,
            "region": account_dict.get("region", "us-east-1"),
            "role_arn": account_dict.get("role_arn"),
            "role_name": account_dict.get("role_name", "CostQAccessRole"),
            "session_duration": account_dict.get("session_duration"),
        }

    async def _create_execution_log(
        self,
        alert_id: str,
        org_id: str,
        user_id: str | None,
        account_id: str,
        account_type: str,
        is_test: bool,
    ) -> str:
        """创建执行日志记录（初始状态）"""
        db = next(get_db())
        try:
            log = AlertExecutionLog(
                alert_id=alert_id,
                org_id=org_id,
                triggered_by_user_id=user_id,
                account_id=account_id,
                account_type=account_type,
                execution_type="test" if is_test else "scheduled",
                success=False,
                triggered=False,
                email_sent=False,
                started_at=datetime.now(UTC),
            )
            db.add(log)
            db.commit()
            db.refresh(log)

            logger.debug(f"✅ 执行日志已创建 - ID: {log.id}")
            return log.id
        except Exception as e:
            logger.error(f"❌ 创建执行日志失败: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    async def _update_execution_log(
        self,
        log_id: str,
        result: dict[str, Any],
        agent_response: str | None,
        execution_time: int,
    ):
        """更新执行日志（最终结果）"""
        db = next(get_db())
        try:
            log = (
                db.query(AlertExecutionLog)
                .filter(AlertExecutionLog.id == log_id)
                .first()
            )

            if not log:
                logger.warning(f"⚠️  执行日志不存在 - ID: {log_id}")
                return

            # 提取字段
            email_sent = result.get("email_sent", False)
            success = result.get("success", False)

            # ✅ 关键修复：如果邮件发送成功，说明整个执行流程成功（查询→判断→发送）
            if email_sent:
                success = True
                logger.info(f"✅ 邮件发送成功 - 自动标记执行成功 (log_id: {log_id})")

            # 更新字段（确保 JSON 可序列化）
            log.success = success
            log.triggered = result.get("triggered", False)
            log.current_value = self._make_json_serializable(
                result.get("current_value")
            )
            log.threshold = result.get("threshold")
            log.threshold_operator = result.get("threshold_operator")
            log.email_sent = email_sent
            log.to_emails = self._make_json_serializable(result.get("to_emails"))
            log.agent_response = agent_response
            log.error_message = result.get("error")
            log.execution_duration_ms = execution_time
            log.completed_at = datetime.now(UTC)

            db.commit()
            logger.debug(f"✅ 执行日志已更新 - ID: {log_id}")
        except Exception as e:
            logger.error(f"❌ 更新执行日志失败: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def _build_enhanced_query(
        self,
        query_description: str,
        alert_name: str,
        account_info: dict[str, Any],
        alert_id: str,
        org_id: str,
        is_test: bool,
    ) -> str:
        """构造增强查询提示词（参考 websocket.py）

        Args:
            query_description: 自然语言告警描述
            alert_name: 告警显示名称（用于邮件主题）
            account_info: 账号信息
            alert_id: 告警ID
            org_id: 组织ID
            is_test: 是否为测试模式

        Returns:
            str: 增强后的查询提示词
        """
        account_type = account_info.get("account_type", "aws")

        # ============ P1: 邮件主题生成与验证 ============
        # 邮件主题长度限制（AWS SES 建议 ≤78 字符，最大 998 字符）
        MAX_SUBJECT_LENGTH = 78

        # 测试模式下的邮件主题格式
        email_subject = f"[测试] {alert_name}" if is_test else alert_name

        # 长度检查和截断
        if len(email_subject) > MAX_SUBJECT_LENGTH:
            original_length = len(email_subject)
            email_subject = email_subject[: MAX_SUBJECT_LENGTH - 3] + "..."
            logger.warning(
                f"⚠️  邮件主题超长已截断 - "
                f"原长度: {original_length}, "
                f"截断后: {len(email_subject)}, "
                f"告警名称: {alert_name[:30]}..."
            )

        # 记录邮件主题生成日志（P1：可观测性）
        logger.info(
            "📧 邮件主题已生成",
            extra={
                "alert_id": alert_id,
                "alert_name": alert_name,
                "email_subject": email_subject,
                "subject_length": len(email_subject),
                "is_test": is_test,
                "account_type": account_type,
            },
        )

        if account_type == "gcp":
            enhanced_query = f"""用户查询: {query_description}

告警名称: {alert_name}

当前查询的 GCP 账号:
- 账号名称: {account_info.get("alias", "Unknown")}
- GCP 项目 ID: {account_info.get("project_id", "Unknown")}
- 组织 ID: {account_info.get("organization_id", "Unknown")}

告警ID: {alert_id}
组织ID: {org_id}
{"模式: 测试模式" if is_test else "模式: 正常执行"}

⚠️ 重要：发送邮件时，请使用上述"告警名称"作为邮件主题（subject）。
邮件主题格式："{email_subject}"

请执行告警检查并返回纯 JSON 格式的结果。"""
        else:
            enhanced_query = f"""用户查询: {query_description}

告警名称: {alert_name}

当前查询的 AWS 账号:
- 账号别名: {account_info.get("alias", "Unknown")}
- AWS 账号 ID: {account_info.get("account_id", "Unknown")}

告警ID: {alert_id}
组织ID: {org_id}
{"模式: 测试模式" if is_test else "模式: 正常执行"}

⚠️ 重要：发送邮件时，请使用上述"告警名称"作为邮件主题（subject）。
邮件主题格式："{email_subject}"

请执行告警检查并返回纯 JSON 格式的结果。"""

        return enhanced_query.strip()

    def _parse_agent_response(self, response: str) -> dict[str, Any]:
        """解析 Agent 响应（提取 JSON）"""
        # 策略1: 直接解析 JSON
        try:
            result = json.loads(response.strip())
            if isinstance(result, dict) and "success" in result:
                logger.debug("✅ 使用策略1解析成功（直接JSON）")
                return result
        except json.JSONDecodeError:
            pass

        # 策略2: 提取 JSON 代码块
        json_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        matches = re.findall(json_block_pattern, response, re.DOTALL)

        if matches:
            for match in matches:
                try:
                    result = json.loads(match.strip())
                    if isinstance(result, dict) and "success" in result:
                        logger.warning("⚠️  使用策略2解析成功（提取代码块）")
                        return result
                except json.JSONDecodeError:
                    continue

        # 策略3: 提取最外层 JSON 对象
        json_object_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_object_pattern, response, re.DOTALL)

        if matches:
            matches_sorted = sorted(matches, key=len, reverse=True)
            for match in matches_sorted:
                try:
                    result = json.loads(match)
                    if isinstance(result, dict) and "success" in result:
                        logger.warning("⚠️  使用策略3解析成功（提取JSON对象）")
                        return result
                except json.JSONDecodeError:
                    continue

        # 解析失败
        logger.error("❌ 无法解析 Agent 响应为有效 JSON")
        logger.error(f"   原始响应（前500字符）: {response[:500]}")

        return {
            "success": False,
            "triggered": False,
            "email_sent": False,
            "message": "Agent 响应格式错误或无法解析",
            "error": f"无法解析 Agent 响应: {response[:200]}...",
            "raw_response": response,
        }

    def _make_json_serializable(self, obj: Any, _depth: int = 0) -> Any:
        """确保对象可以被 JSON 序列化

        Args:
            obj: 任意对象
            _depth: 递归深度（内部使用，防止无限递归）

        Returns:
            JSON 可序列化的对象

        Note:
            - 当前场景下，输入来自 JSON 解析，不会有循环引用
            - 添加深度限制作为额外防护（最大深度100）
        """
        from uuid import UUID

        # 防护：限制递归深度（正常JSON嵌套不会超过100层）
        if _depth > 100:
            logger.error(f"❌ 递归深度超限 (>100)，可能存在循环引用或过深嵌套")
            return "<RecursionLimitExceeded>"

        if obj is None:
            return None

        # UUID 对象转字符串
        if isinstance(obj, UUID):
            return str(obj)

        # 列表递归处理
        if isinstance(obj, list):
            return [self._make_json_serializable(item, _depth + 1) for item in obj]

        # 字典递归处理
        if isinstance(obj, dict):
            return {
                key: self._make_json_serializable(value, _depth + 1)
                for key, value in obj.items()
            }

        # 其他不可序列化的对象转字符串
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            logger.warning(f"⚠️  对象无法序列化，转换为字符串: {type(obj)}")
            return str(obj)


__all__ = ["AlertAgentManager"]
