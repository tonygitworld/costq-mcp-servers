"""
Billing Handler - BigQuery Cost Queries

Implements cost analysis tools using BigQuery billing export data.
"""

import logging

from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context


from constants import (
    BILLING_EXPORT_SETUP_INSTRUCTIONS,
    DEFAULT_LOOKBACK_DAYS,
)
from models import (
    CostByLabelParams,
    CostByProjectParams,
    CostByServiceParams,
    CostBySkuParams,
    CostSummaryParams,
    DailyCostTrendParams,
)
from utils.bigquery_helper import (
    BigQueryHelper,
    sanitize_string_for_sql,
    validate_date_range,
)
from utils.multi_account_client import (
    get_bigquery_client_for_account,
)
from services.gcp_credentials_provider import get_gcp_credentials_provider


async def get_cost_by_service(ctx: Context, params: CostByServiceParams) -> dict[str, Any]:
    """Get GCP costs grouped by service

    Query BigQuery billing export to get cost breakdown by service.

    Supports both project-level and organization-level queries.

    Args:
        ctx: MCP context
        params: Cost by service parameters

    Returns:
        Dictionary with success, items (cost by service), and summary

    Note:
        - Use project_ids to query specific projects
        - Use billing_account_id to query entire organization
        - If neither is provided, uses account's default (billing_account_id if available)

    Example:
        >>> result = await get_cost_by_service(ctx, start_date='2024-01-01', end_date='2024-01-31')
        >>> print(result['data']['items'][0])
        {'service_name': 'Compute Engine', 'total_cost': 1234.56, 'net_cost': 1100.00}
    """
    operation = "get_cost_by_service"

    # Smart default: use billing_account_id if available
    project_ids = params.project_ids
    billing_account_id = params.billing_account_id
    account_id = params.account_id

    if not project_ids and not billing_account_id:
        provider = get_gcp_credentials_provider()
        account_info = provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")
        # 如果没有 billing_account_id，project_ids 保持 None（查询所有项目）

    # logger.info(
    #     f"🔍 {operation} - Account: {account_id or 'default'}, "
    #     f"Date range: {start_date} to {end_date}"
    # )  # 已静默

    try:
        # Get date range
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            start_date, end_date = BigQueryHelper.get_default_date_range(DEFAULT_LOOKBACK_DAYS)
            # logger.info(f"Using default date range: {start_date} to {end_date}")  # 已静默

        # Validate dates
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
            error_msg = "BigQuery billing export not configured"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error_message": error_msg,
                "help_url": "https://cloud.google.com/billing/docs/how-to/export-data-bigquery",
                "setup_guide": BILLING_EXPORT_SETUP_INSTRUCTIONS,
                "data": None,
            }

        # Get BigQuery client
        bq_client = get_bigquery_client_for_account(account_id)

        # Build and execute query
        helper = BigQueryHelper(table_name)
        query = helper.build_cost_by_service_query(
            start_date, end_date, project_ids, billing_account_id, params.limit
        )

        # logger.debug(f"Executing query:\n{query}")  # 已静默 - 太长的 SQL 查询
        query_job = bq_client.query(query)
        results = query_job.result()

        # Process results
        items = []
        total_cost = 0.0
        total_credits = 0.0
        total_net_cost = 0.0
        currency = "USD"

        for row in results:
            item = {
                "service_name": row.service_name,
                "total_cost": float(row.total_cost or 0),
                "total_credits": float(row.total_credits or 0),
                "net_cost": float(row.net_cost or 0),
                "currency": row.currency,
                "project_count": row.project_count,
            }
            items.append(item)
            total_cost += item["total_cost"]
            total_credits += item["total_credits"]
            total_net_cost += item["net_cost"]
            currency = row.currency

        # Calculate summary
        summary = {
            "total_cost": round(total_cost, 2),
            "total_credits": round(total_credits, 2),
            "net_cost": round(total_net_cost, 2),
            "currency": currency,
            "services_count": len(items),
            "start_date": start_date,
            "end_date": end_date,
        }

        # logger.info(f"✅ {operation} completed - {len(items)} services, total: {currency} {total_net_cost:.2f}")  # 已静默

        return {
            "success": True,
            "data": {"items": items, "summary": summary},
            "account_id": account_id,
            "message": f"Retrieved cost data for {len(items)} services",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        return {"success": False, "error_message": error_msg, "data": None}


async def get_cost_by_project(ctx: Context, params: CostByProjectParams) -> dict[str, Any]:
    """Get GCP costs grouped by project

    Groups costs by project, optionally filtered by billing account.

    Args:
        ctx: MCP context
        params: Cost by project parameters

    Returns:
        Dictionary with success, items (cost by project), and summary

    Note:
        - If billing_account_id is provided, only shows projects under that billing account
        - Otherwise shows all projects in the billing export table
    """
    operation = "get_cost_by_project"

    # Smart default
    billing_account_id = params.billing_account_id
    account_id = params.account_id
    service_filter = params.service_filter

    if not billing_account_id:
        provider = get_gcp_credentials_provider()
        account_info = provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")

    # logger.info(f"🔍 {operation} - Account: {account_id or 'default'}, Service: {service_filter}")  # 已静默

    try:
        # Get date range
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            start_date, end_date = BigQueryHelper.get_default_date_range(DEFAULT_LOOKBACK_DAYS)

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
                "setup_guide": BILLING_EXPORT_SETUP_INSTRUCTIONS,
                "data": None,
            }

        # Sanitize service filter
        if service_filter:
            service_filter = sanitize_string_for_sql(service_filter)

        # Get BigQuery client and execute query
        bq_client = get_bigquery_client_for_account(account_id)
        helper = BigQueryHelper(table_name)
        query = helper.build_cost_by_project_query(
            start_date, end_date, service_filter, billing_account_id, params.limit
        )

        results = bq_client.query(query).result()

        # Process results
        items = []
        total_cost = 0.0
        total_credits = 0.0
        total_net_cost = 0.0
        currency = "USD"

        for row in results:
            item = {
                "project_id": row.project_id,
                "project_name": row.project_name or row.project_id,
                "total_cost": float(row.total_cost or 0),
                "total_credits": float(row.total_credits or 0),
                "net_cost": float(row.net_cost or 0),
                "currency": row.currency,
                "service_count": row.service_count,
            }
            items.append(item)
            total_cost += item["total_cost"]
            total_credits += item["total_credits"]
            total_net_cost += item["net_cost"]
            currency = row.currency

        summary = {
            "total_cost": round(total_cost, 2),
            "total_credits": round(total_credits, 2),
            "net_cost": round(total_net_cost, 2),
            "currency": currency,
            "projects_count": len(items),
            "start_date": start_date,
            "end_date": end_date,
            "service_filter": service_filter,
        }

        # logger.info(f"✅ {operation} completed - {len(items)} projects")  # 已静默

        return {
            "success": True,
            "data": {"items": items, "summary": summary},
            "account_id": account_id,
            "message": f"Retrieved cost data for {len(items)} projects",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def get_daily_cost_trend(ctx: Context, params: DailyCostTrendParams) -> dict[str, Any]:
    """Get daily cost trend

    Args:
        ctx: MCP context
        params: Daily cost trend parameters

    Returns:
        Dictionary with success, items (daily cost data points), and summary
    """
    operation = "get_daily_cost_trend"
    account_id = params.account_id
    # logger.info(f"🔍 {operation} - Account: {account_id or 'default'}")  # 已静默

    try:
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            start_date, end_date = BigQueryHelper.get_default_date_range(DEFAULT_LOOKBACK_DAYS)

        if not validate_date_range(start_date, end_date):
            return {"success": False, "error_message": "Invalid date range", "data": None}

        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "setup_guide": BILLING_EXPORT_SETUP_INSTRUCTIONS,
                "data": None,
            }

        service_filter = params.service_filter
        if service_filter:
            service_filter = sanitize_string_for_sql(service_filter)

        bq_client = get_bigquery_client_for_account(account_id)
        helper = BigQueryHelper(table_name)
        query = helper.build_daily_cost_trend_query(
            start_date, end_date, params.project_ids, service_filter
        )

        results = bq_client.query(query).result()

        # Process results
        items = []
        total_cost = 0.0
        total_net_cost = 0.0
        currency = "USD"

        for row in results:
            item = {
                "date": str(row.date),
                "daily_cost": float(row.daily_cost or 0),
                "daily_credits": float(row.daily_credits or 0),
                "daily_net_cost": float(row.daily_net_cost or 0),
                "currency": row.currency,
                "services_used": row.services_used,
                "projects_count": row.projects_count,
            }
            items.append(item)
            total_cost += item["daily_cost"]
            total_net_cost += item["daily_net_cost"]
            currency = row.currency

        # Calculate average
        days_count = len(items)
        avg_daily_cost = total_net_cost / days_count if days_count > 0 else 0

        summary = {
            "total_cost": round(total_cost, 2),
            "total_net_cost": round(total_net_cost, 2),
            "average_daily_cost": round(avg_daily_cost, 2),
            "currency": currency,
            "days_count": days_count,
            "start_date": start_date,
            "end_date": end_date,
        }

        # logger.info(f"✅ {operation} completed - {days_count} days")  # 已静默

        return {
            "success": True,
            "data": {"items": items, "summary": summary},
            "account_id": account_id,
            "message": f"Retrieved {days_count} days of cost data",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def get_cost_by_label(ctx: Context, params: CostByLabelParams) -> dict[str, Any]:
    """Get costs grouped by label (cost allocation/chargeback)

    Supports both project-level and organization-level queries.

    Args:
        ctx: MCP context
        params: Cost by label parameters

    Returns:
        Dictionary with success, items (cost by label value), and summary
    """
    operation = "get_cost_by_label"

    # Smart default
    project_ids = params.project_ids
    billing_account_id = params.billing_account_id
    account_id = params.account_id
    label_key = params.label_key

    if not project_ids and not billing_account_id:
        provider = get_gcp_credentials_provider()
        account_info = provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")

    logger.info(f"🔍 {operation} - Label: {label_key}, Account: {account_id or 'default'}")

    try:
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            start_date, end_date = BigQueryHelper.get_default_date_range(DEFAULT_LOOKBACK_DAYS)

        if not validate_date_range(start_date, end_date):
            return {"success": False, "error_message": "Invalid date range", "data": None}

        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        # Sanitize label key
        label_key = sanitize_string_for_sql(label_key)

        bq_client = get_bigquery_client_for_account(account_id)
        helper = BigQueryHelper(table_name)
        query = helper.build_cost_by_label_query(
            start_date, end_date, label_key, project_ids, billing_account_id, params.limit
        )

        results = bq_client.query(query).result()

        items = []
        total_cost = 0.0
        total_net_cost = 0.0
        currency = "USD"

        for row in results:
            item = {
                "label_value": row.label_value,
                "total_cost": float(row.total_cost or 0),
                "total_credits": float(row.total_credits or 0),
                "net_cost": float(row.net_cost or 0),
                "currency": row.currency,
                "project_count": row.project_count,
                "service_count": row.service_count,
            }
            items.append(item)
            total_cost += item["total_cost"]
            total_net_cost += item["net_cost"]
            currency = row.currency

        summary = {
            "total_cost": round(total_cost, 2),
            "total_net_cost": round(total_net_cost, 2),
            "currency": currency,
            "label_values_count": len(items),
            "label_key": label_key,
            "start_date": start_date,
            "end_date": end_date,
        }

        # logger.info(f"✅ {operation} completed - {len(items)} label values for '{label_key}'")  # 已静默

        return {
            "success": True,
            "data": {"items": items, "summary": summary, "label_key": label_key},
            "account_id": account_id,
            "message": f"Retrieved cost data for {len(items)} {label_key} values",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def get_cost_by_sku(ctx: Context, params: CostBySkuParams) -> dict[str, Any]:
    """Get costs grouped by SKU (detailed breakdown)

    Supports both project-level and organization-level queries.

    Args:
        ctx: MCP context
        params: Cost by SKU parameters

    Returns:
        Dictionary with success, items (cost by SKU), and metadata
    """
    operation = "get_cost_by_sku"

    # Smart default
    project_ids = params.project_ids
    billing_account_id = params.billing_account_id
    account_id = params.account_id
    service_filter = params.service_filter

    if not project_ids and not billing_account_id:
        provider = get_gcp_credentials_provider()
        account_info = provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")

    logger.info(f"🔍 {operation} - Service: {service_filter}, Account: {account_id or 'default'}")

    try:
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            start_date, end_date = BigQueryHelper.get_default_date_range(DEFAULT_LOOKBACK_DAYS)

        if not validate_date_range(start_date, end_date):
            return {"success": False, "error_message": "Invalid date range", "data": None}

        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        if service_filter:
            service_filter = sanitize_string_for_sql(service_filter)

        bq_client = get_bigquery_client_for_account(account_id)
        helper = BigQueryHelper(table_name)
        query = helper.build_cost_by_sku_query(
            start_date, end_date, service_filter, project_ids, billing_account_id, params.limit
        )

        results = bq_client.query(query).result()

        items = []
        total_cost = 0.0

        for row in results:
            item = {
                "service_name": row.service_name,
                "sku_description": row.sku_description,
                "total_cost": float(row.total_cost or 0),
                "total_usage_amount": float(row.total_usage_amount or 0),
                "usage_unit": row.usage_unit or "",
                "currency": row.currency,
                "project_count": row.project_count,
            }
            items.append(item)
            total_cost += item["total_cost"]

        # logger.info(f"✅ {operation} completed - {len(items)} SKUs")  # 已静默

        return {
            "success": True,
            "data": {
                "items": items,
                "total_cost": round(total_cost, 2),
                "sku_count": len(items),
                "service_filter": service_filter,
            },
            "account_id": account_id,
            "message": f"Retrieved {len(items)} SKUs",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def get_cost_summary(ctx: Context, params: CostSummaryParams) -> dict[str, Any]:
    """Get overall cost summary

    Supports both project-level and organization-level summaries.

    Args:
        ctx: MCP context
        params: Cost summary parameters

    Returns:
        Dictionary with success and summary statistics
    """
    operation = "get_cost_summary"

    # Smart default
    project_ids = params.project_ids
    billing_account_id = params.billing_account_id
    account_id = params.account_id

    if not project_ids and not billing_account_id:
        provider = get_gcp_credentials_provider()
        account_info = provider.get_account_info(account_id or "default")
        if account_info and account_info.get("billing_account_id"):
            billing_account_id = account_info["billing_account_id"]
            logger.info(f"🎯 使用账号配置的 billing_account_id: {billing_account_id}")

    # logger.info(f"🔍 {operation} - Account: {account_id or 'default'}")  # 已静默

    try:
        start_date = params.start_date
        end_date = params.end_date
        if not start_date or not end_date:
            start_date, end_date = BigQueryHelper.get_default_date_range(DEFAULT_LOOKBACK_DAYS)

        if not validate_date_range(start_date, end_date):
            return {"success": False, "error_message": "Invalid date range", "data": None}

        provider = get_gcp_credentials_provider()
        table_name = provider.get_bigquery_table_name(account_id) if account_id else None

        if not table_name:
            return {
                "success": False,
                "error_message": "BigQuery billing export not configured",
                "data": None,
            }

        bq_client = get_bigquery_client_for_account(account_id)
        helper = BigQueryHelper(table_name)
        query = helper.build_cost_summary_query(
            start_date, end_date, project_ids, billing_account_id
        )

        results = bq_client.query(query).result()

        summary = None
        for row in results:
            days_count = row.days_count
            avg_daily = (row.net_cost / days_count) if days_count > 0 else 0

            summary = {
                "total_cost": float(row.total_cost or 0),
                "total_credits": float(row.total_credits or 0),
                "net_cost": float(row.net_cost or 0),
                "currency": row.currency,
                "services_count": row.services_count,
                "projects_count": row.projects_count,
                "days_count": days_count,
                "start_date": str(row.start_date),
                "end_date": str(row.end_date),
                "average_daily_cost": round(avg_daily, 2),
            }
            break

        if not summary:
            summary = {
                "total_cost": 0.0,
                "net_cost": 0.0,
                "currency": "USD",
                "message": "No cost data found for the specified period",
            }

        # logger.info(f"✅ {operation} completed - Total: {summary.get('currency', 'USD')} {summary.get('net_cost', 0):.2f}")  # 已静默

        return {
            "success": True,
            "data": summary,
            "account_id": account_id,
            "message": "Cost summary retrieved successfully",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}
