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

"""Parameter models for GCP Budget operations."""

from typing import Literal

from pydantic import BaseModel, Field


class CreateBudgetParams(BaseModel):
    """Simplified parameters for create budget operation."""

    billing_account_id: str = Field(
        description="GCP billing account ID (e.g., '012345-6789AB-CDEF01')"
    )
    display_name: str = Field(description="Display name for the budget")
    amount: float = Field(description="Budget amount", gt=0)
    currency_code: Literal["USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF", "INR"] = Field(
        default="USD", description="Currency code"
    )
    project_ids: list[str] | None = Field(
        default=None, description="List of GCP project IDs to apply budget to"
    )
    threshold_percents: list[float] | None = Field(
        default=None,
        description="List of threshold percentages for alerts (e.g., [50.0, 90.0, 100.0])",
    )
    account_id: str | None = Field(default=None, description="Optional GCP account ID")
