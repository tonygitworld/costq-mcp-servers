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

"""Parameter models for GCP CUD (Committed Use Discount) operations."""

from typing import Literal

from pydantic import BaseModel, Field


class ListCommitmentsParams(BaseModel):
    """Simplified parameters for list commitments query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    region: str | None = Field(
        default=None, description="GCP region to filter by (e.g., 'us-central1')"
    )
    status_filter: Literal["ACTIVE", "EXPIRED", "CREATING", "CANCELLED"] | None = Field(
        default=None, description="Status filter"
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class CudUtilizationParams(BaseModel):
    """Simplified parameters for CUD utilization query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    start_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date for utilization analysis (YYYY-MM-DD format)",
    )
    end_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date for utilization analysis (YYYY-MM-DD format)",
    )
    granularity: Literal["DAILY", "MONTHLY"] = Field(
        default="DAILY", description="Time granularity"
    )
    region: str | None = Field(default=None, description="GCP region to filter by")
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class CudCoverageParams(BaseModel):
    """Simplified parameters for CUD coverage query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    start_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date for coverage analysis (YYYY-MM-DD format)",
    )
    end_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date for coverage analysis (YYYY-MM-DD format)",
    )
    granularity: Literal["DAILY", "MONTHLY"] = Field(
        default="DAILY", description="Time granularity"
    )
    service_filter: str = Field(default="Compute Engine", description="Service name to filter by")
    region: str | None = Field(default=None, description="GCP region to filter by")
    account_id: str | None = Field(default=None, description="Optional GCP account ID")


class CudSavingsAnalysisParams(BaseModel):
    """Simplified parameters for CUD savings analysis query."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    billing_account_id: str | None = Field(default=None, description="GCP billing account ID")
    start_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date for savings analysis (YYYY-MM-DD format)",
    )
    end_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date for savings analysis (YYYY-MM-DD format)",
    )
    granularity: Literal["DAILY", "MONTHLY"] = Field(
        default="MONTHLY", description="Time granularity"
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")
