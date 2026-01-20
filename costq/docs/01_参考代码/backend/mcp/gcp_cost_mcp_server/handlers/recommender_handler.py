"""
Recommender Handler - Cost Optimization Recommendations

Implements cost optimization tools using GCP Recommender API.
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

from backend.mcp.gcp_cost_mcp_server.constants import RECOMMENDER_TYPES
from backend.mcp.gcp_cost_mcp_server.models.recommender_models import (
    IdleResourcesParams,
    VmRightsizingRecommendationsParams,
)
from backend.mcp.gcp_cost_mcp_server.utils.multi_account_client import (
    get_bigquery_client_for_account,
    get_recommender_client_for_account,
)
from backend.services.gcp_credentials_provider import get_gcp_credentials_provider


async def get_vm_rightsizing_recommendations(
    ctx: Context, params: VmRightsizingRecommendationsParams
) -> dict[str, Any]:
    """Get VM rightsizing recommendations

    Retrieves machine type recommendations for over-provisioned VMs.

    Args:
        ctx: MCP context
        params: VM rightsizing recommendations parameters

    Returns:
        Dictionary with success, recommendations list, and summary
    """
    operation = "get_vm_rightsizing_recommendations"
    project_id = params.project_id
    account_id = params.account_id
    location = params.location

    logger.info(f"🔍 {operation} - Project: {project_id}, Account: {account_id or 'default'}")

    try:
        # Get Recommender client
        recommender_client = get_recommender_client_for_account(account_id)

        # Build parent path
        parent = (
            f"projects/{project_id}/locations/{location}/recommenders/"
            f"{RECOMMENDER_TYPES['VM_RIGHTSIZING']}"
        )

        # List recommendations
        recommendations = []
        total_savings = 0.0
        currency = "USD"

        count = 0
        for recommendation in recommender_client.list_recommendations(parent=parent):
            # Parse cost impact
            cost_impact = None
            if recommendation.primary_impact and recommendation.primary_impact.cost_projection:
                cost_proj = recommendation.primary_impact.cost_projection
                if cost_proj.cost:
                    monthly_savings = abs(
                        float(cost_proj.cost.units or 0) + float(cost_proj.cost.nanos or 0) / 1e9
                    )
                    currency = cost_proj.cost.currency_code
                    total_savings += monthly_savings

                    cost_impact = {
                        "currency_code": currency,
                        "monthly_savings": round(monthly_savings, 2),
                        "annual_savings": round(monthly_savings * 12, 2),
                    }

            # Extract target resources
            target_resources = []
            if recommendation.content and recommendation.content.operation_groups:
                for op_group in recommendation.content.operation_groups:
                    for operation in op_group.operations:
                        if operation.resource:
                            target_resources.append(operation.resource)

            rec_item = {
                "recommendation_id": recommendation.name,
                "recommender_type": "VM_RIGHTSIZING",
                "description": recommendation.description,
                "state": recommendation.state.name if recommendation.state else "UNKNOWN",
                "priority": recommendation.priority.name if recommendation.priority else None,
                "cost_impact": cost_impact,
                "target_resources": target_resources,
                "last_refresh_time": (
                    recommendation.last_refresh_time.isoformat()
                    if recommendation.last_refresh_time
                    else None
                ),
            }

            recommendations.append(rec_item)
            count += 1

            max_results = params.max_results
            if max_results and count >= max_results:
                break

        logger.info(
            f"✅ {operation} completed - {len(recommendations)} recommendations, "
            f"potential savings: {currency} {total_savings:.2f}/month"
        )

        return {
            "success": True,
            "data": {
                "recommendations": recommendations,
                "total_count": len(recommendations),
                "total_potential_savings": round(total_savings, 2),
                "currency": currency,
                "project_id": project_id,
                "recommender_type": "VM_RIGHTSIZING",
            },
            "account_id": account_id,
            "message": f"Retrieved {len(recommendations)} VM rightsizing recommendations",
        }

    except Exception as e:
        error_msg = f"{operation} failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)

        # Check for permission/service errors
        if "PermissionDenied" in str(e) or "permission" in str(e).lower():
            error_msg += "\n\nRequired IAM role: roles/recommender.viewer"
        elif "not found" in str(e).lower() or "not enabled" in str(e).lower():
            error_msg += "\n\nPlease enable Recommender API: gcloud services enable recommender.googleapis.com"

        return {"success": False, "error_message": error_msg, "data": None}


async def get_idle_resources(ctx: Context, params: IdleResourcesParams) -> dict[str, Any]:
    """Get idle resource recommendations

    Identifies idle VMs, disks, and IP addresses.

    Args:
        ctx: MCP context
        params: Idle resources parameters

    Returns:
        Dictionary with success, recommendations by type, and summary
    """
    operation = "get_idle_resources"
    project_id = params.project_id
    account_id = params.account_id
    location = params.location

    logger.info(f"🔍 {operation} - Project: {project_id}, Account: {account_id or 'default'}")

    try:
        resource_types = params.resource_types
        if resource_types is None:
            resource_types = ["VM", "DISK", "IP"]

        recommender_client = get_recommender_client_for_account(account_id)

        all_recommendations = []
        total_savings = 0.0
        currency = "USD"
        recommendations_by_type = {}

        # Map resource types to recommender types
        recommender_map = {
            "VM": RECOMMENDER_TYPES["IDLE_VM"],
            "DISK": RECOMMENDER_TYPES["IDLE_DISK"],
            "IP": RECOMMENDER_TYPES["IDLE_IP"],
        }

        for resource_type in resource_types:
            if resource_type not in recommender_map:
                logger.warning(f"Unknown resource type: {resource_type}")
                continue

            recommender_type = recommender_map[resource_type]
            parent = f"projects/{project_id}/locations/{location}/recommenders/{recommender_type}"

            type_recommendations = []
            type_savings = 0.0

            try:
                for recommendation in recommender_client.list_recommendations(parent=parent):
                    cost_impact = None
                    if (
                        recommendation.primary_impact
                        and recommendation.primary_impact.cost_projection
                    ):
                        cost_proj = recommendation.primary_impact.cost_projection
                        if cost_proj.cost:
                            monthly_savings = abs(
                                float(cost_proj.cost.units or 0)
                                + float(cost_proj.cost.nanos or 0) / 1e9
                            )
                            currency = cost_proj.cost.currency_code
                            type_savings += monthly_savings
                            total_savings += monthly_savings

                            cost_impact = {
                                "currency_code": currency,
                                "monthly_savings": round(monthly_savings, 2),
                            }

                    rec_item = {
                        "recommendation_id": recommendation.name,
                        "resource_type": resource_type,
                        "description": recommendation.description,
                        "state": recommendation.state.name if recommendation.state else "UNKNOWN",
                        "cost_impact": cost_impact,
                    }

                    type_recommendations.append(rec_item)
                    all_recommendations.append(rec_item)

                recommendations_by_type[resource_type] = {
                    "count": len(type_recommendations),
                    "total_savings": round(type_savings, 2),
                    "recommendations": type_recommendations,
                }

            except Exception as e:
                logger.warning(f"Failed to get {resource_type} recommendations: {e}")
                recommendations_by_type[resource_type] = {
                    "count": 0,
                    "total_savings": 0.0,
                    "recommendations": [],
                    "error": str(e),
                }

        logger.info(
            f"✅ {operation} completed - {len(all_recommendations)} idle resources, "
            f"savings: {currency} {total_savings:.2f}/month"
        )

        return {
            "success": True,
            "data": {
                "by_type": recommendations_by_type,
                "total_recommendations": len(all_recommendations),
                "total_potential_savings": round(total_savings, 2),
                "currency": currency,
                "project_id": project_id,
            },
            "account_id": account_id,
            "message": f"Found {len(all_recommendations)} idle resources",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def get_commitment_recommendations(
    ctx: Context,
    project_id: str = None,
    billing_account_id: str = None,
    location: str = "-",
    account_id: str | None = None,
) -> dict[str, Any]:
    """Get commitment (CUD) purchase recommendations

    **Supports both project-level and organization-level queries.**

    Args:
        ctx: MCP context
        project_id: GCP project ID (for single project query). Optional.
        billing_account_id: Billing account ID (for org-level query). Optional.
        location: Location ('-' for all)
        account_id: Optional GCP account ID

    Returns:
        Dictionary with success, CUD recommendations, and savings

    Note:
        Provide either project_id OR billing_account_id, not both.
        If neither is provided, will use the default from account configuration.
    """
    operation = "get_commitment_recommendations"

    # Smart default: use billing_account_id if available, otherwise project_id
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
        # If billing_account_id is provided, query all projects under it
        if billing_account_id:
            bq_client = get_bigquery_client_for_account(account_id)

            # Get list of projects for this billing account
            credentials_provider = get_gcp_credentials_provider()
            table_name = credentials_provider.get_bigquery_table_name(account_id)

            query = f"""
            SELECT DISTINCT project.id AS project_id
            FROM `{table_name}`
            WHERE billing_account_id = '{billing_account_id}'
              AND _PARTITIONDATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            """

            query_job = bq_client.query(query)
            project_ids = [row.project_id for row in query_job.result()]

            logger.info(
                f"📊 Found {len(project_ids)} projects for billing account {billing_account_id}"
            )

            # Query recommendations for each project and aggregate
            all_recommendations = []
            total_savings = 0.0
            currency = "USD"

            recommender_client = get_recommender_client_for_account(account_id)

            for proj_id in project_ids:
                parent = (
                    f"projects/{proj_id}/locations/{location}/recommenders/"
                    f"{RECOMMENDER_TYPES['COMMITMENT']}"
                )

                try:
                    for recommendation in recommender_client.list_recommendations(parent=parent):
                        cost_impact = None
                        if (
                            recommendation.primary_impact
                            and recommendation.primary_impact.cost_projection
                        ):
                            cost_proj = recommendation.primary_impact.cost_projection
                            if cost_proj.cost:
                                monthly_savings = abs(
                                    float(cost_proj.cost.units or 0)
                                    + float(cost_proj.cost.nanos or 0) / 1e9
                                )
                                currency = cost_proj.cost.currency_code
                                total_savings += monthly_savings

                                cost_impact = {
                                    "currency_code": currency,
                                    "monthly_savings": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                }

                        rec_item = {
                            "recommendation_id": recommendation.name,
                            "recommender_type": "COMMITMENT",
                            "project_id": proj_id,  # Add project_id for context
                            "description": recommendation.description,
                            "state": (
                                recommendation.state.name if recommendation.state else "UNKNOWN"
                            ),
                            "cost_impact": cost_impact,
                            "last_refresh_time": (
                                recommendation.last_refresh_time.isoformat()
                                if recommendation.last_refresh_time
                                else None
                            ),
                        }

                        all_recommendations.append(rec_item)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to get recommendations for project {proj_id}: {e}")
                    continue

            logger.info(
                f"✅ {operation} completed - {len(all_recommendations)} CUD recommendations across {len(project_ids)} projects, "
                f"savings: {currency} {total_savings:.2f}/month"
            )

            return {
                "success": True,
                "data": {
                    "recommendations": all_recommendations,
                    "total_count": len(all_recommendations),
                    "total_potential_savings": round(total_savings, 2),
                    "currency": currency,
                    "billing_account_id": billing_account_id,
                    "project_count": len(project_ids),
                },
                "account_id": account_id,
                "message": f"Retrieved {len(all_recommendations)} commitment recommendations across {len(project_ids)} projects",
            }

        # Single project query (original logic)
        recommender_client = get_recommender_client_for_account(account_id)

        parent = (
            f"projects/{project_id}/locations/{location}/recommenders/"
            f"{RECOMMENDER_TYPES['COMMITMENT']}"
        )

        recommendations = []
        total_savings = 0.0
        currency = "USD"

        for recommendation in recommender_client.list_recommendations(parent=parent):
            cost_impact = None
            if recommendation.primary_impact and recommendation.primary_impact.cost_projection:
                cost_proj = recommendation.primary_impact.cost_projection
                if cost_proj.cost:
                    monthly_savings = abs(
                        float(cost_proj.cost.units or 0) + float(cost_proj.cost.nanos or 0) / 1e9
                    )
                    currency = cost_proj.cost.currency_code
                    total_savings += monthly_savings

                    cost_impact = {
                        "currency_code": currency,
                        "monthly_savings": round(monthly_savings, 2),
                        "annual_savings": round(monthly_savings * 12, 2),
                    }

            rec_item = {
                "recommendation_id": recommendation.name,
                "recommender_type": "COMMITMENT",
                "description": recommendation.description,
                "state": recommendation.state.name if recommendation.state else "UNKNOWN",
                "cost_impact": cost_impact,
                "last_refresh_time": (
                    recommendation.last_refresh_time.isoformat()
                    if recommendation.last_refresh_time
                    else None
                ),
            }

            recommendations.append(rec_item)

        logger.info(
            f"✅ {operation} completed - {len(recommendations)} CUD recommendations, "
            f"savings: {currency} {total_savings:.2f}/month"
        )

        return {
            "success": True,
            "data": {
                "recommendations": recommendations,
                "total_count": len(recommendations),
                "total_potential_savings": round(total_savings, 2),
                "currency": currency,
                "project_id": project_id,
            },
            "account_id": account_id,
            "message": f"Retrieved {len(recommendations)} commitment recommendations",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def get_all_recommendations(
    ctx: Context,
    project_id: str = None,
    billing_account_id: str = None,
    location: str = "-",
    account_id: str | None = None,
) -> dict[str, Any]:
    """Get all cost optimization recommendations

    Aggregates all types of recommendations.

    **Supports both project-level and organization-level queries.**

    Args:
        ctx: MCP context
        project_id: GCP project ID (for single project query). Optional.
        billing_account_id: Billing account ID (for org-level query). Optional.
        location: Location ('-' for all)
        account_id: Optional GCP account ID

    Returns:
        Dictionary with success, recommendations by type, and total savings

    Note:
        Provide either project_id OR billing_account_id, not both.
        If neither is provided, will use the default from account configuration.
    """
    operation = "get_all_recommendations"

    # Smart default: use billing_account_id if available, otherwise project_id
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
        # Get all recommendation types (pass billing_account_id to each function)
        vm_result = await get_vm_rightsizing_recommendations(
            ctx, project_id, billing_account_id, location, None, account_id
        )
        idle_result = await get_idle_resources(
            ctx, project_id, billing_account_id, None, location, account_id
        )
        cud_result = await get_commitment_recommendations(
            ctx, project_id, billing_account_id, location, account_id
        )

        # Aggregate results
        by_type = []
        total_recommendations = 0
        total_savings = 0.0
        currency = "USD"

        if vm_result.get("success"):
            vm_data = vm_result["data"]
            by_type.append(
                {
                    "recommender_type": "VM_RIGHTSIZING",
                    "count": vm_data["total_count"],
                    "total_savings": vm_data["total_potential_savings"],
                    "currency": vm_data["currency"],
                }
            )
            total_recommendations += vm_data["total_count"]
            total_savings += vm_data["total_potential_savings"]
            currency = vm_data["currency"]

        if idle_result.get("success"):
            idle_data = idle_result["data"]
            by_type.append(
                {
                    "recommender_type": "IDLE_RESOURCES",
                    "count": idle_data["total_recommendations"],
                    "total_savings": idle_data["total_potential_savings"],
                    "currency": idle_data["currency"],
                }
            )
            total_recommendations += idle_data["total_recommendations"]
            total_savings += idle_data["total_potential_savings"]

        if cud_result.get("success"):
            cud_data = cud_result["data"]
            by_type.append(
                {
                    "recommender_type": "COMMITMENT",
                    "count": cud_data["total_count"],
                    "total_savings": cud_data["total_potential_savings"],
                    "currency": cud_data["currency"],
                }
            )
            total_recommendations += cud_data["total_count"]
            total_savings += cud_data["total_potential_savings"]

        logger.info(
            f"✅ {operation} completed - {total_recommendations} total recommendations, "
            f"savings: {currency} {total_savings:.2f}/month"
        )

        return {
            "success": True,
            "data": {
                "by_type": by_type,
                "total_recommendations": total_recommendations,
                "total_potential_savings": round(total_savings, 2),
                "currency": currency,
                "project_id": project_id,
            },
            "account_id": account_id,
            "message": f"Retrieved {total_recommendations} total recommendations",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}


async def mark_recommendation_status(
    ctx: Context,
    recommendation_name: str,
    state: str,
    state_metadata: dict[str, str] | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Mark recommendation status (CLAIMED, SUCCEEDED, FAILED, DISMISSED)

    Args:
        ctx: MCP context
        recommendation_name: Full recommendation name
        state: New state ('CLAIMED', 'SUCCEEDED', 'FAILED', 'DISMISSED')
        state_metadata: Optional metadata
        account_id: Optional GCP account ID

    Returns:
        Dictionary with success and updated recommendation info
    """
    operation = "mark_recommendation_status"
    logger.info(f"🔍 {operation} - State: {state}, Account: {account_id or 'default'}")

    try:
        recommender_client = get_recommender_client_for_account(account_id)

        state = state.upper()
        valid_states = ["CLAIMED", "SUCCEEDED", "FAILED", "DISMISSED"]

        if state not in valid_states:
            return {
                "success": False,
                "error_message": f"Invalid state: {state}. Must be one of: {valid_states}",
                "data": None,
            }

        # Call appropriate method based on state
        if state == "CLAIMED":
            updated = recommender_client.mark_recommendation_claimed(
                name=recommendation_name, state_metadata=state_metadata or {}
            )
        elif state == "SUCCEEDED":
            updated = recommender_client.mark_recommendation_succeeded(
                name=recommendation_name, state_metadata=state_metadata or {}
            )
        elif state == "FAILED":
            updated = recommender_client.mark_recommendation_failed(
                name=recommendation_name, state_metadata=state_metadata or {}
            )
        elif state == "DISMISSED":
            updated = recommender_client.mark_recommendation_dismissed(
                name=recommendation_name, state_metadata=state_metadata or {}
            )

        logger.info(f"✅ {operation} completed - Marked as {state}")

        return {
            "success": True,
            "data": {
                "recommendation_name": updated.name,
                "new_state": updated.state.name if updated.state else "UNKNOWN",
                "description": updated.description,
            },
            "account_id": account_id,
            "message": f"Recommendation marked as {state}",
        }

    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        return {"success": False, "error_message": str(e), "data": None}
