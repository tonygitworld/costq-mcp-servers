"""
Budget Handler - Budget Management

Implements budget management tools using GCP Cloud Billing Budgets API.
"""

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.mcp.gcp_cost_mcp_server.models.budget_models import CreateBudgetParams
from backend.mcp.gcp_cost_mcp_server.utils.multi_account_client import get_budget_client_for_account
from backend.services.gcp_credentials_provider import get_gcp_credentials_provider


async def list_budgets(
    ctx: Context, billing_account_id: str | None = None, account_id: str | None = None
) -> dict[str, Any]:
    """List all budgets for a billing account

    Args:
        ctx: MCP context
        billing_account_id: GCP billing account ID (e.g., '012345-6789AB-CDEF01')
                           If not provided, will try to get from account metadata
        account_id: Optional GCP account ID

    Returns:
        Dictionary with success, budgets list, and summary
    """
    operation = "list_budgets"
    logger.info(f"🔍 {operation} - Account: {account_id or 'default'}")

    try:
        # Get billing account ID
        if not billing_account_id and account_id:
            provider = get_gcp_credentials_provider()
            account_info = provider.get_account_info(account_id)
            if account_info:
                billing_account_id = account_info.get("billing_account_id")

        if not billing_account_id:
            return {
                "success": False,
                "error_message": "Billing account ID not provided and not found in account metadata",
                "data": None,
            }

        # Get Budget client
        budget_client = get_budget_client_for_account(account_id)

        # List budgets
        parent = f"billingAccounts/{billing_account_id}"
        budgets = []

        for budget in budget_client.list_budgets(parent=parent):
            # Parse budget amount
            amount_info = None
            if budget.amount:
                if budget.amount.specified_amount:
                    amount_info = {
                        "type": "specified",
                        "currency_code": budget.amount.specified_amount.currency_code,
                        "amount": float(budget.amount.specified_amount.units or 0)
                        + float(budget.amount.specified_amount.nanos or 0) / 1e9,
                    }
                elif budget.amount.last_period_amount:
                    amount_info = {"type": "last_period"}

            # Parse threshold rules
            thresholds = []
            if budget.threshold_rules:
                for rule in budget.threshold_rules:
                    thresholds.append(
                        {
                            "threshold_percent": rule.threshold_percent,
                            "spend_basis": (
                                rule.spend_basis.name if rule.spend_basis else "CURRENT_SPEND"
                            ),
                        }
                    )

            # Parse budget filter
            filter_info = {}
            if budget.budget_filter:
                if budget.budget_filter.projects:
                    filter_info["projects"] = list(budget.budget_filter.projects)
                if budget.budget_filter.services:
                    filter_info["services"] = list(budget.budget_filter.services)
                filter_info["credit_types_treatment"] = (
                    budget.budget_filter.credit_types_treatment.name
                    if budget.budget_filter.credit_types_treatment
                    else "INCLUDE_ALL_CREDITS"
                )

            budget_item = {
                "name": budget.name,
                "display_name": budget.display_name,
                "amount": amount_info,
                "thresholds": thresholds,
                "filter": filter_info,
                "etag": budget.etag,
            }

            budgets.append(budget_item)

        logger.info(f"✅ {operation} completed - {len(budgets)} budgets found")

        return {
            "success": True,
            "data": {
                "budgets": budgets,
                "total_count": len(budgets),
                "billing_account_id": billing_account_id,
            },
            "account_id": account_id,
            "message": f"Retrieved {len(budgets)} budgets",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)

        if "PermissionDenied" in str(e):
            error_msg += "\n\nRequired IAM role: roles/billing.viewer or roles/billing.costsManager"

        return {"success": False, "error_message": error_msg, "data": None}


