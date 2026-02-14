"""
CUD Handler - Cost Comparison and Flexible CUD Analysis

Provides cost comparison tools and flexible CUD analysis:
- CUD vs On-Demand comparison
- Flexible CUD analysis
- Enhanced purchase recommendations
"""

import logging
from datetime import datetime, timedelta

from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context


from constants import DEFAULT_LOOKBACK_DAYS
from utils.bigquery_helper import validate_date_range
from utils.multi_account_client import (
    get_bigquery_client_for_account,
)


async def get_cud_vs_ondemand_comparison(
    ctx: Context,
    project_id: str | None = None,
    billing_account_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    scenario: str = "actual",
    account_id: str | None = None,
) -> dict[str, Any]:
    """Compare CUD costs vs on-demand pricing with scenario analysis

    Provides cost comparison across multiple scenarios:
    - actual: Current situation with CUD
    - no_cud: Hypothetical scenario without CUD
    - optimal: Optimized CUD configuration

    Args:
        ctx: MCP context
        project_id: GCP project ID
        billing_account_id: Billing account ID (org-level)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        scenario: Scenario type (actual, no_cud, optimal)
        account_id: Optional GCP account ID

    Returns:
        Detailed cost comparison with savings analysis
    """
    operation = "get_cud_vs_ondemand_comparison"

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
    logger.info(f"🔍 {operation} - Scope: {scope}, Scenario: {scenario}")

    try:
        if not project_id and not billing_account_id:
            return {
                "success": False,
                "error_message": "project_id or billing_account_id required",
                "data": None,
            }

        # Date range
        if not start_date or not end_date:
            end_datetime = datetime.now() - timedelta(days=2)
            start_datetime = end_datetime - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            start_date = start_datetime.strftime("%Y-%m-%d")
            end_date = end_datetime.strftime("%Y-%m-%d")

        if not validate_date_range(start_date, end_date):
            return {"success": False, "error_message": "Invalid date range", "data": None}

        # Get BigQuery client
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
        scope_filter = (
            f"AND project.id = '{project_id}'"
            if project_id
            else f"AND billing_account_id = '{billing_account_id}'"
        )

        # Query actual costs
        query = f"""
        SELECT
          DATE(_PARTITIONDATE) AS date,
          -- Commitment cost
          SUM(CASE WHEN cost_type = 'commitment' THEN cost ELSE 0 END) AS commitment_cost,
          -- On-demand cost (not covered by CUD)
          SUM(CASE
            WHEN NOT EXISTS(SELECT 1 FROM UNNEST(credits) WHERE type = 'COMMITTED_USAGE_DISCOUNT')
            THEN cost ELSE 0
          END) AS on_demand_cost,
          -- CUD credits (discount value)
          ABS(SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c WHERE c.type = 'COMMITTED_USAGE_DISCOUNT'))) AS cud_credits,
          -- Total cost
          SUM(cost) AS total_cost,
          currency
        FROM `{table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
          AND service.description = 'Compute Engine'
          {scope_filter}
        GROUP BY date, currency
        ORDER BY date
        """

        query_job = bq_client.query(query)
        results = query_job.result()

        # Process results
        cost_breakdown = []
        total_commitment = 0.0
        total_on_demand = 0.0
        total_credits = 0.0
        total_actual = 0.0
        currency = "USD"

        for row in results:
            commitment = float(row.commitment_cost or 0)
            on_demand = float(row.on_demand_cost or 0)
            credits = float(row.cud_credits or 0)
            actual = float(row.total_cost or 0)

            # Calculate scenarios
            # Scenario 1: Actual (with CUD)
            actual_cost = commitment + on_demand

            # Scenario 2: No CUD (all on-demand)
            # On-demand equivalent = actual usage that was covered by CUD + current on-demand
            no_cud_cost = (commitment + credits) + on_demand

            # Scenario 3: Optimal (assuming 95% utilization)
            optimal_commitment = commitment * 0.95
            optimal_on_demand = on_demand + (commitment * 0.05)
            optimal_cost = optimal_commitment + optimal_on_demand

            cost_breakdown.append(
                {
                    "date": str(row.date),
                    "actual_cost": round(actual_cost, 2),
                    "no_cud_cost": round(no_cud_cost, 2),
                    "optimal_cost": round(optimal_cost, 2),
                    "daily_savings": round(no_cud_cost - actual_cost, 2),
                    "optimization_opportunity": round(actual_cost - optimal_cost, 2),
                    "currency": row.currency,
                }
            )

            total_commitment += commitment
            total_on_demand += on_demand
            total_credits += credits
            total_actual += actual
            currency = row.currency

        # Calculate summary
        actual_total = total_commitment + total_on_demand
        no_cud_total = (total_commitment + total_credits) + total_on_demand
        optimal_total = (total_commitment * 0.95) + (total_on_demand + total_commitment * 0.05)

        savings_vs_no_cud = no_cud_total - actual_total
        savings_pct = (savings_vs_no_cud / no_cud_total * 100) if no_cud_total > 0 else 0
        optimization_opp = actual_total - optimal_total

        # Pricing analysis
        730 * DEFAULT_LOOKBACK_DAYS / 30  # Approximate hours
        avg_cud_discount = (
            (total_credits / (total_commitment + total_credits) * 100)
            if (total_commitment + total_credits) > 0
            else 0
        )

        comparison_summary = {
            "period": f"{start_date} to {end_date}",
            "actual_cost": {
                "commitment_cost": round(total_commitment, 2),
                "on_demand_cost": round(total_on_demand, 2),
                "total_cost": round(actual_total, 2),
                "description": "实际花费（有 CUD）",
            },
            "no_cud_scenario": {
                "estimated_on_demand_cost": round(no_cud_total, 2),
                "total_cost": round(no_cud_total, 2),
                "description": "假设场景：如果不购买 CUD",
            },
            "optimal_scenario": {
                "optimized_commitment": round(total_commitment * 0.95, 2),
                "estimated_on_demand": round(total_on_demand + total_commitment * 0.05, 2),
                "total_cost": round(optimal_total, 2),
                "description": "优化场景：调整承诺配置后",
            },
            "savings": {
                "actual_vs_no_cud": round(savings_vs_no_cud, 2),
                "actual_vs_optimal": round(-optimization_opp, 2),
                "savings_percentage": round(savings_pct, 2),
                "optimization_opportunity": round(optimization_opp, 2),
            },
        }

        pricing_analysis = {
            "average_cud_discount": round(avg_cud_discount, 2),
            "effective_savings_rate": round(savings_pct, 2),
            "break_even_utilization": 60.0,  # Simplified
        }

        recommendations = []
        if optimization_opp > 0:
            recommendations.append(
                {
                    "scenario": "optimal",
                    "action": f"减少承诺 {round((1 - 0.95) * 100, 1)}%",
                    "rationale": "基于历史平均利用率优化",
                    "potential_savings": round(optimization_opp, 2),
                }
            )

        logger.info(f"✅ {operation} - Savings: ${savings_vs_no_cud:.2f} ({savings_pct:.1f}%)")

        return {
            "success": True,
            "data": {
                "comparison_summary": comparison_summary,
                "cost_breakdown": cost_breakdown,
                "pricing_analysis": pricing_analysis,
                "recommendations": recommendations,
                "currency": currency,
            },
            "account_id": account_id,
            "message": f"CUD vs On-Demand: 节省 ${savings_vs_no_cud:.2f} ({savings_pct:.1f}%)",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        return {"success": False, "error_message": error_msg, "data": None}


async def get_flexible_cud_analysis(
    ctx: Context,
    project_id: str | None = None,
    billing_account_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    granularity: str = "MONTHLY",
    account_id: str | None = None,
) -> dict[str, Any]:
    """Analyze Flexible (Spend-based) CUD usage

    Provides detailed analysis of Flexible CUD commitments including:
    - Subscription details
    - Service-level spend breakdown
    - Comparison with Resource-based CUD

    Args:
        ctx: MCP context
        project_id: GCP project ID
        billing_account_id: Billing account ID
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        granularity: DAILY or MONTHLY
        account_id: Optional GCP account ID

    Returns:
        Flexible CUD analysis with recommendations
    """
    operation = "get_flexible_cud_analysis"

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

        # Date range
        if not start_date or not end_date:
            end_datetime = datetime.now() - timedelta(days=2)
            start_datetime = end_datetime - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            start_date = start_datetime.strftime("%Y-%m-%d")
            end_date = end_datetime.strftime("%Y-%m-%d")

        if not validate_date_range(start_date, end_date):
            return {"success": False, "error_message": "Invalid date range", "data": None}

        # Get BigQuery client
        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None
        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        bq_client = get_bigquery_client_for_account(account_id)

        # Query 1: Get Flexible CUD subscriptions
        # Note: This requires the cud_subscriptions_export table
        dataset_parts = table_name.rsplit(".", 1)
        cud_table = (
            f"{dataset_parts[0]}.cud_subscriptions_export"
            if len(dataset_parts) == 2
            else "cud_subscriptions_export"
        )

        subscription_query = f"""
        SELECT
          cud_product.id AS subscription_id,
          cud_product.display_name,
          cud_product.commitment_amount,
          cud_product.unit,
          cud_product.region,
          cud_product.start_time,
          cud_product.end_time,
          cud_product.term
        FROM `{cud_table}`
        WHERE _PARTITIONDATE = CURRENT_DATE()
        ORDER BY cud_product.start_time DESC
        """

        subscription_details = []
        total_commitment = 0.0

        try:
            sub_job = bq_client.query(subscription_query)
            sub_results = sub_job.result()

            for row in sub_results:
                subscription_details.append(
                    {
                        "subscription_id": row.subscription_id,
                        "display_name": row.display_name,
                        "commitment_amount": float(row.commitment_amount or 0),
                        "unit": row.unit,
                        "region": row.region or "global",
                        "start_time": str(row.start_time) if row.start_time else None,
                        "end_time": str(row.end_time) if row.end_time else None,
                        "term": row.term,
                        "status": "ACTIVE",  # Simplified
                    }
                )
                total_commitment += float(row.commitment_amount or 0)
        except Exception as e:
            logger.warning(f"Could not query CUD subscriptions table: {e}")

        # Query 2: Get Flexible CUD usage by service
        scope_filter = (
            f"AND project.id = '{project_id}'"
            if project_id
            else f"AND billing_account_id = '{billing_account_id}'"
        )

        usage_query = f"""
        SELECT
          service.description AS service,
          SUM(cost) + ABS(SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c WHERE c.type = 'COMMITTED_USAGE_DISCOUNT_DOLLAR_BASE'))) AS spend_covered,
          currency
        FROM `{table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
          AND EXISTS(
            SELECT 1 FROM UNNEST(credits)
            WHERE type = 'COMMITTED_USAGE_DISCOUNT_DOLLAR_BASE'
          )
          {scope_filter}
        GROUP BY service, currency
        ORDER BY spend_covered DESC
        """

        service_breakdown = []
        total_spend = 0.0
        currency = "USD"

        usage_job = bq_client.query(usage_query)
        usage_results = usage_job.result()

        for row in usage_results:
            spend = float(row.spend_covered or 0)
            percentage = (spend / total_commitment * 100) if total_commitment > 0 else 0

            service_breakdown.append(
                {
                    "service": row.service,
                    "spend_covered": round(spend, 2),
                    "percentage_of_commitment": round(percentage, 2),
                    "currency": row.currency,
                }
            )

            total_spend += spend
            currency = row.currency

        # Calculate utilization
        utilization = (total_spend / total_commitment * 100) if total_commitment > 0 else 0
        unused = max(0, total_commitment - total_spend)

        # Comparison with Resource-based CUD
        flexible_discount = 25.0  # Typical Flexible CUD discount
        resource_discount = 45.0  # Typical Resource-based CUD discount

        comparison = {
            "flexible_cud_discount": flexible_discount,
            "resource_based_discount": resource_discount,
            "flexibility_premium": resource_discount - flexible_discount,
            "recommendation": (
                "考虑部分转换为 Resource-based CUD 以获得更高折扣"
                if resource_discount > flexible_discount
                else "Flexible CUD 提供更好的灵活性"
            ),
        }

        logger.info(
            f"✅ {operation} - Utilization: {utilization:.1f}%, Services: {len(service_breakdown)}"
        )

        return {
            "success": True,
            "data": {
                "flexible_cud_summary": {
                    "total_commitment": round(total_commitment, 2),
                    "total_spend": round(total_spend, 2),
                    "utilization_percentage": round(utilization, 2),
                    "unused_commitment": round(unused, 2),
                    "discount_rate": flexible_discount,
                    "covered_services": [s["service"] for s in service_breakdown],
                    "currency": currency,
                },
                "subscription_details": subscription_details,
                "service_breakdown": service_breakdown,
                "comparison_with_resource_based": comparison,
                "request_parameters": {
                    "project_id": project_id,
                    "billing_account_id": billing_account_id,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            },
            "account_id": account_id,
            "message": f"Flexible CUD: {utilization:.1f}% utilization across {len(service_breakdown)} services",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        return {"success": False, "error_message": error_msg, "data": None}
