"""
Billing Data Models

Pydantic models for billing cost data requests and responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class CostItem(BaseModel):
    """Individual cost item"""

    name: str = Field(..., description="Service, project, SKU, or label name")
    total_cost: float = Field(..., description="Total cost before credits")
    total_credits: float = Field(default=0.0, description="Total credits/discounts")
    net_cost: float = Field(..., description="Net cost after credits")
    currency: str = Field(default="USD", description="Currency code")

    # Optional metadata
    project_count: int | None = Field(None, description="Number of projects")
    service_count: int | None = Field(None, description="Number of services")


class DailyCostItem(BaseModel):
    """Daily cost data point"""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    daily_cost: float
    daily_credits: float = 0.0
    daily_net_cost: float
    currency: str = "USD"
    services_used: int | None = None
    projects_count: int | None = None


class CostSummary(BaseModel):
    """Cost summary statistics"""

    total_cost: float
    total_credits: float
    net_cost: float
    currency: str
    services_count: int
    projects_count: int
    days_count: int
    start_date: str
    end_date: str
    average_daily_cost: float | None = None


class CostByServiceResponse(BaseModel):
    """Response for cost by service query"""

    success: bool
    items: list[CostItem]
    summary: CostSummary
    account_id: str | None = None
    message: str | None = None


class CostByProjectResponse(BaseModel):
    """Response for cost by project query"""

    success: bool
    items: list[CostItem]
    summary: CostSummary
    account_id: str | None = None
    service_filter: str | None = None
    message: str | None = None


class DailyCostTrendResponse(BaseModel):
    """Response for daily cost trend query"""

    success: bool
    items: list[DailyCostItem]
    summary: CostSummary
    account_id: str | None = None
    message: str | None = None


class CostByLabelResponse(BaseModel):
    """Response for cost by label query (cost allocation)"""

    success: bool
    label_key: str
    items: list[CostItem]
    summary: CostSummary
    account_id: str | None = None
    message: str | None = None


class SKUCostItem(BaseModel):
    """SKU-level cost item"""

    service_name: str
    sku_description: str
    total_cost: float
    total_usage_amount: float
    usage_unit: str
    currency: str = "USD"
    project_count: int | None = None


class CostBySKUResponse(BaseModel):
    """Response for cost by SKU query"""

    success: bool
    items: list[SKUCostItem]
    account_id: str | None = None
    service_filter: str | None = None
    message: str | None = None


class CostAnomalyItem(BaseModel):
    """Cost anomaly data point"""

    date: str
    actual_cost: float
    expected_cost: float
    deviation: float
    z_score: float
    severity: str = Field(..., description="HIGH, MEDIUM, or LOW")
    currency: str = "USD"


class CostAnomalyResponse(BaseModel):
    """Response for cost anomaly detection"""

    success: bool
    anomalies_detected: int
    anomalies: list[CostAnomalyItem]
    summary: dict[str, Any]
    account_id: str | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response"""

    success: bool = False
    error_message: str
    error_code: str | None = None
    help_url: str | None = None
    setup_guide: str | None = None


# ============================================================================
# Parameter Models for Handler Functions
# ============================================================================


class CostByServiceParams(BaseModel):
    """Simplified parameters for cost by service query."""

    start_date: str | None = Field(
        default=None, description="Start date for cost analysis (YYYY-MM-DD format)"
    )
    end_date: str | None = Field(
        default=None, description="End date for cost analysis (YYYY-MM-DD format)"
    )
    project_ids: list[str] | None = Field(
        default=None, description="List of GCP project IDs to filter by"
    )
    billing_account_id: str | None = Field(
        default=None, description="GCP billing account ID (e.g., '012345-6789AB-CDEF01')"
    )
    limit: int = Field(
        default=100, description="Maximum number of results to return", ge=1, le=1000
    )
    account_id: str | None = Field(
        default=None, description="Optional GCP account ID for multi-account scenarios"
    )


class CostByProjectParams(BaseModel):
    """Simplified parameters for cost by project query."""

    start_date: str | None = Field(
        default=None, description="Start date for cost analysis (YYYY-MM-DD format)"
    )
    end_date: str | None = Field(
        default=None, description="End date for cost analysis (YYYY-MM-DD format)"
    )
    service_filter: str | None = Field(
        default=None, description="Service name to filter by (e.g., 'Compute Engine')"
    )
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    limit: int = Field(
        default=100, description="Maximum number of results to return", ge=1, le=1000
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class DailyCostTrendParams(BaseModel):
    """Simplified parameters for daily cost trend query."""

    start_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date for trend analysis (YYYY-MM-DD format)",
    )
    end_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date for trend analysis (YYYY-MM-DD format)",
    )
    project_ids: list[str] | None = Field(
        default=None, description="List of GCP project IDs to filter by"
    )
    service_filter: str | None = Field(default=None, description="Service name to filter by")
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class CostByLabelParams(BaseModel):
    """Simplified parameters for cost by label query."""

    label_key: str = Field(description="Label key to group costs by (e.g., 'environment', 'team')")
    start_date: str | None = Field(
        default=None, description="Start date for cost analysis (YYYY-MM-DD format)"
    )
    end_date: str | None = Field(
        default=None, description="End date for cost analysis (YYYY-MM-DD format)"
    )
    project_ids: list[str] | None = Field(
        default=None, description="List of GCP project IDs to filter by"
    )
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    limit: int = Field(
        default=100, description="Maximum number of results to return", ge=1, le=1000
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class CostBySkuParams(BaseModel):
    """Simplified parameters for cost by SKU query."""

    start_date: str | None = Field(
        default=None, description="Start date for cost analysis (YYYY-MM-DD format)"
    )
    end_date: str | None = Field(
        default=None, description="End date for cost analysis (YYYY-MM-DD format)"
    )
    service_filter: str | None = Field(default=None, description="Service name to filter by")
    project_ids: list[str] | None = Field(
        default=None, description="List of GCP project IDs to filter by"
    )
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    limit: int = Field(default=50, description="Maximum number of results to return", ge=1, le=1000)
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class CostSummaryParams(BaseModel):
    """Simplified parameters for cost summary query."""

    start_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date for summary (YYYY-MM-DD format)",
    )
    end_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date for summary (YYYY-MM-DD format)",
    )
    project_ids: list[str] | None = Field(
        default=None, description="List of GCP project IDs to filter by"
    )
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    account_id: str | None = Field(default=None, description="Optional GCP account ID")
