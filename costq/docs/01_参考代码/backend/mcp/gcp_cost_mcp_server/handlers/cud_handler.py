"""
CUD (Committed Use Discounts) Handler for GCP Cost MCP Server

This module provides handler functions for GCP Committed Use Discount operations
including utilization, coverage, and savings analysis.

Implements functionality similar to AWS RISP MCP Server's RI/SP analysis.
"""

import logging
import sys
from datetime import datetime, timedelta

# Add project root to path
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.mcp.gcp_cost_mcp_server.constants import (
    DEFAULT_LOOKBACK_DAYS,
)
from backend.mcp.gcp_cost_mcp_server.models.cud_models import (
    CudCoverageParams,
    CudSavingsAnalysisParams,
    CudUtilizationParams,
    ListCommitmentsParams,
)
from backend.mcp.gcp_cost_mcp_server.utils.bigquery_helper import (
    validate_date_range,
)
from backend.mcp.gcp_cost_mcp_server.utils.multi_account_client import (
    get_bigquery_client_for_account,
)

# Note: get_compute_client_for_account removed - no Compute API permissions
from backend.services.gcp_credentials_provider import get_gcp_credentials_provider


async def list_commitments(ctx: Context, params: ListCommitmentsParams) -> dict[str, Any]:
    """List all CUD commitments

    Retrieves commitment inventory using Compute Engine API. Shows active, expired,
    and pending commitments with their resource allocations and costs.

    Supports both project-level and organization-level queries.

    Args:
        ctx: MCP context
        params: List commitments parameters

    Returns:
        Dictionary with success, commitments list, and summary

    Note:
        Provide either project_id OR billing_account_id, not both.
        If neither is provided, will use the default from account configuration.

    Example:
        >>> # Single project
        >>> result = await list_commitments(ctx, project_id='my-project')

        >>> # Entire organization
        >>> result = await list_commitments(ctx, billing_account_id='012345-ABCDEF-123456')
    """
    operation = "list_commitments"

    # Smart default: use billing_account_id if available, otherwise project_id
    project_id = params.project_id
    billing_account_id = params.billing_account_id
    account_id = params.account_id

    if not project_id and not billing_account_id:
        credentials_provider = get_gcp_credentials_provider()
        account_info = credentials_provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")
        elif account_info:
            project_id = account_info["project_id"]
            logger.info(f"🎯 使用账号配置的 project_id: {project_id}")

    region = params.region

    if billing_account_id:
        logger.info(
            f"🔍 {operation} - Billing Account: {billing_account_id}, Region: {region or 'all'}"
        )
    else:
        logger.info(f"🔍 {operation} - Project: {project_id}, Region: {region or 'all'}")

    try:
        # ✅ PERFECT SOLUTION: Use the perfect BigQuery implementation
        #
        # Key improvements over v2:
        # 1. Correctly calculates commitment on-demand equivalent value
        # 2. Uses discount rate (28% for 1-year, 46% for 3-year)
        # 3. Compares usage_cost_on_demand vs commitment_on_demand_value
        # 4. Ensures utilization rate is reasonable (0-120%)
        #
        # This matches industry best practices and competitor solutions
        logger.info("🚀 使用 BigQuery 完美查询方案 (v3)")
        from backend.mcp.gcp_cost_mcp_server.handlers.cud_handler_bigquery_v5_coverage_fixed import (
            list_commitments_with_coverage_fixed,
        )

        return await list_commitments_with_coverage_fixed(
            account_id=account_id,
            project_id=project_id,
            billing_account_id=billing_account_id,
            region=region,
        )

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")

        return {"success": False, "error_message": error_msg, "data": None}


