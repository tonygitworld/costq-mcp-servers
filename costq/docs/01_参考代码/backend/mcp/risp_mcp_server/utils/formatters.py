# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Data formatting utilities for RISP MCP Server.

This module provides formatting functions for RISP-related data,
following the patterns from the upstream Cost Explorer MCP Server.
"""

from datetime import datetime
from typing import Any


def format_date_for_api(date_str: str, granularity: str) -> str:
    """Format date string appropriately for AWS Cost Explorer API based on granularity.

    Args:
        date_str: Date string in YYYY-MM-DD format
        granularity: The granularity (DAILY, MONTHLY, HOURLY), can be None

    Returns:
        Formatted date string appropriate for the API call
    """
    # 处理 granularity 为 None 的情况
    if granularity is None:
        granularity = "DAILY"

    if granularity.upper() == "HOURLY":
        # For hourly granularity, AWS expects datetime format
        # Convert YYYY-MM-DD to YYYY-MM-DDTHH:MM:SSZ
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT00:00:00Z")
    else:
        # For DAILY and MONTHLY, use the original date format
        return date_str


def format_currency(amount: str, currency_code: str = "USD") -> str:
    """Format currency amount for display.

    Args:
        amount: Amount as string
        currency_code: Currency code (default: USD)

    Returns:
        Formatted currency string
    """
    try:
        amount_float = float(amount)
        if currency_code == "USD":
            return f"${amount_float:,.2f}"
        else:
            return f"{amount_float:,.2f} {currency_code}"
    except (ValueError, TypeError):
        return f"{amount} {currency_code}"


def format_percentage(percentage: str) -> str:
    """Format percentage for display.

    Args:
        percentage: Percentage as string

    Returns:
        Formatted percentage string
    """
    try:
        percentage_float = float(percentage)
        return f"{percentage_float:.2f}%"
    except (ValueError, TypeError):
        return f"{percentage}%"


def format_hours(hours: str) -> str:
    """Format hours for display.

    Args:
        hours: Hours as string

    Returns:
        Formatted hours string
    """
    try:
        hours_float = float(hours)
        return f"{hours_float:,.0f} hours"
    except (ValueError, TypeError):
        return f"{hours} hours"


def format_ri_utilization_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format RI utilization summary for display.

    Args:
        response: Raw AWS API response

    Returns:
        Formatted summary dictionary
    """
    total = response.get("Total", {})
    return {
        "utilization_percentage": format_percentage(total.get("UtilizationPercentage", "0")),
        "purchased_hours": format_hours(total.get("PurchasedHours", "0")),
        "used_hours": format_hours(total.get("TotalActualHours", "0")),
        "unused_hours": format_hours(total.get("UnusedHours", "0")),
        "net_savings": format_currency(total.get("NetRISavings", "0")),
        "total_potential_savings": format_currency(total.get("TotalPotentialRISavings", "0")),
        "amortized_upfront_fee": format_currency(total.get("AmortizedUpfrontFee", "0")),
        "amortized_recurring_fee": format_currency(total.get("AmortizedRecurringFee", "0")),
        "total_amortized_fee": format_currency(total.get("TotalAmortizedFee", "0")),
        "on_demand_cost_equivalent": format_currency(total.get("OnDemandCostOfRIHoursUsed", "0")),
        "realized_savings": format_currency(total.get("RealizedSavings", "0")),
        "unrealized_savings": format_currency(total.get("UnrealizedSavings", "0")),
    }


def format_ri_coverage_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format RI coverage summary for display.

    Args:
        response: Raw AWS API response

    Returns:
        Formatted summary dictionary
    """
    total = response.get("Total", {})
    return {
        "coverage_percentage": format_percentage(total.get("CoveragePercentage", "0")),
        "on_demand_hours": format_hours(total.get("OnDemandHours", "0")),
        "reserved_hours": format_hours(total.get("ReservedHours", "0")),
        "total_running_hours": format_hours(total.get("TotalRunningHours", "0")),
        "coverage_hours_percentage": format_percentage(total.get("CoverageHoursPercentage", "0")),
        "on_demand_cost": format_currency(total.get("OnDemandCost", "0")),
        "coverage_cost_percentage": format_percentage(total.get("CoverageCostPercentage", "0")),
    }


def format_sp_utilization_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format SP utilization summary for display.

    Args:
        response: Raw AWS API response

    Returns:
        Formatted summary dictionary
    """
    total = response.get("Total", {})
    return {
        "utilization_percentage": format_percentage(total.get("UtilizationPercentage", "0")),
        "total_commitment": format_currency(total.get("TotalCommitment", "0")),
        "used_commitment": format_currency(total.get("UsedCommitment", "0")),
        "unused_commitment": format_currency(total.get("UnusedCommitment", "0")),
        "utilization_percentage_in_units": format_percentage(
            total.get("UtilizationPercentageInUnits", "0")
        ),
        "amortized_commitment": format_currency(total.get("SavingsPlansAmortizedCommitment", "0")),
        "on_demand_cost_equivalent": format_currency(total.get("OnDemandCostEquivalent", "0")),
        "net_savings": format_currency(total.get("NetSavings", "0")),
    }


