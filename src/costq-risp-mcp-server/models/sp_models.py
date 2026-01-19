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

"""Savings Plans data models for RISP MCP Server.

This module contains data models specific to Savings Plans operations.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from constants import (
    VALID_ACCOUNT_SCOPES,
    VALID_LOOKBACK_PERIODS,
    VALID_PAYMENT_OPTIONS,
    VALID_SAVINGS_PLANS_TYPES,
    VALID_SP_SORT_KEYS,
    VALID_TERM_IN_YEARS,
)
from .common_models import (
    BaseRISPRequest,
    BaseRISPResponse,
    DateRange,
    FilterExpression,
    GroupDefinition,
    PaginationRequest,
    SortDefinition,
)


class SavingsPlansUtilizationRequest(BaseRISPRequest):
    """Request model for SP utilization analysis."""

    sort_by: SortDefinition | None = Field(default=None, description="Sort definition for results")
    pagination: PaginationRequest | None = Field(default=None, description="Pagination settings")

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v):
        """Validate sort definition."""
        if v is not None and v.Key not in VALID_SP_SORT_KEYS:
            raise ValueError(f"Invalid sort key '{v.Key}'. Valid keys: {VALID_SP_SORT_KEYS}")
        return v


class SavingsPlansCoverageRequest(BaseRISPRequest):
    """Request model for SP coverage analysis."""

    group_by: list[GroupDefinition] | None = Field(default=None, description="Group by dimensions")
    sort_by: SortDefinition | None = Field(default=None, description="Sort definition for results")
    pagination: PaginationRequest | None = Field(default=None, description="Pagination settings")

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v):
        """Validate sort definition."""
        if v is not None and v.Key not in VALID_SP_SORT_KEYS:
            raise ValueError(f"Invalid sort key '{v.Key}'. Valid keys: {VALID_SP_SORT_KEYS}")
        return v


class SavingsPlansPurchaseRecommendationRequest(BaseModel):
    """Request model for SP purchase recommendations."""

    savings_plans_type: str = Field(
        description="Savings Plans type (COMPUTE_SP, EC2_INSTANCE_SP, SAGEMAKER_SP)"
    )
    term_in_years: str = Field(description="Term length (ONE_YEAR, THREE_YEARS)")
    payment_option: str = Field(
        description="Payment option (NO_UPFRONT, PARTIAL_UPFRONT, ALL_UPFRONT)"
    )
    lookback_period_in_days: str = Field(
        description="Lookback period (SEVEN_DAYS, THIRTY_DAYS, SIXTY_DAYS)"
    )
    account_scope: str | None = Field(default="PAYER", description="Account scope (PAYER, LINKED)")
    filter_expression: FilterExpression | None = Field(
        default=None, description="Filter conditions"
    )
    pagination: PaginationRequest | None = Field(default=None, description="Pagination settings")

    @field_validator("savings_plans_type")
    @classmethod
    def validate_savings_plans_type(cls, v):
        """Validate Savings Plans type."""
        if v not in VALID_SAVINGS_PLANS_TYPES:
            raise ValueError(
                f"Invalid savings_plans_type '{v}'. Valid types: {VALID_SAVINGS_PLANS_TYPES}"
            )
        return v

    @field_validator("term_in_years")
    @classmethod
    def validate_term_in_years(cls, v):
        """Validate term in years."""
        if v not in VALID_TERM_IN_YEARS:
            raise ValueError(f"Invalid term '{v}'. Valid terms: {VALID_TERM_IN_YEARS}")
        return v

    @field_validator("payment_option")
    @classmethod
    def validate_payment_option(cls, v):
        """Validate payment option."""
        if v not in VALID_PAYMENT_OPTIONS:
            raise ValueError(
                f"Invalid payment option '{v}'. Valid options: {VALID_PAYMENT_OPTIONS}"
            )
        return v

    @field_validator("lookback_period_in_days")
    @classmethod
    def validate_lookback_period(cls, v):
        """Validate lookback period."""
        if v not in VALID_LOOKBACK_PERIODS:
            raise ValueError(
                f"Invalid lookback period '{v}'. Valid periods: {VALID_LOOKBACK_PERIODS}"
            )
        return v

    @field_validator("account_scope")
    @classmethod
    def validate_account_scope(cls, v):
        """Validate account scope."""
        if v not in VALID_ACCOUNT_SCOPES:
            raise ValueError(f"Invalid account scope '{v}'. Valid scopes: {VALID_ACCOUNT_SCOPES}")
        return v


class SavingsPlansUtilizationResponse(BaseRISPResponse):
    """Response model for SP utilization analysis."""

    utilization_summary: dict[str, Any] | None = Field(
        default=None, description="Formatted utilization summary"
    )
    utilizations_by_time: list[dict[str, Any]] | None = Field(
        default=None, description="Time-series utilization data"
    )
    savings_plans_utilization_details: list[dict[str, Any]] | None = Field(
        default=None, description="Detailed utilization by Savings Plans"
    )
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


class SavingsPlansCoverageResponse(BaseRISPResponse):
    """Response model for SP coverage analysis."""

    coverage_summary: dict[str, Any] | None = Field(
        default=None, description="Formatted coverage summary"
    )
    coverages_by_time: list[dict[str, Any]] | None = Field(
        default=None, description="Time-series coverage data"
    )
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


class SavingsPlansPurchaseRecommendationResponse(BaseRISPResponse):
    """Response model for SP purchase recommendations."""

    recommendation_summary: dict[str, Any] | None = Field(
        default=None, description="Formatted recommendation summary"
    )
    recommendations: list[dict[str, Any]] | None = Field(
        default=None, description="List of purchase recommendations"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="Recommendation metadata")
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


class SavingsPlansDetails(BaseModel):
    """Model for Savings Plans details."""

    offering_id: str | None = Field(default=None, description="Savings Plans offering ID")
    instance_family: str | None = Field(default=None, description="Instance family")
    region: str | None = Field(default=None, description="AWS region")


class SavingsPlansUtilizationDetail(BaseModel):
    """Model for SP utilization detail."""

    savings_plans_arn: str | None = Field(default=None, description="Savings Plans ARN")
    attributes: dict[str, str] | None = Field(default=None, description="Savings Plans attributes")
    utilization: dict[str, Any] | None = Field(default=None, description="Utilization metrics")
    savings: dict[str, Any] | None = Field(default=None, description="Savings metrics")
    amortized_commitment: dict[str, Any] | None = Field(
        default=None, description="Amortized commitment"
    )


class SavingsPlansCoverageData(BaseModel):
    """Model for SP coverage data."""

    spend_covered_by_savings_plans: str | None = Field(
        default=None, description="Spend covered by Savings Plans"
    )
    on_demand_spend: str | None = Field(default=None, description="On-demand spend")
    total_spend: str | None = Field(default=None, description="Total spend")
    coverage_percentage: str | None = Field(default=None, description="Coverage percentage")


class SavingsPlansPurchaseRecommendationDetail(BaseModel):
    """Model for SP purchase recommendation detail."""

    recommendation_detail_id: str | None = Field(
        default=None, description="Recommendation detail ID"
    )
    account_id: str | None = Field(default=None, description="AWS account ID")
    currency_code: str | None = Field(default=None, description="Currency code")
    current_average_hourly_on_demand_spend: str | None = Field(
        default=None, description="Current average hourly on-demand spend"
    )
    current_maximum_hourly_on_demand_spend: str | None = Field(
        default=None, description="Current maximum hourly on-demand spend"
    )
    current_minimum_hourly_on_demand_spend: str | None = Field(
        default=None, description="Current minimum hourly on-demand spend"
    )
    estimated_average_utilization: str | None = Field(
        default=None, description="Estimated average utilization"
    )
    estimated_monthly_savings_amount: str | None = Field(
        default=None, description="Estimated monthly savings amount"
    )
    estimated_on_demand_cost: str | None = Field(
        default=None, description="Estimated on-demand cost"
    )
    estimated_on_demand_cost_with_current_commitment: str | None = Field(
        default=None, description="Estimated on-demand cost with current commitment"
    )
    estimated_roi: str | None = Field(default=None, description="Estimated ROI")
    estimated_savings_amount: str | None = Field(
        default=None, description="Estimated savings amount"
    )
    estimated_savings_percentage: str | None = Field(
        default=None, description="Estimated savings percentage"
    )
    estimated_sp_cost: str | None = Field(default=None, description="Estimated SP cost")
    hourly_commitment_to_purchase: str | None = Field(
        default=None, description="Hourly commitment to purchase"
    )
    savings_plans_details: SavingsPlansDetails | None = Field(
        default=None, description="Savings Plans details"
    )
    upfront_cost: str | None = Field(default=None, description="Upfront cost")


class SavingsPlansPurchaseRecommendationSummary(BaseModel):
    """Model for SP purchase recommendation summary."""

    currency_code: str | None = Field(default=None, description="Currency code")
    current_on_demand_spend: str | None = Field(default=None, description="Current on-demand spend")
    daily_commitment_to_purchase: str | None = Field(
        default=None, description="Daily commitment to purchase"
    )
    estimated_monthly_savings_amount: str | None = Field(
        default=None, description="Estimated monthly savings amount"
    )
    estimated_on_demand_cost_with_current_commitment: str | None = Field(
        default=None, description="Estimated on-demand cost with current commitment"
    )
    estimated_roi: str | None = Field(default=None, description="Estimated ROI")
    estimated_savings_amount: str | None = Field(
        default=None, description="Estimated savings amount"
    )
    estimated_savings_percentage: str | None = Field(
        default=None, description="Estimated savings percentage"
    )
    estimated_total_cost: str | None = Field(default=None, description="Estimated total cost")
    hourly_commitment_to_purchase: str | None = Field(
        default=None, description="Hourly commitment to purchase"
    )
    total_recommendation_count: str | None = Field(
        default=None, description="Total recommendation count"
    )


# ===== 新增API模型 =====


class SavingsPlansUtilizationDetailsRequest(BaseRISPRequest):
    """Request model for GetSavingsPlansUtilizationDetails API."""

    time_period: DateRange = Field(description="Time period for analysis")
    data_type: list[str] | None = Field(
        default=None, description="Data types to include (ATTRIBUTES, UTILIZATION, COST_AND_USAGE)"
    )
    filter_expression: FilterExpression | None = Field(
        default=None, description="Filter conditions"
    )
    sort_by: list[SortDefinition] | None = Field(default=None, description="Sort definitions")
    max_results: int | None = Field(
        default=None, ge=1, le=100, description="Maximum number of results"
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v):
        if v is not None:
            from constants import ERROR_MESSAGES, VALID_SP_DATA_TYPES

            for data_type in v:
                if data_type not in VALID_SP_DATA_TYPES:
                    raise ValueError(ERROR_MESSAGES["INVALID_SP_DATA_TYPE"])
        return v


class SavingsPlansUtilizationDetailsResponse(BaseRISPResponse):
    """Response model for GetSavingsPlansUtilizationDetails API."""

    savings_plans_utilization_details: list[dict[str, Any]] = Field(
        default_factory=list, description="Detailed utilization data for each Savings Plan"
    )
    time_period: dict[str, str] = Field(
        default_factory=dict, description="Time period for the data"
    )
    total: dict[str, Any] | None = Field(
        default=None, description="Total utilization across all Savings Plans"
    )
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


class SavingsPlanPurchaseRecommendationDetailsRequest(BaseRISPRequest):
    """Request model for GetSavingsPlanPurchaseRecommendationDetails API."""

    recommendation_detail_id: str = Field(
        description="Unique identifier for the recommendation detail"
    )


class SavingsPlanPurchaseRecommendationDetailsResponse(BaseRISPResponse):
    """Response model for GetSavingsPlanPurchaseRecommendationDetails API."""

    recommendation_detail_id: str = Field(
        description="Unique identifier for the recommendation detail"
    )
    recommendation_detail_data: dict[str, Any] | None = Field(
        default=None, description="Detailed recommendation data"
    )
    account_scope: str | None = Field(
        default=None, description="Account scope for the recommendation"
    )
    savings_plans_type: str | None = Field(default=None, description="Type of Savings Plans")
    term_in_years: str | None = Field(default=None, description="Term length in years")
    payment_option: str | None = Field(default=None, description="Payment option")
    lookback_period_in_days: str | None = Field(default=None, description="Lookback period in days")


class ListSavingsPlansPurchaseRecommendationGenerationRequest(BaseRISPRequest):
    """Request model for ListSavingsPlansPurchaseRecommendationGeneration API."""

    generation_status: str | None = Field(
        default=None, description="Filter by generation status (SUCCEEDED, PROCESSING, FAILED)"
    )
    recommendation_ids: list[str] | None = Field(
        default=None, description="List of recommendation IDs to filter by"
    )
    page_size: int | None = Field(
        default=20, ge=1, le=100, description="Number of results per page"
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("generation_status")
    @classmethod
    def validate_generation_status(cls, v):
        if v is not None:
            from constants import ERROR_MESSAGES, VALID_ANALYSIS_STATUSES

            if v not in VALID_ANALYSIS_STATUSES:
                raise ValueError(ERROR_MESSAGES["INVALID_ANALYSIS_STATUS"])
        return v


class ListSavingsPlansPurchaseRecommendationGenerationResponse(BaseRISPResponse):
    """Response model for ListSavingsPlansPurchaseRecommendationGeneration API."""

    generation_summary_list: list[dict[str, Any]] = Field(
        default_factory=list, description="List of recommendation generation summaries"
    )
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


# ============================================================================
# Simplified Parameter Models for Handler Functions
# ============================================================================
# These models are used to simplify handler function signatures by
# encapsulating multiple parameters into a single Pydantic model.
# This provides automatic validation, better type hints, and cleaner code.


class SavingsPlansUtilizationParams(BaseModel):
    """Simplified parameters for Savings Plans utilization query."""

    time_period: DateRange = Field(description="Time period for analysis (start and end dates)")
    granularity: str | None = Field(
        default="MONTHLY", description="Data granularity (DAILY or MONTHLY)"
    )
    filter_expression: dict[str, Any] | None = Field(default=None, description="Filter conditions")
    sort_key: str | None = Field(default=None, description="Sort key for results")
    sort_order: str | None = Field(
        default="DESCENDING", description="Sort order (ASCENDING or DESCENDING)"
    )
    max_results: int | None = Field(
        default=None, description="Maximum number of results to return", ge=1, le=100
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, v):
        """Validate granularity and apply default if None."""
        # 如果传递了 null，使用默认值 MONTHLY
        if v is None:
            return "MONTHLY"
        if v not in ["DAILY", "MONTHLY"]:
            raise ValueError("granularity must be DAILY or MONTHLY")
        return v

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v):
        if v is not None and v not in ["ASCENDING", "DESCENDING"]:
            raise ValueError("sort_order must be ASCENDING or DESCENDING")
        return v


class SavingsPlansCoverageParams(BaseModel):
    """Simplified parameters for Savings Plans coverage query."""

    time_period: DateRange = Field(description="Time period for analysis (start and end dates)")
    granularity: str | None = Field(
        default="MONTHLY", description="Data granularity (DAILY or MONTHLY)"
    )
    group_by: list[str] | None = Field(
        default=None, description="List of dimensions to group by (e.g., SERVICE, INSTANCE_TYPE)"
    )
    filter_expression: dict[str, Any] | None = Field(default=None, description="Filter conditions")
    sort_key: str | None = Field(default=None, description="Sort key for results")
    sort_order: str | None = Field(
        default="DESCENDING", description="Sort order (ASCENDING or DESCENDING)"
    )
    max_results: int | None = Field(
        default=None, description="Maximum number of results to return", ge=1, le=100
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, v):
        """Validate granularity and apply default if None."""
        # 如果传递了 null，使用默认值 MONTHLY
        if v is None:
            return "MONTHLY"
        if v not in ["DAILY", "MONTHLY"]:
            raise ValueError("granularity must be DAILY or MONTHLY")
        return v

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v):
        if v is not None and v not in ["ASCENDING", "DESCENDING"]:
            raise ValueError("sort_order must be ASCENDING or DESCENDING")
        return v


class SavingsPlansPurchaseRecommendationParams(BaseModel):
    """Simplified parameters for Savings Plans purchase recommendation query."""

    savings_plans_type: str = Field(
        description="Type of Savings Plans (COMPUTE_SP, EC2_INSTANCE_SP, SAGEMAKER_SP)"
    )
    term_in_years: str = Field(description="Commitment term in years (ONE_YEAR or THREE_YEARS)")
    payment_option: str = Field(
        description="Payment option (NO_UPFRONT, PARTIAL_UPFRONT, ALL_UPFRONT)"
    )
    lookback_period_in_days: str = Field(
        description="Lookback period (SEVEN_DAYS, THIRTY_DAYS, SIXTY_DAYS)"
    )
    account_scope: str | None = Field(
        default="LINKED", description="Account scope (LINKED or PAYER)"
    )
    filter_expression: dict[str, Any] | None = Field(default=None, description="Filter conditions")
    page_size: int | None = Field(
        default=None, description="Maximum number of results per page", ge=1, le=100
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("savings_plans_type")
    @classmethod
    def validate_savings_plans_type(cls, v):
        if v not in VALID_SAVINGS_PLANS_TYPES:
            raise ValueError(f"savings_plans_type must be one of {VALID_SAVINGS_PLANS_TYPES}")
        return v

    @field_validator("term_in_years")
    @classmethod
    def validate_term_in_years(cls, v):
        if v not in VALID_TERM_IN_YEARS:
            raise ValueError(f"term_in_years must be one of {VALID_TERM_IN_YEARS}")
        return v

    @field_validator("payment_option")
    @classmethod
    def validate_payment_option(cls, v):
        if v not in VALID_PAYMENT_OPTIONS:
            raise ValueError(f"payment_option must be one of {VALID_PAYMENT_OPTIONS}")
        return v

    @field_validator("lookback_period_in_days")
    @classmethod
    def validate_lookback_period(cls, v):
        if v not in VALID_LOOKBACK_PERIODS:
            raise ValueError(f"lookback_period_in_days must be one of {VALID_LOOKBACK_PERIODS}")
        return v

    @field_validator("account_scope")
    @classmethod
    def validate_account_scope(cls, v):
        if v is not None and v not in VALID_ACCOUNT_SCOPES:
            raise ValueError(f"account_scope must be one of {VALID_ACCOUNT_SCOPES}")
        return v


# ============================================================================
# Savings Plans Utilization Details Parameters
# ============================================================================


class SavingsPlansUtilizationDetailsParams(BaseModel):
    """Simplified parameters for Savings Plans utilization details query."""

    time_period: DateRange = Field(description="Time period for analysis (start and end dates)")
    data_type: list[str] | None = Field(
        default=None,
        description="Data types to include (Valid: ATTRIBUTES, UTILIZATION, SAVINGS, AMORTIZED_COMMITMENT)",
    )
    filter_expression: dict[str, Any] | None = Field(
        default=None, description="Filter conditions (e.g., by account, SP ARN, SP type)"
    )
    sort_by: list[dict[str, Any]] | None = Field(
        default=None,
        description="Sort definitions (e.g., by utilization percentage, savings amount)",
    )
    max_results: int | None = Field(
        default=None, description="Maximum number of results to return", ge=1, le=1000
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v):
        if v is not None:
            valid_types = ["ATTRIBUTES", "UTILIZATION", "SAVINGS", "AMORTIZED_COMMITMENT"]
            for dt in v:
                if dt not in valid_types:
                    raise ValueError(f"data_type must contain only: {valid_types}")
        return v
