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

"""Data formatting utilities for CostQ RISP MCP Server.

This module provides formatting functions for RISP-related data,
following the patterns from the upstream Cost Explorer MCP Server.
"""

from datetime import datetime
from typing import Any


def format_date_for_api(date_str: str, granularity: str) -> str:
    """Format date string appropriately for AWS Cost Explorer API based on granularity."""
    if granularity is None:
        granularity = "DAILY"

    if granularity.upper() == "HOURLY":
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT00:00:00Z")
    else:
        return date_str


def format_currency(amount: str, currency_code: str = "USD") -> str:
    """Format currency amount for display."""
    try:
        amount_float = float(amount)
        if currency_code == "USD":
            return f"${amount_float:,.2f}"
        else:
            return f"{amount_float:,.2f} {currency_code}"
    except (ValueError, TypeError):
        return f"{amount} {currency_code}"


def format_percentage(percentage: str) -> str:
    """Format percentage for display."""
    try:
        percentage_float = float(percentage)
        return f"{percentage_float:.2f}%"
    except (ValueError, TypeError):
        return f"{percentage}%"


def format_hours(hours: str) -> str:
    """Format hours for display."""
    try:
        hours_float = float(hours)
        return f"{hours_float:,.0f} hours"
    except (ValueError, TypeError):
        return f"{hours} hours"


def format_ri_utilization_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format RI utilization summary for display."""
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

    AWS GetReservationCoverage API returns Total as a nested Coverage object:
    Total.CoverageHours.{CoverageHoursPercentage, OnDemandHours, ReservedHours, TotalRunningHours}
    Total.CoverageCost.{OnDemandCost}
    """
    total = response.get("Total", {})
    coverage_hours = total.get("CoverageHours", {})
    coverage_cost = total.get("CoverageCost", {})
    return {
        "coverage_percentage": format_percentage(
            coverage_hours.get("CoverageHoursPercentage", "0")
        ),
        "on_demand_hours": format_hours(coverage_hours.get("OnDemandHours", "0")),
        "reserved_hours": format_hours(coverage_hours.get("ReservedHours", "0")),
        "total_running_hours": format_hours(coverage_hours.get("TotalRunningHours", "0")),
        "on_demand_cost": format_currency(coverage_cost.get("OnDemandCost", "0")),
    }


def format_sp_utilization_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format SP utilization summary for display.

    AWS GetSavingsPlansUtilization API returns Total as a nested SavingsPlansUtilizationAggregates:
    Total.Utilization.{TotalCommitment, UsedCommitment, UnusedCommitment, UtilizationPercentage}
    Total.Savings.{NetSavings, OnDemandCostEquivalent}
    Total.AmortizedCommitment.{AmortizedRecurringCommitment, AmortizedUpfrontCommitment, TotalAmortizedCommitment}
    """
    total = response.get("Total", {})
    utilization = total.get("Utilization", {})
    savings = total.get("Savings", {})
    amortized = total.get("AmortizedCommitment", {})
    return {
        "utilization_percentage": format_percentage(
            utilization.get("UtilizationPercentage", "0")
        ),
        "total_commitment": format_currency(utilization.get("TotalCommitment", "0")),
        "used_commitment": format_currency(utilization.get("UsedCommitment", "0")),
        "unused_commitment": format_currency(utilization.get("UnusedCommitment", "0")),
        "amortized_commitment": format_currency(
            amortized.get("TotalAmortizedCommitment", "0")
        ),
        "on_demand_cost_equivalent": format_currency(
            savings.get("OnDemandCostEquivalent", "0")
        ),
        "net_savings": format_currency(savings.get("NetSavings", "0")),
    }


def format_sp_coverage_summary(
    response: dict[str, Any],
    all_coverages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Format SP coverage summary for display.

    AWS GetSavingsPlansCoverage API has NO 'Total' field in the response.
    Summary must be aggregated from the SavingsPlansCoverages array items.
    Each item has: Coverage.{CoveragePercentage, OnDemandCost, SpendCoveredBySavingsPlans, TotalCost}
    """
    coverages = all_coverages or response.get("SavingsPlansCoverages", [])

    if not coverages:
        return {
            "coverage_percentage": format_percentage("0"),
            "on_demand_cost": format_currency("0"),
            "spend_covered_by_savings_plans": format_currency("0"),
            "total_cost": format_currency("0"),
        }

    total_on_demand = 0.0
    total_covered = 0.0
    total_cost = 0.0

    for item in coverages:
        coverage = item.get("Coverage", {})
        try:
            total_on_demand += float(coverage.get("OnDemandCost", "0"))
            total_covered += float(coverage.get("SpendCoveredBySavingsPlans", "0"))
            total_cost += float(coverage.get("TotalCost", "0"))
        except (ValueError, TypeError):
            continue

    coverage_pct = (total_covered / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "coverage_percentage": format_percentage(str(coverage_pct)),
        "on_demand_cost": format_currency(str(total_on_demand)),
        "spend_covered_by_savings_plans": format_currency(str(total_covered)),
        "total_cost": format_currency(str(total_cost)),
    }


def format_sp_purchase_recommendation_summary(response: dict[str, Any]) -> dict[str, Any]:
    """Format SP purchase recommendation summary for display."""
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
    """Format SP purchase recommendation details for display."""
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
    """Format error response for consistent error handling."""
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
    """Format success response for consistent response structure."""
    response = {
        "success": True,
        "operation": operation,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if summary:
        response["summary"] = summary

    return response