def format_sp_coverage_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format SP coverage summary for display.

    Args:
        response: Raw AWS API response

    Returns:
        Formatted summary dictionary
    """
    total = response.get("Total", {})
    return {
        "coverage_percentage": format_percentage(total.get("CoveragePercentage", "0")),
        "on_demand_spend": format_currency(total.get("OnDemandSpend", "0")),
        "spend_covered_by_savings_plans": format_currency(
            total.get("SpendCoveredBySavingsPlans", "0")
        ),
        "total_spend": format_currency(total.get("TotalSpend", "0")),
    }


def format_sp_purchase_recommendation_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format SP purchase recommendation summary for display.

    Args:
        response: Raw AWS API response

    Returns:
        Formatted summary dictionary
    """
    recommendation = response.get("SavingsPlansPurchaseRecommendation", {})
    summary = recommendation.get("SavingsPlansPurchaseRecommendationSummary", {})

    return {
        "total_recommendations": summary.get("TotalRecommendationCount", "0"),
        "estimated_monthly_savings": format_currency(
            summary.get("EstimatedMonthlySavingsAmount", "0")
        ),
        "estimated_savings_percentage": format_percentage(
            summary.get("EstimatedSavingsPercentage", "0")
        ),
        "estimated_roi": format_percentage(summary.get("EstimatedROI", "0")),
        "hourly_commitment_to_purchase": format_currency(
            summary.get("HourlyCommitmentToPurchase", "0")
        ),
        "daily_commitment_to_purchase": format_currency(
            summary.get("DailyCommitmentToPurchase", "0")
        ),
        "current_on_demand_spend": format_currency(summary.get("CurrentOnDemandSpend", "0")),
        "estimated_total_cost": format_currency(summary.get("EstimatedTotalCost", "0")),
        "currency_code": summary.get("CurrencyCode", "USD"),
    }


def format_sp_purchase_recommendations(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Format SP purchase recommendation details for display.

    Args:
        response: Raw AWS API response

    Returns:
        List of formatted recommendation dictionaries
    """
    recommendation = response.get("SavingsPlansPurchaseRecommendation", {})
    details = recommendation.get("SavingsPlansPurchaseRecommendationDetails", [])

    formatted_recommendations = []
    for detail in details:
        sp_details = detail.get("SavingsPlansDetails", {})
        formatted_recommendations.append(
            {
                "recommendation_id": detail.get("RecommendationDetailId", ""),
                "account_id": detail.get("AccountId", ""),
                "hourly_commitment": format_currency(detail.get("HourlyCommitmentToPurchase", "0")),
                "upfront_cost": format_currency(detail.get("UpfrontCost", "0")),
                "estimated_monthly_savings": format_currency(
                    detail.get("EstimatedMonthlySavingsAmount", "0")
                ),
                "estimated_savings_percentage": format_percentage(
                    detail.get("EstimatedSavingsPercentage", "0")
                ),
                "estimated_roi": format_percentage(detail.get("EstimatedROI", "0")),
                "estimated_sp_cost": format_currency(detail.get("EstimatedSPCost", "0")),
                "estimated_on_demand_cost": format_currency(
                    detail.get("EstimatedOnDemandCost", "0")
                ),
                "estimated_average_utilization": format_percentage(
                    detail.get("EstimatedAverageUtilization", "0")
                ),
                "current_average_hourly_spend": format_currency(
                    detail.get("CurrentAverageHourlyOnDemandSpend", "0")
                ),
                "current_max_hourly_spend": format_currency(
                    detail.get("CurrentMaximumHourlyOnDemandSpend", "0")
                ),
                "current_min_hourly_spend": format_currency(
                    detail.get("CurrentMinimumHourlyOnDemandSpend", "0")
                ),
                "savings_plans_details": {
                    "offering_id": sp_details.get("OfferingId", ""),
                    "instance_family": sp_details.get("InstanceFamily", ""),
                    "region": sp_details.get("Region", ""),
                },
                "currency_code": detail.get("CurrencyCode", "USD"),
            }
        )

    return formatted_recommendations


def format_error_response(error: Exception, operation: str) -> dict[str, Any]:
    """Format error response for consistent error handling.

    Args:
        error: Exception that occurred
        operation: Operation that failed

    Returns:
        Formatted error response dictionary
    """
    return {
        "success": False,
        "error": str(error),
        "operation": operation,
        "message": f"{operation} failed: {str(error)}",
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_success_response(
    data: Any, operation: str, summary: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Format success response for consistent response structure.

    Args:
        data: Response data
        operation: Operation that succeeded
        summary: Optional summary data

    Returns:
        Formatted success response dictionary
    """
    response = {
        "success": True,
        "operation": operation,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if summary:
        response["summary"] = summary

    return response