async def get_cud_utilization(ctx: Context, params: CudUtilizationParams) -> dict[str, Any]:
    """Get CUD utilization analysis (similar to AWS RI Utilization)

    Analyzes how much of your purchased CUD commitments are being utilized.
    Calculates utilization percentage, unused commitment hours, and potential savings.

    Supports both project-level and organization-level queries.

    Args:
        ctx: MCP context
        params: CUD utilization parameters

    Returns:
        Dictionary with utilization summary and time-series data

    Note:
        Provide either project_id OR billing_account_id, not both.

    Example:
        >>> # Single project
        >>> result = await get_cud_utilization(ctx, project_id='my-project')

        >>> # Entire organization
        >>> result = await get_cud_utilization(ctx, billing_account_id='012345-ABCDEF-123456')
    """
    operation = "get_cud_utilization"

    # Smart default
    project_id = params.project_id
    billing_account_id = params.billing_account_id
    account_id = params.account_id

    if not project_id and not billing_account_id:
        credentials_provider = get_gcp_credentials_provider()
        account_info = credentials_provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")
        elif account_info:
            project_id = account_info["project_id"]
            logger.info(f"🎯 使用账号配置的 project_id: {project_id}")

    start_date = params.start_date
    end_date = params.end_date

    if billing_account_id:
        logger.info(
            f"🔍 {operation} - Billing Account: {billing_account_id}, Period: {start_date} to {end_date}"
        )
    else:
        logger.info(f"🔍 {operation} - Project: {project_id}, Period: {start_date} to {end_date}")

    try:
        # Get date range (exclude last 2 days to avoid incomplete data)
        if not start_date or not end_date:
            end_datetime = datetime.now() - timedelta(days=2)  # 2-day buffer for data lag
            start_datetime = end_datetime - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            start_date = start_datetime.strftime("%Y-%m-%d")
            end_date = end_datetime.strftime("%Y-%m-%d")
            logger.info(
                f"Using adjusted date range: {start_date} to {end_date} (excludes last 2 days)"
            )

        if not validate_date_range(start_date, end_date):
            return {
                "success": False,
                "error_message": f"Invalid date range: {start_date} to {end_date}",
                "data": None,
            }

        # Get BigQuery table name
        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        # Get BigQuery client
        bq_client = get_bigquery_client_for_account(account_id)

        # Build scope filter (project or billing account)
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
        else:
            scope_filter = f"AND project.id = '{project_id}'"

        # Build CUD utilization query
        region = params.region
        granularity = params.granularity
        region_filter = f"AND location.region = '{region}'" if region else ""
        date_grouping = (
            "DATE(_PARTITIONDATE)"
            if granularity == "DAILY"
            else "FORMAT_DATE('%Y-%m', DATE(_PARTITIONDATE))"
        )

        query = f"""
        WITH commitment_costs AS (
          SELECT
            {date_grouping} AS period,
            location.region AS region,
            -- Commitment fees (what you pay for the CUD)
            SUM(CASE
              WHEN sku.description LIKE 'Commitment v1:%' THEN cost
              ELSE 0
            END) AS commitment_cost,
            -- CUD credits applied (negative, represents usage covered by CUD)
            ABS(SUM(
              (SELECT SUM(c.amount)
               FROM UNNEST(credits) AS c
               WHERE c.type = 'COMMITTED_USAGE_DISCOUNT')
            )) AS cud_credits_applied,
            currency
          FROM `{table_name}`
          WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            AND service.description = 'Compute Engine'
            {scope_filter}
            {region_filter}
          GROUP BY period, region, currency
        )
        SELECT
          period,
          region,
          commitment_cost,
          cud_credits_applied,
          -- Utilization = credits applied / commitment cost
          SAFE_DIVIDE(cud_credits_applied, commitment_cost) * 100 AS utilization_percentage,
          -- Unused commitment
          commitment_cost - cud_credits_applied AS unused_commitment,
          currency
        FROM commitment_costs
        WHERE commitment_cost > 0
        ORDER BY period, region
        """

        logger.debug("Executing CUD utilization query")
        query_job = bq_client.query(query)
        results = query_job.result()

        # Process results
        utilizations_by_time = []
        total_commitment_cost = 0.0
        total_cud_credits = 0.0
        currency = "USD"

        for row in results:
            item = {
                "period": str(row.period),
                "region": row.region or "global",
                "commitment_cost": float(row.commitment_cost or 0),
                "cud_credits_applied": float(row.cud_credits_applied or 0),
                "utilization_percentage": float(row.utilization_percentage or 0),
                "unused_commitment": float(row.unused_commitment or 0),
                "currency": row.currency,
            }
            utilizations_by_time.append(item)
            total_commitment_cost += item["commitment_cost"]
            total_cud_credits += item["cud_credits_applied"]
            currency = row.currency

        # Calculate overall utilization
        overall_utilization = (
            (total_cud_credits / total_commitment_cost * 100) if total_commitment_cost > 0 else 0
        )

        # Build summary
        utilization_summary = {
            "total_commitment_cost": round(total_commitment_cost, 2),
            "total_cud_credits_applied": round(total_cud_credits, 2),
            "total_unused_commitment": round(total_commitment_cost - total_cud_credits, 2),
            "utilization_percentage": round(overall_utilization, 2),
            "currency": currency,
            "period_count": len(utilizations_by_time),
            "data_freshness_note": "Data may lag by up to 1.5 days due to CUD credit attribution delay",
        }

        logger.info(
            f"✅ {operation} completed - "
            f"Utilization: {overall_utilization:.1f}%, "
            f"Periods: {len(utilizations_by_time)}"
        )

        return {
            "success": True,
            "data": {
                "utilization_summary": utilization_summary,
                "utilizations_by_time": utilizations_by_time,
                "request_parameters": {
                    "project_id": project_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "granularity": granularity,
                    "region": region,
                },
            },
            "account_id": account_id,
            "message": f"CUD utilization: {overall_utilization:.1f}% across {len(utilizations_by_time)} periods",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")

        return {"success": False, "error_message": error_msg, "data": None}


async def get_cud_coverage(ctx: Context, params: CudCoverageParams) -> dict[str, Any]:
    """Get CUD coverage analysis (similar to AWS RI Coverage)

    Analyzes what percentage of your eligible usage is covered by CUD commitments
    vs running at on-demand rates.

    Supports both project-level and organization-level queries.

    Args:
        ctx: MCP context
        params: CUD coverage parameters

    Returns:
        Dictionary with coverage summary and time-series data

    Example:
        >>> result = await get_cud_coverage(ctx, project_id='my-project')
        >>> result = await get_cud_coverage(ctx, billing_account_id='012345-ABCDEF-123456')
    """
    operation = "get_cud_coverage"

    # Smart default
    project_id = params.project_id
    billing_account_id = params.billing_account_id
    account_id = params.account_id
    service_filter = params.service_filter

    if not project_id and not billing_account_id:
        credentials_provider = get_gcp_credentials_provider()
        account_info = credentials_provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")
        elif account_info:
            project_id = account_info["project_id"]
            logger.info(f"🎯 使用账号配置的 project_id: {project_id}")

    if billing_account_id:
        logger.info(
            f"🔍 {operation} - Billing Account: {billing_account_id}, Service: {service_filter}"
        )
    else:
        logger.info(f"🔍 {operation} - Project: {project_id}, Service: {service_filter}")

    try:
        # Get date range (exclude last 2 days)
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            end_datetime = datetime.now() - timedelta(days=2)
            start_datetime = end_datetime - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            start_date = start_datetime.strftime("%Y-%m-%d")
            end_date = end_datetime.strftime("%Y-%m-%d")

        if not validate_date_range(start_date, end_date):
            return {
                "success": False,
                "error_message": f"Invalid date range: {start_date} to {end_date}",
                "data": None,
            }

        # Get BigQuery table name
        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        # Get BigQuery client
        bq_client = get_bigquery_client_for_account(account_id)

        # Build scope filter
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
        else:
            scope_filter = f"AND project.id = '{project_id}'"

        # Build CUD coverage query
        region = params.region
        granularity = params.granularity
        region_filter = f"AND location.region = '{region}'" if region else ""
        date_grouping = (
            "DATE(_PARTITIONDATE)"
            if granularity == "DAILY"
            else "FORMAT_DATE('%Y-%m', DATE(_PARTITIONDATE))"
        )

        query = f"""
        SELECT
          {date_grouping} AS period,
          location.region AS region,

          -- Total eligible cost (CUD-eligible resources, excluding preemptible)
          SUM(cost) AS total_eligible_cost,

          -- CUD-covered cost (resources with CUD credits applied)
          SUM(CASE
            WHEN EXISTS(
              SELECT 1 FROM UNNEST(credits) AS c
              WHERE c.type = 'COMMITTED_USAGE_DISCOUNT'
            ) THEN cost
            ELSE 0
          END) AS cud_covered_cost,

          -- On-demand cost (resources NOT covered by CUD)
          SUM(CASE
            WHEN NOT EXISTS(
              SELECT 1 FROM UNNEST(credits) AS c
              WHERE c.type = 'COMMITTED_USAGE_DISCOUNT'
            ) THEN cost
            ELSE 0
          END) AS on_demand_cost,

          -- Coverage percentage
          SAFE_DIVIDE(
            SUM(CASE WHEN EXISTS(SELECT 1 FROM UNNEST(credits) AS c WHERE c.type = 'COMMITTED_USAGE_DISCOUNT') THEN cost ELSE 0 END),
            SUM(cost)
          ) * 100 AS coverage_percentage,

          currency
        FROM `{table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
          AND service.description = '{service_filter}'
          AND sku.description NOT LIKE '%Preemptible%'  -- Exclude preemptible VMs (not CUD-eligible)
          {scope_filter}
          {region_filter}
        GROUP BY period, region, currency
        HAVING total_eligible_cost > 0
        ORDER BY period, region
        """

        logger.debug("Executing CUD coverage query")
        query_job = bq_client.query(query)
        results = query_job.result()

        # Process results
        coverages_by_time = []
        total_eligible_cost = 0.0
        total_cud_covered = 0.0
        total_on_demand = 0.0
        currency = "USD"

        for row in results:
            item = {
                "period": str(row.period),
                "region": row.region or "global",
                "total_eligible_cost": float(row.total_eligible_cost or 0),
                "cud_covered_cost": float(row.cud_covered_cost or 0),
                "on_demand_cost": float(row.on_demand_cost or 0),
                "coverage_percentage": float(row.coverage_percentage or 0),
                "currency": row.currency,
            }
            coverages_by_time.append(item)
            total_eligible_cost += item["total_eligible_cost"]
            total_cud_covered += item["cud_covered_cost"]
            total_on_demand += item["on_demand_cost"]
            currency = row.currency

        # Calculate overall coverage
        overall_coverage = (
            (total_cud_covered / total_eligible_cost * 100) if total_eligible_cost > 0 else 0
        )

        # Build summary
        coverage_summary = {
            "total_eligible_cost": round(total_eligible_cost, 2),
            "cud_covered_cost": round(total_cud_covered, 2),
            "on_demand_cost": round(total_on_demand, 2),
            "coverage_percentage": round(overall_coverage, 2),
            "uncovered_percentage": round(100 - overall_coverage, 2),
            "currency": currency,
            "period_count": len(coverages_by_time),
            "service": service_filter,
        }

        logger.info(
            f"✅ {operation} completed - "
            f"Coverage: {overall_coverage:.1f}%, "
            f"On-demand: ${total_on_demand:.2f}"
        )

        return {
            "success": True,
            "data": {
                "coverage_summary": coverage_summary,
                "coverages_by_time": coverages_by_time,
                "request_parameters": {
                    "project_id": project_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "granularity": granularity,
                    "service": service_filter,
                    "region": region,
                },
            },
            "account_id": account_id,
            "message": f"CUD coverage: {overall_coverage:.1f}% of eligible usage",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")

        return {"success": False, "error_message": error_msg, "data": None}


async def get_cud_savings_analysis(
    ctx: Context, params: CudSavingsAnalysisParams
) -> dict[str, Any]:
    """Analyze cost savings from CUD commitments

    Calculates actual savings achieved by using CUDs vs on-demand pricing.
    Shows ROI of commitment purchases.

    Supports both project-level and organization-level queries.

    Args:
        ctx: MCP context
        params: CUD savings analysis parameters

    Returns:
        Dictionary with savings summary and breakdown
    """
    operation = "get_cud_savings_analysis"

    # Smart default
    project_id = params.project_id
    billing_account_id = params.billing_account_id
    account_id = params.account_id

    if not project_id and not billing_account_id:
        credentials_provider = get_gcp_credentials_provider()
        account_info = credentials_provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")
        elif account_info:
            project_id = account_info["project_id"]
            logger.info(f"🎯 使用账号配置的 project_id: {project_id}")

    if billing_account_id:
        logger.info(f"🔍 {operation} - Billing Account: {billing_account_id}")
    else:
        logger.info(f"🔍 {operation} - Project: {project_id}")

    try:
        # Get date range
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            end_datetime = datetime.now() - timedelta(days=2)
            start_datetime = end_datetime - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            start_date = start_datetime.strftime("%Y-%m-%d")
            end_date = end_datetime.strftime("%Y-%m-%d")

        if not validate_date_range(start_date, end_date):
            return {
                "success": False,
                "error_message": f"Invalid date range: {start_date} to {end_date}",
                "data": None,
            }

        # Get BigQuery table name
        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        # Get BigQuery client
        bq_client = get_bigquery_client_for_account(account_id)

        # Build scope filter
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
        else:
            scope_filter = f"AND project.id = '{project_id}'"

        # Build savings analysis query
        granularity = params.granularity
        date_grouping = (
            "DATE(_PARTITIONDATE)"
            if granularity == "DAILY"
            else "FORMAT_DATE('%Y-%m', DATE(_PARTITIONDATE))"
        )

        query = f"""
        SELECT
          {date_grouping} AS period,

          -- Commitment cost (what you paid)
          SUM(CASE
            WHEN cost_type = 'commitment' THEN cost
            ELSE 0
          END) AS commitment_cost,

          -- CUD credits (discount value received)
          ABS(SUM(
            (SELECT SUM(c.amount)
             FROM UNNEST(credits) AS c
             WHERE c.type = 'COMMITTED_USAGE_DISCOUNT')
          )) AS cud_credits_received,

          -- Net savings (credits - commitment cost)
          ABS(SUM(
            (SELECT SUM(c.amount)
             FROM UNNEST(credits) AS c
             WHERE c.type = 'COMMITTED_USAGE_DISCOUNT')
          )) - SUM(CASE WHEN cost_type = 'commitment' THEN cost ELSE 0 END) AS net_savings,

          -- On-demand equivalent cost
          SUM(cost) + ABS(SUM(
            (SELECT SUM(c.amount)
             FROM UNNEST(credits) AS c
             WHERE c.type = 'COMMITTED_USAGE_DISCOUNT')
          )) AS on_demand_equivalent_cost,

          currency
        FROM `{table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
          AND service.description = 'Compute Engine'
          {scope_filter}
        GROUP BY period, currency
        ORDER BY period
        """

        logger.debug("Executing CUD savings query")
        query_job = bq_client.query(query)
        results = query_job.result()

        # Process results
        savings_by_period = []
        total_commitment = 0.0
        total_credits = 0.0
        total_savings = 0.0
        currency = "USD"

        for row in results:
            commitment = float(row.commitment_cost or 0)
            credits = float(row.cud_credits_received or 0)
            savings = float(row.net_savings or 0)
            on_demand_equiv = float(row.on_demand_equivalent_cost or 0)

            savings_pct = (savings / on_demand_equiv * 100) if on_demand_equiv > 0 else 0

            item = {
                "period": str(row.period),
                "commitment_cost": round(commitment, 2),
                "cud_credits_received": round(credits, 2),
                "net_savings": round(savings, 2),
                "on_demand_equivalent_cost": round(on_demand_equiv, 2),
                "savings_percentage": round(savings_pct, 2),
                "currency": row.currency,
            }
            savings_by_period.append(item)
            total_commitment += commitment
            total_credits += credits
            total_savings += savings
            currency = row.currency

        # Calculate overall savings percentage
        total_on_demand_equiv = total_commitment + total_credits
        overall_savings_pct = (
            (total_savings / total_on_demand_equiv * 100) if total_on_demand_equiv > 0 else 0
        )
        roi_pct = (total_savings / total_commitment * 100) if total_commitment > 0 else 0

        # Build summary
        savings_summary = {
            "total_commitment_cost": round(total_commitment, 2),
            "total_cud_credits": round(total_credits, 2),
            "net_savings": round(total_savings, 2),
            "on_demand_equivalent_cost": round(total_on_demand_equiv, 2),
            "savings_percentage": round(overall_savings_pct, 2),
            "roi_percentage": round(roi_pct, 2),
            "currency": currency,
            "period_count": len(savings_by_period),
        }

        logger.info(
            f"✅ {operation} completed - "
            f"Net savings: ${total_savings:.2f} ({overall_savings_pct:.1f}%)"
        )

        return {
            "success": True,
            "data": {
                "savings_summary": savings_summary,
                "savings_by_period": savings_by_period,
                "request_parameters": {
                    "project_id": project_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "granularity": granularity,
                },
            },
            "account_id": account_id,
            "message": f"CUD savings: ${total_savings:.2f} ({overall_savings_pct:.1f}%)",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")

        return {"success": False, "error_message": error_msg, "data": None}
