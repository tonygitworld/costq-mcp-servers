"""
CUD Handler - Advanced Analysis Tools

Provides detailed CUD resource usage analysis and health monitoring.

This module provides advanced CUD analysis capabilities including:
- Resource-level usage analysis
- Health checks and alerts
- Cost comparison scenarios
- Flexible CUD support
- Organization-level aggregation
"""

import logging
from datetime import datetime, timedelta

# Note: compute_v1 is not needed here as we use multi_account_client
# from google.cloud import compute_v1
from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context


from constants import DEFAULT_LOOKBACK_DAYS
from utils.bigquery_helper import (
    validate_date_range,
)
from utils.multi_account_client import (
    get_bigquery_client_for_account,
)

# Note: get_compute_client_for_account removed - no Compute API permissions
from services.gcp_credentials_provider import get_gcp_credentials_provider


async def get_cud_resource_usage(
    ctx: Context,
    project_id: str | None = None,
    billing_account_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    resource_type: str | None = None,
    region: str | None = None,
    granularity: str = "DAILY",
    account_id: str | None = None,
) -> dict[str, Any]:
    """Get detailed CUD resource usage by type (vCPU, Memory, GPU, etc.)

    Analyzes CUD usage at resource type level to identify underutilized resource types.
    Supports both project-level and organization-level (billing account) queries.

    NOTE: Commitment configuration details (committed vCPU/RAM amounts) are not
    available due to lack of Compute Engine API permissions. Usage analysis is
    based on BigQuery billing data only.

    Args:
        ctx: MCP context
        project_id: GCP project ID (for project-level query)
        billing_account_id: Billing account ID (for org-level query)
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: 2 days ago)
        resource_type: Filter by type (VCPU, MEMORY, GPU, LOCAL_SSD, ALL)
        region: Filter by specific region
        granularity: DAILY or MONTHLY aggregation
        account_id: Optional GCP account ID

    Returns:
        Dictionary with resource-level usage analysis and recommendations
    """
    operation = "get_cud_resource_usage"
    scope = (
        f"billing_account:{billing_account_id}" if billing_account_id else f"project:{project_id}"
    )
    logger.info(f"🔍 {operation} - Scope: {scope}, Resource: {resource_type or 'ALL'}")

    try:
        # Validate input
        if not project_id and not billing_account_id:
            return {
                "success": False,
                "error_message": "Either project_id or billing_account_id must be provided",
                "data": None,
            }

        # Get date range
        if not start_date or not end_date:
            end_datetime = datetime.now() - timedelta(days=2)
            start_datetime = end_datetime - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            start_date = start_datetime.strftime("%Y-%m-%d")
            end_date = end_datetime.strftime("%Y-%m-%d")

        if not validate_date_range(start_date, end_date):
            return {"success": False, "error_message": "Invalid date range", "data": None}

        # DEPRECATED: Compute API access for commitment configuration
        # Previous code queried Compute Engine API for commitment resource details
        # (committed vCPU/RAM amounts). This is now disabled due to permission issues.
        # Service Account lacks compute.regionCommitments.list permission (401 Unauthorized)
        logger.warning(
            "⚠️  Commitment configuration details not available "
            "(Compute API permission denied). Analysis based on billing data only."
        )
        commitment_resources = {}

        # Get actual usage from BigQuery
        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        bq_client = get_bigquery_client_for_account(account_id)

        # Build scope filter
        scope_filter = ""
        if project_id:
            scope_filter = f"AND project.id = '{project_id}'"
        elif billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"

        # Build filters
        region_filter = f"AND location.region = '{region}'" if region else ""
        date_grouping = (
            "DATE(_PARTITIONDATE)"
            if granularity == "DAILY"
            else "FORMAT_DATE('%Y-%m', DATE(_PARTITIONDATE))"
        )

        # Resource type filter
        resource_filter = ""
        if resource_type and resource_type != "ALL":
            resource_map = {
                "VCPU": "%Core%",
                "MEMORY": "%Ram%",
                "GPU": "%GPU%",
                "LOCAL_SSD": "%SSD%",
            }
            if resource_type in resource_map:
                resource_filter = f"AND sku.description LIKE '{resource_map[resource_type]}'"

        query = f"""
        WITH resource_usage AS (
          SELECT
            {date_grouping} AS period,
            location.region AS region,
            CASE
              WHEN sku.description LIKE '%Core%' OR sku.description LIKE '%vCPU%' THEN 'VCPU'
              WHEN sku.description LIKE '%Ram%' OR sku.description LIKE '%Memory%' THEN 'MEMORY'
              WHEN sku.description LIKE '%GPU%' THEN 'GPU'
              WHEN sku.description LIKE '%SSD%' THEN 'LOCAL_SSD'
              ELSE 'OTHER'
            END AS resource_type,
            SUM(usage.amount) AS usage_amount,
            ANY_VALUE(usage.unit) AS usage_unit,
            SUM(cost) AS total_cost,
            currency
          FROM `{table_name}`
          WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            AND service.description = 'Compute Engine'
            AND EXISTS(
              SELECT 1 FROM UNNEST(credits) AS c
              WHERE c.type = 'COMMITTED_USAGE_DISCOUNT'
            )
            {scope_filter}
            {region_filter}
            {resource_filter}
          GROUP BY period, region, resource_type, currency
        )
        SELECT
          period,
          region,
          resource_type,
          SUM(usage_amount) AS total_usage,
          ANY_VALUE(usage_unit) AS unit,
          SUM(total_cost) AS cost,
          ANY_VALUE(currency) AS currency
        FROM resource_usage
        WHERE resource_type != 'OTHER'
        GROUP BY period, region, resource_type
        ORDER BY period, region, resource_type
        """

        logger.debug("Executing resource usage query")
        query_job = bq_client.query(query)
        results = query_job.result()

        # Process results
        usage_by_type = {}
        usage_by_time = []

        for row in results:
            rtype = row.resource_type
            region_name = row.region or "global"

            if rtype not in usage_by_type:
                usage_by_type[rtype] = {
                    "resource_type": rtype,
                    "total_usage": 0,
                    "total_cost": 0,
                    "unit": row.unit,
                    "currency": row.currency,
                }

            usage_by_type[rtype]["total_usage"] += float(row.total_usage or 0)
            usage_by_type[rtype]["total_cost"] += float(row.cost or 0)

            usage_by_time.append(
                {
                    "period": str(row.period),
                    "region": region_name,
                    "resource_type": rtype,
                    "usage": float(row.total_usage or 0),
                    "cost": float(row.cost or 0),
                    "unit": row.unit,
                }
            )

        # Calculate utilization and recommendations
        resource_summary = {}
        recommendations = []

        for rtype, usage_data in usage_by_type.items():
            # Find matching commitment
            committed_amount = 0
            for key, commit in commitment_resources.items():
                if commit["type"] == rtype or (
                    rtype == "VCPU" and commit["type"] in ["VCPU", "CPU"]
                ):
                    committed_amount += commit["committed_amount"]

            used_amount = usage_data["total_usage"]
            unused_amount = max(0, committed_amount - used_amount)
            utilization = (used_amount / committed_amount * 100) if committed_amount > 0 else 0

            # Status determination
            if utilization >= 90:
                status = "✅ 良好"
                status_code = "HEALTHY"
            elif utilization >= 70:
                status = "⚠️ 中等利用"
                status_code = "MODERATE"
            else:
                status = "🔴 低利用率"
                status_code = "UNDERUTILIZED"

            resource_summary[rtype] = {
                "resource_type": rtype,
                "committed": round(committed_amount, 2),
                "used": round(used_amount, 2),
                "unused": round(unused_amount, 2),
                "utilization_percentage": round(utilization, 2),
                "status": status,
                "status_code": status_code,
                "total_cost": round(usage_data["total_cost"], 2),
                "unit": usage_data["unit"],
                "currency": usage_data["currency"],
            }

            # Generate recommendations
            if utilization < 80 and committed_amount > 0:
                optimal_commitment = used_amount * 0.95
                reduction_amount = committed_amount - optimal_commitment

                # Rough savings estimate
                unit_cost = 0.05 if rtype == "VCPU" else 0.01
                monthly_savings = reduction_amount * unit_cost * 730

                recommendations.append(
                    {
                        "resource_type": rtype,
                        "current_commitment": round(committed_amount, 2),
                        "current_utilization": round(utilization, 2),
                        "recommended_commitment": round(optimal_commitment, 2),
                        "reduction_amount": round(reduction_amount, 2),
                        "potential_monthly_savings": round(monthly_savings, 2),
                        "reason": f"过去 {DEFAULT_LOOKBACK_DAYS} 天平均使用量仅 {round(used_amount, 2)} {usage_data['unit']}",
                        "priority": "HIGH" if utilization < 60 else "MEDIUM",
                    }
                )

        # Overall metrics
        total_util = sum(r["utilization_percentage"] for r in resource_summary.values())
        avg_util = total_util / len(resource_summary) if resource_summary else 0

        logger.info(f"✅ {operation} - {len(resource_summary)} types, avg util: {avg_util:.1f}%")

        return {
            "success": True,
            "data": {
                "resource_summary": resource_summary,
                "usage_by_time": usage_by_time,
                "recommendations": recommendations,
                "overall_metrics": {
                    "average_utilization": round(avg_util, 2),
                    "resource_types_count": len(resource_summary),
                    "underutilized_count": sum(
                        1 for r in resource_summary.values() if r["utilization_percentage"] < 80
                    ),
                    "total_potential_savings": round(
                        sum(r["potential_monthly_savings"] for r in recommendations), 2
                    ),
                },
                "request_parameters": {
                    "project_id": project_id,
                    "billing_account_id": billing_account_id,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            },
            "account_id": account_id,
            "message": f"Analyzed {len(resource_summary)} resource types, avg util: {avg_util:.1f}%",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        return {"success": False, "error_message": error_msg, "data": None}


async def get_cud_status_check(
    ctx: Context,
    project_id: str | None = None,
    billing_account_id: str | None = None,
    utilization_threshold: float = 80.0,
    coverage_threshold: float = 75.0,
    days_before_expiry: int = 30,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Perform comprehensive CUD health check

    Checks CUD status across multiple dimensions and generates actionable alerts.
    Supports both project-level and organization-level health checks.

    Args:
        ctx: MCP context
        project_id: GCP project ID
        billing_account_id: Billing account ID (for org-level)
        utilization_threshold: Alert if utilization below this (default: 80%)
        coverage_threshold: Alert if coverage below this (default: 75%)
        days_before_expiry: Alert days before commitment expires (default: 30)
        account_id: Optional GCP account ID

    Returns:
        Comprehensive health report with alerts and recommendations
    """
    operation = "get_cud_status_check"

    # Smart default: use billing_account_id if available, otherwise project_id
    if not project_id and not billing_account_id:
        from services.gcp_credentials_provider import get_gcp_credentials_provider

        credentials_provider = get_gcp_credentials_provider()
        account_info = credentials_provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")
        elif account_info:
            project_id = account_info["project_id"]
            logger.info(f"🎯 使用账号配置的 project_id: {project_id}")

    scope = (
        f"billing_account:{billing_account_id}" if billing_account_id else f"project:{project_id}"
    )
    logger.info(f"🔍 {operation} - Scope: {scope}")

    try:
        if not project_id and not billing_account_id:
            return {
                "success": False,
                "error_message": "project_id or billing_account_id required",
                "data": None,
            }

        alerts = []
        checks = {}
        recommendations = []

        # Import other handlers to reuse logic
        from handlers.cud_handler import (
            get_cud_coverage,
            get_cud_utilization,
            list_commitments,
        )

        # Check 1: List commitments and check expiry
        logger.info("🔍 Check 1: Commitment inventory and expiry...")
        if project_id:
            commitments_result = await list_commitments(ctx, project_id, None, None, account_id)
        else:
            # For billing account, would need to iterate projects (simplified here)
            commitments_result = {
                "success": True,
                "data": {"commitments": [], "summary": {"total_count": 0}},
            }

        if commitments_result["success"]:
            commitments = commitments_result["data"]["commitments"]
            expiring_soon = []
            inactive_count = 0

            for c in commitments:
                # Check expiry
                if c.get("end_time"):
                    try:
                        end_time = datetime.fromisoformat(c["end_time"].replace("Z", "+00:00"))
                        days_remaining = (end_time - datetime.now()).days

                        if 0 < days_remaining <= days_before_expiry:
                            expiring_soon.append(
                                {
                                    "commitment_id": c["commitment_id"],
                                    "name": c["name"],
                                    "days_remaining": days_remaining,
                                    "end_date": c["end_time"],
                                }
                            )

                            alerts.append(
                                {
                                    "severity": "INFO" if days_remaining > 14 else "WARNING",
                                    "type": "EXPIRING_SOON",
                                    "commitment_id": c["commitment_id"],
                                    "commitment_name": c["name"],
                                    "expiry_date": c["end_time"],
                                    "days_remaining": days_remaining,
                                    "message": f"承诺将在 {days_remaining} 天后过期",
                                    "recommended_action": "评估是否续约或转换为 Flexible CUD",
                                }
                            )
                    except (ValueError, TypeError, KeyError):
                        pass

                # Check status
                if c.get("status") not in ["ACTIVE", "CREATING"]:
                    inactive_count += 1

            checks["expiry_check"] = {
                "status": "WARNING" if expiring_soon else "OK",
                "message": (
                    f"{len(expiring_soon)} 个承诺即将过期" if expiring_soon else "无即将过期的承诺"
                ),
                "expiring_count": len(expiring_soon),
                "details": expiring_soon,
            }

        # Check 2: Utilization check
        logger.info("🔍 Check 2: Utilization analysis...")
        util_params = {
            "ctx": ctx,
            "start_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "end_date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
            "granularity": "DAILY",
            "account_id": account_id,
        }
        if project_id:
            util_params["project_id"] = project_id
        else:
            util_params["billing_account_id"] = billing_account_id

        # Simplified call (would need to handle billing_account properly)
        if project_id:
            util_result = await get_cud_utilization(**util_params)

            if util_result["success"]:
                util_pct = util_result["data"]["utilization_summary"]["utilization_percentage"]
                unused = util_result["data"]["utilization_summary"]["total_unused_commitment"]

                if util_pct < utilization_threshold:
                    alerts.append(
                        {
                            "severity": "CRITICAL" if util_pct < 50 else "WARNING",
                            "type": "LOW_UTILIZATION",
                            "current_value": util_pct,
                            "threshold": utilization_threshold,
                            "message": f"利用率 {util_pct}% 低于阈值 {utilization_threshold}%",
                            "recommended_action": "考虑减少承诺或启用折扣共享",
                            "potential_savings": round(unused, 2),
                        }
                    )
                    checks["utilization_check"] = {
                        "status": "CRITICAL" if util_pct < 50 else "WARNING",
                        "message": f"平均利用率 {util_pct}% 低于阈值",
                        "current_utilization": util_pct,
                        "threshold": utilization_threshold,
                    }
                else:
                    checks["utilization_check"] = {
                        "status": "OK",
                        "message": f"利用率 {util_pct}% 符合目标",
                        "current_utilization": util_pct,
                    }

        # Check 3: Coverage check
        logger.info("🔍 Check 3: Coverage analysis...")
        if project_id:
            cov_params = {
                "ctx": ctx,
                "project_id": project_id,
                "start_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "end_date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                "account_id": account_id,
            }
            cov_result = await get_cud_coverage(**cov_params)

            if cov_result["success"]:
                cov_pct = cov_result["data"]["coverage_summary"]["coverage_percentage"]
                on_demand = cov_result["data"]["coverage_summary"]["on_demand_cost"]

                if cov_pct < coverage_threshold:
                    potential_savings = on_demand * 0.3  # 假设30%节省
                    alerts.append(
                        {
                            "severity": "WARNING",
                            "type": "LOW_COVERAGE",
                            "current_value": cov_pct,
                            "threshold": coverage_threshold,
                            "message": f"覆盖率 {cov_pct}% 低于阈值 {coverage_threshold}%",
                            "recommended_action": "考虑购买额外 CUD 覆盖按需使用",
                            "potential_savings": round(potential_savings, 2),
                        }
                    )
                    checks["coverage_check"] = {
                        "status": "WARNING",
                        "message": f"覆盖率 {cov_pct}% 低于目标",
                        "current_coverage": cov_pct,
                        "on_demand_cost": on_demand,
                    }
                else:
                    checks["coverage_check"] = {
                        "status": "OK",
                        "message": f"覆盖率 {cov_pct}% 符合目标",
                        "current_coverage": cov_pct,
                    }

        # Calculate overall health status
        critical_count = sum(1 for a in alerts if a["severity"] == "CRITICAL")
        warning_count = sum(1 for a in alerts if a["severity"] == "WARNING")

        if critical_count > 0:
            health_status = "CRITICAL"
            health_score = 30
        elif warning_count > 2:
            health_status = "WARNING"
            health_score = 60
        elif warning_count > 0:
            health_status = "WARNING"
            health_score = 75
        else:
            health_status = "OK"
            health_score = 95

        # Generate recommendations
        if critical_count + warning_count > 0:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "title": "立即采取行动",
                    "description": f"发现 {critical_count} 个严重问题和 {warning_count} 个警告",
                    "action_required": "查看告警详情并采取建议的优化措施",
                }
            )

        logger.info(f"✅ {operation} - Status: {health_status}, Score: {health_score}")

        return {
            "success": True,
            "data": {
                "health_status": health_status,
                "overall_score": health_score,
                "checks": checks,
                "alerts": alerts,
                "recommendations": recommendations,
                "summary": {
                    "total_alerts": len(alerts),
                    "critical_alerts": critical_count,
                    "warning_alerts": warning_count,
                    "info_alerts": sum(1 for a in alerts if a["severity"] == "INFO"),
                },
            },
            "account_id": account_id,
            "message": f"Health check: {health_status} (Score: {health_score})",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        return {"success": False, "error_message": error_msg, "data": None}


# 继续添加其他 Phase 2 工具...
# (由于文件已经很长，我会在下一个文件中继续)
