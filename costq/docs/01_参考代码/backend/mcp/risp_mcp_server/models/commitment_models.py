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

"""Commitment Purchase Analysis models for RISP MCP Server.

This module contains Pydantic models for Commitment Purchase Analysis operations
including analysis configuration, requests, and responses.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .common_models import BaseRISPRequest, BaseRISPResponse


class CommitmentPurchaseAnalysisConfiguration(BaseModel):
    """Configuration for commitment purchase analysis."""

    account_scope: str | None = Field(default="PAYER", description="Account scope (PAYER, LINKED)")
    account_id: str | None = Field(default=None, description="Specific account ID for LINKED scope")
    analysis_type: str = Field(description="Type of analysis (MAX_SAVINGS, CUSTOM_COMMITMENT)")
    savings_plans_to_add: list[dict[str, Any]] | None = Field(
        default=None, description="Savings Plans to add to the analysis"
    )
    savings_plans_to_exclude: list[str] | None = Field(
        default=None, description="Savings Plans ARNs to exclude from analysis"
    )

    @field_validator("account_scope")
    @classmethod
    def validate_account_scope(cls, v):
        from ..constants import ERROR_MESSAGES, VALID_ACCOUNT_SCOPES

        if v not in VALID_ACCOUNT_SCOPES:
            raise ValueError(ERROR_MESSAGES["INVALID_ACCOUNT_SCOPE"])
        return v

    @field_validator("analysis_type")
    @classmethod
    def validate_analysis_type(cls, v):
        from ..constants import ERROR_MESSAGES, VALID_ANALYSIS_TYPES

        if v not in VALID_ANALYSIS_TYPES:
            raise ValueError(ERROR_MESSAGES["INVALID_ANALYSIS_TYPE"])
        return v


class StartCommitmentPurchaseAnalysisRequest(BaseRISPRequest):
    """Request model for StartCommitmentPurchaseAnalysis API."""

    commitment_purchase_analysis_configuration: CommitmentPurchaseAnalysisConfiguration = Field(
        description="Configuration for the commitment purchase analysis"
    )


class StartCommitmentPurchaseAnalysisResponse(BaseRISPResponse):
    """Response model for StartCommitmentPurchaseAnalysis API."""

    analysis_id: str = Field(description="Unique identifier for the analysis")
    analysis_started_time: str = Field(description="Timestamp when the analysis was started")
    estimated_completion_time: str | None = Field(
        default=None, description="Estimated completion time for the analysis"
    )


class GetCommitmentPurchaseAnalysisRequest(BaseRISPRequest):
    """Request model for GetCommitmentPurchaseAnalysis API."""

    analysis_id: str = Field(description="Unique identifier for the analysis")


class CommitmentPurchaseAnalysisResult(BaseModel):
    """Model for commitment purchase analysis result."""

    commitment_purchase_analysis_id: str = Field(description="Analysis ID")
    commitment_purchase_analysis_status: str = Field(
        description="Analysis status (SUCCEEDED, PROCESSING, FAILED)"
    )
    analysis_started_time: str = Field(description="Analysis start time")
    analysis_completion_time: str | None = Field(
        default=None, description="Analysis completion time"
    )
    estimated_monthly_savings: str | None = Field(
        default=None, description="Estimated monthly savings"
    )
    estimated_on_demand_cost: str | None = Field(
        default=None, description="Estimated on-demand cost"
    )
    recommended_commitment_purchases: list[dict[str, Any]] | None = Field(
        default=None, description="Recommended commitment purchases"
    )
    error_message: str | None = Field(default=None, description="Error message if analysis failed")


class GetCommitmentPurchaseAnalysisResponse(BaseRISPResponse):
    """Response model for GetCommitmentPurchaseAnalysis API."""

    commitment_purchase_analysis_result: CommitmentPurchaseAnalysisResult = Field(
        description="Analysis result data"
    )


class ListCommitmentPurchaseAnalysesRequest(BaseRISPRequest):
    """Request model for ListCommitmentPurchaseAnalyses API."""

    analysis_status: str | None = Field(
        default=None, description="Filter by analysis status (SUCCEEDED, PROCESSING, FAILED)"
    )
    analysis_ids: list[str] | None = Field(
        default=None, description="List of analysis IDs to filter by"
    )
    page_size: int | None = Field(
        default=20, ge=1, le=100, description="Number of results per page"
    )
    next_page_token: str | None = Field(default=None, description="Token for pagination")

    @field_validator("analysis_status")
    @classmethod
    def validate_analysis_status(cls, v):
        if v is not None:
            from ..constants import ERROR_MESSAGES, VALID_ANALYSIS_STATUSES

            if v not in VALID_ANALYSIS_STATUSES:
                raise ValueError(ERROR_MESSAGES["INVALID_ANALYSIS_STATUS"])
        return v


class CommitmentPurchaseAnalysisSummary(BaseModel):
    """Model for commitment purchase analysis summary."""

    commitment_purchase_analysis_id: str = Field(description="Analysis ID")
    commitment_purchase_analysis_status: str = Field(description="Analysis status")
    analysis_started_time: str = Field(description="Analysis start time")
    analysis_completion_time: str | None = Field(
        default=None, description="Analysis completion time"
    )
    estimated_monthly_savings: str | None = Field(
        default=None, description="Estimated monthly savings"
    )


class ListCommitmentPurchaseAnalysesResponse(BaseRISPResponse):
    """Response model for ListCommitmentPurchaseAnalyses API."""

    commitment_purchase_analysis_summaries: list[CommitmentPurchaseAnalysisSummary] = Field(
        default_factory=list, description="List of analysis summaries"
    )
    next_page_token: str | None = Field(default=None, description="Token for next page of results")
