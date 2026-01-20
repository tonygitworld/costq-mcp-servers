"""
Recommender Data Models

Pydantic models for cost optimization recommendations.
"""

from pydantic import BaseModel, Field


class CostImpact(BaseModel):
    """Cost impact of recommendation"""

    currency_code: str = "USD"
    monthly_savings: float = Field(..., description="Estimated monthly savings")
    annual_savings: float | None = None


class Recommendation(BaseModel):
    """Cost optimization recommendation"""

    recommendation_id: str
    recommender_type: str
    description: str
    state: str = Field(..., description="ACTIVE, CLAIMED, SUCCEEDED, FAILED, DISMISSED")
    priority: str | None = None
    cost_impact: CostImpact | None = None
    target_resources: list[str] = Field(default_factory=list)
    last_refresh_time: str | None = None


class RecommendationListResponse(BaseModel):
    """Response for list recommendations"""

    success: bool
    recommendations: list[Recommendation]
    total_count: int
    total_potential_savings: float
    currency: str = "USD"
    account_id: str | None = None
    project_id: str | None = None
    recommender_type: str | None = None
    message: str | None = None


class RecommendationSummary(BaseModel):
    """Summary of recommendations by type"""

    recommender_type: str
    count: int
    total_savings: float
    currency: str = "USD"


class AllRecommendationsResponse(BaseModel):
    """Response for all recommendations across types"""

    success: bool
    by_type: list[RecommendationSummary]
    total_recommendations: int
    total_potential_savings: float
    currency: str = "USD"
    account_id: str | None = None
    project_id: str | None = None
    message: str | None = None


# ============================================================================
# Parameter Models for Handler Functions
# ============================================================================


class VmRightsizingRecommendationsParams(BaseModel):
    """Simplified parameters for VM rightsizing recommendations query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    location: str = Field(
        default="-", description="GCP location/region (use '-' for all locations)"
    )
    max_results: int | None = Field(
        default=None, description="Maximum number of results to return", ge=1, le=1000
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class IdleResourcesParams(BaseModel):
    """Simplified parameters for idle resources query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    resource_types: list[str] | None = Field(
        default=None, description="List of resource types to check (e.g., ['VM', 'DISK', 'IP'])"
    )
    location: str = Field(
        default="-", description="GCP location/region (use '-' for all locations)"
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class CommitmentRecommendationsParams(BaseModel):
    """Simplified parameters for commitment (CUD) purchase recommendations query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    location: str = Field(
        default="-", description="GCP location/region (use '-' for all locations)"
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class AllRecommendationsParams(BaseModel):
    """Simplified parameters for all recommendations query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    location: str = Field(
        default="-", description="GCP location/region (use '-' for all locations)"
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class MarkRecommendationStatusParams(BaseModel):
    """Simplified parameters for marking recommendation status."""

    recommendation_name: str = Field(
        description="Full recommendation name (e.g., 'projects/123/locations/us-central1/recommenders/google.compute.instance.MachineTypeRecommender/recommendations/456')"
    )
    state: str = Field(description="New state (CLAIMED, SUCCEEDED, FAILED, DISMISSED)")
    state_metadata: dict[str, str] | None = Field(
        default=None, description="Optional metadata for the state change"
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")
