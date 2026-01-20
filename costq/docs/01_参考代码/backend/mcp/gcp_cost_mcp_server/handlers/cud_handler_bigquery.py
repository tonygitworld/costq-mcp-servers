"""
CUD Commitments List - BigQuery Implementation

This module provides a BigQuery-based implementation for listing CUD commitments.
This is significantly faster than the Compute Engine API approach for organization-level queries.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.mcp.gcp_cost_mcp_server.utils.multi_account_client import (
    get_bigquery_client_for_account,
)
from backend.services.gcp_credentials_provider import get_gcp_credentials_provider


async def list_commitments_from_bigquery(
    ctx: Context,
    project_id: str | None = None,
    billing_account_id: str | None = None,
    region: str | None = None,
    account_id: str | None = None,
    days_lookback: int = 30,
) -> dict[str, Any]:
    """List CUD commitments from BigQuery billing export

    This function analyzes billing data to identify CUD commitments.
    Much faster than Compute Engine API for organization-level queries.

    Args:
        ctx: MCP context
        project_id: GCP project ID (optional, for single project)
        billing_account_id: Billing account ID (recommended for org-level)
        region: Filter by specific region
        account_id: GCP account ID for credentials
        days_lookback: Number of days to analyze (default: 30)

    Returns:
        Dictionary with commitment information extracted from billing data
    """
    operation = "list_commitments_from_bigquery"

    # Smart default
    if not project_id and not billing_account_id:
        credentials_provider = get_gcp_credentials_provider()
        account_info = credentials_provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")
        elif account_info:
            project_id = account_info["project_id"]
            logger.info(f"🎯 使用账号配置的 project_id: {project_id}")

    logger.info(f"🔍 {operation} - 从 BigQuery 查询 CUD 承诺数据")

    try:
        # Get BigQuery client and table name
        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id or "default")

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        bq_client = get_bigquery_client_for_account(account_id)

        # Calculate date range
        end_date = datetime.now() - timedelta(days=2)
        start_date = end_date - timedelta(days=days_lookback)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Build scope filter
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
            logger.info(f"📊 查询范围: Billing Account {billing_account_id}")
        else:
            scope_filter = f"AND project.id = '{project_id}'"
            logger.info(f"📊 查询范围: Project {project_id}")

        # Build region filter
        region_filter = f"AND location.region = '{region}'" if region else ""

        # Query to identify CUD commitments from billing data
        # CUD commitments show up as:
        # 1. cost_type = 'commitment' (the monthly commitment fee)
        # 2. credits with type = 'COMMITTED_USAGE_DISCOUNT' (usage covered by CUD)
        query = f"""
        WITH commitment_data AS (
          SELECT
            project.id AS project_id,
            project.name AS project_name,
            location.region AS region,
            location.zone AS zone,
            sku.description AS sku_description,
            -- Commitment costs
            SUM(CASE
              WHEN cost_type = 'commitment' THEN cost
              ELSE 0
            END) AS commitment_cost,
            -- CUD credits applied (indicates active usage)
            ABS(SUM(
              (SELECT SUM(c.amount)
               FROM UNNEST(credits) AS c
               WHERE c.type = 'COMMITTED_USAGE_DISCOUNT')
            )) AS cud_credits_used,
            currency,
            MIN(_PARTITIONDATE) AS first_seen,
            MAX(_PARTITIONDATE) AS last_seen,
            COUNT(DISTINCT _PARTITIONDATE) AS days_active
          FROM `{table_name}`
          WHERE _PARTITIONDATE BETWEEN '{start_date_str}' AND '{end_date_str}'
            AND service.description = 'Compute Engine'
            AND (cost_type = 'commitment' OR
                 EXISTS(SELECT 1 FROM UNNEST(credits) AS c
                        WHERE c.type = 'COMMITTED_USAGE_DISCOUNT'))
            {scope_filter}
            {region_filter}
          GROUP BY project_id, project_name, region, zone, sku_description, currency
          HAVING commitment_cost > 0  -- Only show actual commitments
        ),
        commitment_summary AS (
          SELECT
            project_id,
            project_name,
            region,
            sku_description,
            commitment_cost,
            cud_credits_used,
            -- Utilization percentage
            SAFE_DIVIDE(cud_credits_used, commitment_cost) * 100 AS utilization_pct,
            -- Estimated monthly cost (extrapolate from sample period)
            commitment_cost * (30.0 / days_active) AS estimated_monthly_cost,
            currency,
            first_seen,
            last_seen,
            days_active,
            -- Determine commitment type from SKU description
            CASE
              WHEN LOWER(sku_description) LIKE '%cpu%' THEN 'CPU'
              WHEN LOWER(sku_description) LIKE '%memory%' OR LOWER(sku_description) LIKE '%ram%' THEN 'Memory'
              WHEN LOWER(sku_description) LIKE '%commitment%' THEN 'General Commitment'
              ELSE 'Unknown'
            END AS commitment_type,
            -- Extract term if possible (1 year or 3 years)
            CASE
              WHEN LOWER(sku_description) LIKE '%1%year%' OR LOWER(sku_description) LIKE '%12%month%' THEN '1-Year'
              WHEN LOWER(sku_description) LIKE '%3%year%' OR LOWER(sku_description) LIKE '%36%month%' THEN '3-Year'
              ELSE 'Unknown'
            END AS commitment_term
          FROM commitment_data
        )
        SELECT
          project_id,
          project_name,
          region,
          sku_description,
          commitment_type,
          commitment_term,
          ROUND(commitment_cost, 2) AS commitment_cost,
          ROUND(cud_credits_used, 2) AS cud_credits_used,
          ROUND(utilization_pct, 2) AS utilization_percentage,
          ROUND(estimated_monthly_cost, 2) AS estimated_monthly_cost,
          currency,
          first_seen,
          last_seen,
          days_active
        FROM commitment_summary
        ORDER BY estimated_monthly_cost DESC, project_id, region
        """

        logger.debug("执行 BigQuery 查询...")
        query_job = bq_client.query(query)
        results = query_job.result()

        # Process results
        commitments = []
        total_monthly_cost = 0.0
        total_utilization_sum = 0.0
        commitment_count = 0
        project_set = set()
        region_set = set()
        currency = "USD"

        for row in results:
            commitment = {
                "project_id": row.project_id,
                "project_name": row.project_name or row.project_id,
                "region": row.region or "global",
                "sku_description": row.sku_description,
                "commitment_type": row.commitment_type,
                "commitment_term": row.commitment_term,
                "commitment_cost": float(row.commitment_cost or 0),
                "cud_credits_used": float(row.cud_credits_used or 0),
                "utilization_percentage": float(row.utilization_percentage or 0),
                "estimated_monthly_cost": float(row.estimated_monthly_cost or 0),
                "currency": row.currency,
                "first_seen": str(row.first_seen),
                "last_seen": str(row.last_seen),
                "days_active": int(row.days_active),
                "status": (
                    "ACTIVE" if row.days_active >= days_lookback - 5 else "POTENTIALLY_EXPIRED"
                ),
            }

            commitments.append(commitment)
            total_monthly_cost += commitment["estimated_monthly_cost"]
            total_utilization_sum += commitment["utilization_percentage"]
            commitment_count += 1
            project_set.add(row.project_id)
            region_set.add(row.region or "global")
            currency = row.currency

        # Calculate average utilization
        avg_utilization = (total_utilization_sum / commitment_count) if commitment_count > 0 else 0

        # Build summary
        summary = {
            "total_count": len(commitments),
            "total_estimated_monthly_cost": round(total_monthly_cost, 2),
            "average_utilization_percentage": round(avg_utilization, 2),
            "unique_projects": len(project_set),
            "unique_regions": len(region_set),
            "currency": currency,
            "analysis_period": f"{start_date_str} to {end_date_str}",
            "data_source": "BigQuery Billing Export",
            "note": f"分析了过去 {days_lookback} 天的账单数据（排除最近2天）",
        }

        logger.info(
            f"✅ {operation} 完成 - "
            f"找到 {len(commitments)} 个承诺, "
            f"总月度成本: ${total_monthly_cost:.2f}, "
            f"平均利用率: {avg_utilization:.1f}%"
        )

        return {
            "success": True,
            "data": {"commitments": commitments, "summary": summary},
            "message": f"从 BigQuery 提取了 {len(commitments)} 个 CUD 承诺",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        return {"success": False, "error_message": error_msg, "data": None}
