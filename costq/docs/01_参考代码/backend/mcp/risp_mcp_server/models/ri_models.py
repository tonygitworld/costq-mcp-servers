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

"""Reserved Instance data models for RISP MCP Server.

This module contains data models specific to Reserved Instance operations.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..constants import (
    VALID_ACCOUNT_SCOPES,
    VALID_LOOKBACK_PERIODS,
    VALID_PAYMENT_OPTIONS,
    VALID_RI_SERVICES,
    VALID_RI_SORT_KEYS,
    VALID_TERM_IN_YEARS,
)
from .common_models import (
    BaseRISPRequest,
    BaseRISPResponse,
    DateRange,
    GroupDefinition,
    PaginationRequest,
    SortDefinition,
)


class ReservationUtilizationRequest(BaseRISPRequest):
    """Request model for RI utilization analysis."""

    group_by: list[GroupDefinition] | None = Field(
        default=None, description="Group by dimensions (only SUBSCRIPTION_ID supported)"
    )
    sort_by: SortDefinition | None = Field(default=None, description="Sort definition for results")
    pagination: PaginationRequest | None = Field(default=None, description="Pagination settings")

    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, v):
        """Validate group by definitions."""
        if v is not None:
            for group in v:
                if group.Type == "DIMENSION" and group.Key != "SUBSCRIPTION_ID":
                    raise ValueError(
                        "For RI utilization, only SUBSCRIPTION_ID dimension grouping is supported"
                    )
        return v

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v):
        """Validate sort definition."""
        if v is not None and v.Key not in VALID_RI_SORT_KEYS:
            raise ValueError(f"Invalid sort key '{v.Key}'. Valid keys: {VALID_RI_SORT_KEYS}")
        return v


class ReservationCoverageRequest(BaseRISPRequest):
    """Request model for RI coverage analysis."""

    group_by: list[GroupDefinition] | None = Field(default=None, description="Group by dimensions")
    sort_by: SortDefinition | None = Field(default=None, description="Sort definition for results")
    pagination: PaginationRequest | None = Field(default=None, description="Pagination settings")

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v):
        """Validate sort definition."""
        if v is not None and v.Key not in VALID_RI_SORT_KEYS:
            raise ValueError(f"Invalid sort key '{v.Key}'. Valid keys: {VALID_RI_SORT_KEYS}")
        return v


class ReservationPurchaseRecommendationRequest(BaseModel):
    """Request model for RI purchase recommendations."""

    service: str = Field(description="AWS service for recommendations")
    account_scope: str | None = Field(default="PAYER", description="Account scope (PAYER, LINKED)")
    lookback_period_in_days: str | None = Field(
        default="SEVEN_DAYS", description="Lookback period for analysis"
    )
    term_in_years: str | None = Field(default="ONE_YEAR", description="RI term length")
    payment_option: str | None = Field(default="NO_UPFRONT", description="Payment option")
    service_specification: dict[str, Any] | None = Field(
        default=None, description="Service-specific configuration"
    )
    pagination: PaginationRequest | None = Field(default=None, description="Pagination settings")

    @field_validator("service")
    @classmethod
    def validate_service(cls, v):
        """Validate RI service."""
        if v not in VALID_RI_SERVICES:
            raise ValueError(f"Invalid RI service '{v}'. Valid services: {VALID_RI_SERVICES}")
        return v

    @field_validator("account_scope")
    @classmethod
    def validate_account_scope(cls, v):
        """Validate account scope."""
        if v not in VALID_ACCOUNT_SCOPES:
            raise ValueError(f"Invalid account scope '{v}'. Valid scopes: {VALID_ACCOUNT_SCOPES}")
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


class ReservationUtilizationResponse(BaseRISPResponse):
    """Response model for RI utilization analysis."""

    utilization_summary: dict[str, Any] | None = Field(
        default=None, description="Formatted utilization summary"
    )
    utilizations_by_time: list[dict[str, Any]] | None = Field(
        default=None, description="Time-series utilization data"
    )
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


class ReservationCoverageResponse(BaseRISPResponse):
    """Response model for RI coverage analysis."""

    coverage_summary: dict[str, Any] | None = Field(
        default=None, description="Formatted coverage summary"
    )
    coverages_by_time: list[dict[str, Any]] | None = Field(
        default=None, description="Time-series coverage data"
    )
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


class ReservationPurchaseRecommendationResponse(BaseRISPResponse):
    """Response model for RI purchase recommendations."""

    recommendation_summary: dict[str, Any] | None = Field(
        default=None, description="Formatted recommendation summary"
    )
    recommendations: list[dict[str, Any]] | None = Field(
        default=None, description="List of purchase recommendations"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="Recommendation metadata")
    next_page_token: str | None = Field(default=None, description="Token for next page of results")


class ReservationDetails(BaseModel):
    """Model for reservation details."""

    subscription_id: str = Field(description="Reservation subscription ID")
    instance_type: str | None = Field(default=None, description="Instance type")
    availability_zone: str | None = Field(default=None, description="Availability zone")
    platform: str | None = Field(default=None, description="Platform")
    region: str | None = Field(default=None, description="AWS region")
    scope: str | None = Field(default=None, description="Reservation scope")
    tenancy: str | None = Field(default=None, description="Tenancy")
    offering_type: str | None = Field(default=None, description="Offering type")
    start_date: str | None = Field(default=None, description="Reservation start date")
    end_date: str | None = Field(default=None, description="Reservation end date")
    number_of_instances: str | None = Field(default=None, description="Number of instances")


class ReservationUtilizationGroup(BaseModel):
    """Model for RI utilization group data."""

    key: str = Field(description="Group key")
    value: str = Field(description="Group value")
    attributes: dict[str, str] | None = Field(default=None, description="Group attributes")
    utilization: dict[str, Any] | None = Field(default=None, description="Utilization metrics")


class ReservationCoverageGroup(BaseModel):
    """Model for RI coverage group data."""

    key: str = Field(description="Group key")
    value: str = Field(description="Group value")
    attributes: dict[str, str] | None = Field(default=None, description="Group attributes")
    coverage: dict[str, Any] | None = Field(default=None, description="Coverage metrics")


class ReservationPurchaseRecommendationDetail(BaseModel):
    """Model for RI purchase recommendation detail."""

    account_id: str | None = Field(default=None, description="AWS account ID")
    instance_details: dict[str, Any] | None = Field(default=None, description="Instance details")
    recommended_number_of_instances_to_purchase: str | None = Field(
        default=None, description="Recommended number of instances"
    )
    minimum_number_of_instances_used_per_hour: str | None = Field(
        default=None, description="Minimum instances used per hour"
    )
    maximum_number_of_instances_used_per_hour: str | None = Field(
        default=None, description="Maximum instances used per hour"
    )
    average_number_of_instances_used_per_hour: str | None = Field(
        default=None, description="Average instances used per hour"
    )
    estimated_monthly_savings_amount: str | None = Field(
        default=None, description="Estimated monthly savings"
    )
    estimated_monthly_savings_percentage: str | None = Field(
        default=None, description="Estimated monthly savings percentage"
    )
    estimated_monthly_on_demand_cost: str | None = Field(
        default=None, description="Estimated monthly on-demand cost"
    )
    estimated_reservation_cost_for_lookback_period: str | None = Field(
        default=None, description="Estimated reservation cost"
    )
    upfront_cost: str | None = Field(default=None, description="Upfront cost")
    recurring_standard_monthly_cost: str | None = Field(
        default=None, description="Recurring monthly cost"
    )
    currency_code: str | None = Field(default=None, description="Currency code")


# ============================================================================
# Simplified Parameter Models for Handler Functions
# ============================================================================
# These models are designed to match the current handler function signatures
# and provide a simpler interface compared to the complex Request models above.
# They use flat parameter structures instead of nested objects.
# ============================================================================


class ReservationUtilizationParams(BaseModel):
    """Simplified parameters for RI utilization query.

    This model provides a flat parameter structure that matches the current
    handler function signature, making it easier to use with MCP tools.
    """

    time_period: DateRange = Field(description="Time period for analysis (start and end dates)")
    granularity: str | None = Field(
        default="MONTHLY", description="Data granularity (DAILY or MONTHLY)"
    )
    group_by_subscription_id: bool | None = Field(
        default=False, description="Whether to group results by subscription ID"
    )
    filter_expression: dict[str, Any] | None = Field(
        default=None, description="Filter conditions (e.g., by service, instance type, region)"
    )
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
        """Validate sort order."""
        if v is not None and v not in ["ASCENDING", "DESCENDING"]:
            raise ValueError("sort_order must be ASCENDING or DESCENDING")
        return v

    @field_validator("sort_key")
    @classmethod
    def validate_sort_key(cls, v):
        """Validate sort key."""
        if v is not None and v not in VALID_RI_SORT_KEYS:
            raise ValueError(f"Invalid sort key '{v}'. Valid keys: {VALID_RI_SORT_KEYS}")
        return v


class ReservationCoverageParams(BaseModel):
    """Simplified parameters for RI coverage query.

    This model provides a flat parameter structure that matches the current
    handler function signature, making it easier to use with MCP tools.
    """

    time_period: DateRange = Field(description="Time period for analysis (start and end dates)")
    granularity: str | None = Field(
        default="MONTHLY", description="Data granularity (DAILY or MONTHLY)"
    )
    group_by: list[str] | None = Field(
        default=None,
        description="List of dimensions to group by (e.g., ['INSTANCE_TYPE', 'REGION'])",
    )
    filter_expression: dict[str, Any] | None = Field(
        default=None, description="Filter conditions (e.g., by service, instance type, region)"
    )
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
        """Validate sort order."""
        if v is not None and v not in ["ASCENDING", "DESCENDING"]:
            raise ValueError("sort_order must be ASCENDING or DESCENDING")
        return v

    @field_validator("sort_key")
    @classmethod
    def validate_sort_key(cls, v):
        """Validate sort key."""
        if v is not None and v not in VALID_RI_SORT_KEYS:
            raise ValueError(f"Invalid sort key '{v}'. Valid keys: {VALID_RI_SORT_KEYS}")
        return v


class ReservationPurchaseRecommendationParams(BaseModel):
    """Simplified parameters for RI purchase recommendation query.

    This model provides a flat parameter structure that matches the current
    handler function signature, making it easier to use with MCP tools.
    """

    service: str = Field(
        description="AWS service for recommendations (e.g., 'Amazon Elastic Compute Cloud - Compute', 'Amazon Relational Database Service')"
    )
    account_scope: str | None = Field(
        default="LINKED",
        description="Account scope: LINKED (per-account recommendations) or PAYER (organization-wide recommendations)",
    )
    lookback_period_in_days: str | None = Field(
        default="THIRTY_DAYS", description="Lookback period: SEVEN_DAYS, THIRTY_DAYS, or SIXTY_DAYS"
    )
    term_in_years: str | None = Field(
        default="ONE_YEAR", description="RI term length: ONE_YEAR or THREE_YEARS"
    )
    payment_option: str | None = Field(
        default="NO_UPFRONT",
        description="Payment option: NO_UPFRONT, PARTIAL_UPFRONT, or ALL_UPFRONT",
    )
    service_specification: dict[str, Any] | None = Field(
        default=None,
        description="Service-specific parameters (e.g., EC2 instance type, RDS database engine)",
    )
    page_size: int | None = Field(
        default=None, description="Maximum number of results per page", ge=1, le=100
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("service")
    @classmethod
    def validate_service(cls, v):
        """Validate service name."""
        if v not in VALID_RI_SERVICES:
            raise ValueError(f"Invalid service '{v}'. Valid services: {VALID_RI_SERVICES}")
        return v

    @field_validator("account_scope")
    @classmethod
    def validate_account_scope(cls, v):
        """Validate account scope."""
        if v is not None and v not in VALID_ACCOUNT_SCOPES:
            raise ValueError(f"Invalid account_scope '{v}'. Valid values: {VALID_ACCOUNT_SCOPES}")
        return v

    @field_validator("lookback_period_in_days")
    @classmethod
    def validate_lookback_period(cls, v):
        """Validate lookback period."""
        if v is not None and v not in VALID_LOOKBACK_PERIODS:
            raise ValueError(
                f"Invalid lookback_period_in_days '{v}'. Valid values: {VALID_LOOKBACK_PERIODS}"
            )
        return v

    @field_validator("term_in_years")
    @classmethod
    def validate_term(cls, v):
        """Validate term."""
        if v is not None and v not in VALID_TERM_IN_YEARS:
            raise ValueError(f"Invalid term_in_years '{v}'. Valid values: {VALID_TERM_IN_YEARS}")
        return v

    @field_validator("payment_option")
    @classmethod
    def validate_payment_option(cls, v):
        """Validate payment option."""
        if v is not None and v not in VALID_PAYMENT_OPTIONS:
            raise ValueError(f"Invalid payment_option '{v}'. Valid values: {VALID_PAYMENT_OPTIONS}")
        return v
