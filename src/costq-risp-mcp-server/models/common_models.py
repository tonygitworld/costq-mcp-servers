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

"""Common data models for RISP MCP Server.

This module contains shared data models used across RI and SP operations.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from utils.validators import validate_date_format, validate_date_range


class DateRange(BaseModel):
    """Date range model for RISP queries.

    This model replicates the DateRange from the upstream Cost Explorer MCP Server
    to ensure consistency across the ecosystem.
    """

    start_date: str = Field(
        description="The start date of the billing period in YYYY-MM-DD format. Defaults to last month, if not provided."
    )
    end_date: str = Field(description="The end date of the billing period in YYYY-MM-DD format.")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_individual_dates(cls, v):
        """Validate that individual dates are in YYYY-MM-DD format and are valid dates."""
        is_valid, error = validate_date_format(v)
        if not is_valid:
            raise ValueError(error)
        return v

    def model_post_init(self, __context):
        """Validate the date range after both dates are set."""
        is_valid, error = validate_date_range(self.start_date, self.end_date)
        if not is_valid:
            raise ValueError(error)

    def validate_with_granularity(self, granularity: str):
        """Validate the date range with granularity-specific constraints."""
        is_valid, error = validate_date_range(self.start_date, self.end_date, granularity)
        if not is_valid:
            raise ValueError(error)


class FilterExpression(BaseModel):
    """Filter expression model for AWS Cost Explorer API calls."""

    And: list["FilterExpression"] | None = Field(
        default=None, description="AND logic for multiple filters"
    )
    Or: list["FilterExpression"] | None = Field(
        default=None, description="OR logic for multiple filters"
    )
    Not: Optional["FilterExpression"] = Field(
        default=None, description="NOT logic for filter negation"
    )
    Dimensions: dict[str, Any] | None = Field(default=None, description="Dimension-based filters")
    Tags: dict[str, Any] | None = Field(default=None, description="Tag-based filters")
    CostCategories: dict[str, Any] | None = Field(
        default=None, description="Cost category-based filters"
    )


class GroupDefinition(BaseModel):
    """Group definition model for AWS Cost Explorer API calls."""

    Type: str = Field(description="Group type (DIMENSION, TAG, COST_CATEGORY)")
    Key: str = Field(description="Group key")

    @field_validator("Type")
    @classmethod
    def validate_group_type(cls, v):
        """Validate group type."""
        valid_types = ["DIMENSION", "TAG", "COST_CATEGORY"]
        if v not in valid_types:
            raise ValueError(f"Invalid group type '{v}'. Valid types: {valid_types}")
        return v


class SortDefinition(BaseModel):
    """Sort definition model for AWS Cost Explorer API calls."""

    Key: str = Field(description="Sort key")
    SortOrder: str | None = Field(
        default="DESCENDING", description="Sort order (ASCENDING, DESCENDING)"
    )

    @field_validator("SortOrder")
    @classmethod
    def validate_sort_order(cls, v):
        """Validate sort order."""
        if v is None:
            return "DESCENDING"
        valid_orders = ["ASCENDING", "DESCENDING"]
        if v not in valid_orders:
            raise ValueError(f"Invalid sort order '{v}'. Valid orders: {valid_orders}")
        return v


class PaginationRequest(BaseModel):
    """Pagination request model for AWS Cost Explorer API calls."""

    MaxResults: int | None = Field(default=None, description="Maximum number of results to return")
    NextPageToken: str | None = Field(default=None, description="Token for next page of results")

    @field_validator("MaxResults")
    @classmethod
    def validate_max_results(cls, v):
        """Validate max results."""
        if v is not None and (v < 1 or v > 100):
            raise ValueError("MaxResults must be between 1 and 100")
        return v


class BaseRISPRequest(BaseModel):
    """Base request model for RISP operations."""

    time_period: DateRange = Field(description="Time period for the analysis")
    granularity: str | None = Field(
        default="MONTHLY", description="Data granularity (DAILY, MONTHLY)"
    )
    filter_expression: FilterExpression | None = Field(
        default=None, description="Filter conditions"
    )

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, v):
        """Validate granularity."""
        if v is None:
            return "MONTHLY"
        valid_granularities = ["DAILY", "MONTHLY"]
        if v not in valid_granularities:
            raise ValueError(f"Invalid granularity '{v}'. Valid values: {valid_granularities}")
        return v

    def model_post_init(self, __context):
        """Validate the request after all fields are set."""
        # Validate date range with granularity
        if self.granularity:
            self.time_period.validate_with_granularity(self.granularity)


class BaseRISPResponse(BaseModel):
    """Base response model for RISP operations."""

    success: bool = Field(description="Whether the operation was successful")
    operation: str = Field(description="The operation that was performed")
    timestamp: str = Field(description="Timestamp of the response")
    data: dict[str, Any] | None = Field(default=None, description="Raw response data")
    summary: dict[str, Any] | None = Field(default=None, description="Formatted summary data")
    error: str | None = Field(default=None, description="Error message if operation failed")
    message: str | None = Field(default=None, description="Additional message")

    @classmethod
    def success_response(
        cls, operation: str, data: dict[str, Any], summary: dict[str, Any] | None = None
    ):
        """Create a success response."""
        return cls(
            success=True,
            operation=operation,
            timestamp=datetime.utcnow().isoformat(),
            data=data,
            summary=summary,
        )

    @classmethod
    def error_response(cls, operation: str, error: str, message: str | None = None):
        """Create an error response."""
        return cls(
            success=False,
            operation=operation,
            timestamp=datetime.utcnow().isoformat(),
            error=error,
            message=message or f"{operation} failed: {error}",
        )


class MetricValue(BaseModel):
    """Model for metric values with formatting."""

    raw_value: str = Field(description="Raw value from AWS API")
    formatted_value: str = Field(description="Formatted value for display")
    unit: str | None = Field(default=None, description="Unit of measurement")


class UtilizationMetrics(BaseModel):
    """Common utilization metrics model."""

    utilization_percentage: MetricValue = Field(description="Utilization percentage")
    total_hours: MetricValue | None = Field(default=None, description="Total hours")
    used_hours: MetricValue | None = Field(default=None, description="Used hours")
    unused_hours: MetricValue | None = Field(default=None, description="Unused hours")


class CoverageMetrics(BaseModel):
    """Common coverage metrics model."""

    coverage_percentage: MetricValue = Field(description="Coverage percentage")
    total_cost: MetricValue | None = Field(default=None, description="Total cost")
    covered_cost: MetricValue | None = Field(default=None, description="Covered cost")
    uncovered_cost: MetricValue | None = Field(default=None, description="Uncovered cost")


class SavingsMetrics(BaseModel):
    """Common savings metrics model."""

    net_savings: MetricValue = Field(description="Net savings amount")
    savings_percentage: MetricValue | None = Field(default=None, description="Savings percentage")
    potential_savings: MetricValue | None = Field(default=None, description="Potential savings")


# Enable forward references for recursive models
FilterExpression.model_rebuild()