async def get_budget_status(
    ctx: Context, budget_name: str, account_id: str | None = None
) -> dict[str, Any]:
    """Get budget status and current spending

    Args:
        ctx: MCP context
        budget_name: Full budget name (e.g., 'billingAccounts/123/budgets/456')
        account_id: Optional GCP account ID

    Returns:
        Dictionary with success, budget details, and current status
    """
    operation = "get_budget_status"
    logger.info(f"🔍 {operation} - Budget: {budget_name}, Account: {account_id or 'default'}")

    try:
        # Get Budget client
        budget_client = get_budget_client_for_account(account_id)

        # Get budget
        budget = budget_client.get_budget(name=budget_name)

        # Parse budget details
        amount_info = None
        if budget.amount and budget.amount.specified_amount:
            amount_info = {
                "currency_code": budget.amount.specified_amount.currency_code,
                "amount": float(budget.amount.specified_amount.units or 0)
                + float(budget.amount.specified_amount.nanos or 0) / 1e9,
            }

        thresholds = []
        if budget.threshold_rules:
            for rule in budget.threshold_rules:
                thresholds.append(
                    {
                        "threshold_percent": rule.threshold_percent,
                        "spend_basis": (
                            rule.spend_basis.name if rule.spend_basis else "CURRENT_SPEND"
                        ),
                    }
                )

        # Note: Current spending is not available via Budget API
        # Users need to query BigQuery billing export or Cost Management API for actual costs

        budget_info = {
            "name": budget.name,
            "display_name": budget.display_name,
            "amount": amount_info,
            "thresholds": thresholds,
            "status_note": "Current spending must be queried via BigQuery billing export or cost query tools",
        }

        logger.info(f"✅ {operation} completed")

        return {
            "success": True,
            "data": budget_info,
            "account_id": account_id,
            "message": "Budget information retrieved successfully",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def create_budget(ctx: Context, params: CreateBudgetParams) -> dict[str, Any]:
    """Create a new budget

    Args:
        ctx: MCP context
        params: Create budget parameters

    Returns:
        Dictionary with success and created budget info
    """
    operation = "create_budget"
    billing_account_id = params.billing_account_id
    display_name = params.display_name
    amount = params.amount
    currency_code = params.currency_code
    account_id = params.account_id

    logger.info(
        f"🔍 {operation} - Amount: {currency_code} {amount}, Account: {account_id or 'default'}"
    )

    try:
        from google.cloud.billing_budgets_v1 import Budget, BudgetAmount, Filter, ThresholdRule
        from google.type import Money

        # Get Budget client
        budget_client = get_budget_client_for_account(account_id)

        # Set default thresholds if not provided
        threshold_percents = params.threshold_percents
        if threshold_percents is None:
            threshold_percents = [0.5, 0.75, 0.9, 1.0]

        # Build threshold rules
        threshold_rules = []
        for percent in threshold_percents:
            threshold_rules.append(
                ThresholdRule(
                    threshold_percent=percent, spend_basis=ThresholdRule.Basis.CURRENT_SPEND
                )
            )

        # Build budget filter
        budget_filter = Filter(
            credit_types_treatment=Filter.CreditTypesTreatment.INCLUDE_ALL_CREDITS
        )

        project_ids = params.project_ids
        if project_ids:
            budget_filter.projects = [f"projects/{pid}" for pid in project_ids]

        # Build budget
        budget = Budget(
            display_name=display_name,
            budget_filter=budget_filter,
            amount=BudgetAmount(
                specified_amount=Money(
                    currency_code=currency_code, units=int(amount), nanos=int((amount % 1) * 1e9)
                )
            ),
            threshold_rules=threshold_rules,
        )

        # Create budget
        parent = f"billingAccounts/{billing_account_id}"
        created_budget = budget_client.create_budget(parent=parent, budget=budget)

        logger.info(f"✅ {operation} completed - Budget created: {created_budget.name}")

        return {
            "success": True,
            "data": {
                "budget_name": created_budget.name,
                "display_name": created_budget.display_name,
                "amount": amount,
                "currency": currency_code,
                "thresholds": threshold_percents,
            },
            "account_id": account_id,
            "message": f'Budget "{display_name}" created successfully',
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)

        if "PermissionDenied" in str(e):
            error_msg += "\n\nRequired IAM role: roles/billing.costsManager or roles/billing.admin"

        return {"success": False, "error_message": error_msg, "data": None}
