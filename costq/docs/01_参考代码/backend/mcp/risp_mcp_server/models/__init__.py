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

"""RISP MCP Server models module.

This module contains all the data models for Reserved Instance and Savings Plans operations.
"""

# Common models
from .common_models import (
    DateRange,
    FilterExpression,
    GroupDefinition,
    PaginationRequest,
    SortDefinition,
)

# RI models - Simplified parameter models for handler functions
# RI models - Request/Response models (for future use)
from .ri_models import (
    ReservationCoverageParams,
    ReservationCoverageRequest,
    ReservationCoverageResponse,
    ReservationPurchaseRecommendationParams,
    ReservationPurchaseRecommendationRequest,
    ReservationPurchaseRecommendationResponse,
    ReservationUtilizationParams,
    ReservationUtilizationRequest,
    ReservationUtilizationResponse,
)

# SP models - Simplified parameter models for handler functions
from .sp_models import (
    SavingsPlansCoverageParams,
    SavingsPlansPurchaseRecommendationParams,
    SavingsPlansUtilizationDetailsParams,
    SavingsPlansUtilizationParams,
)

__all__ = [
    # Common models
    "DateRange",
    "FilterExpression",
    "GroupDefinition",
    "SortDefinition",
    "PaginationRequest",
    # RI parameter models
    "ReservationUtilizationParams",
    "ReservationCoverageParams",
    "ReservationPurchaseRecommendationParams",
    # RI request/response models
    "ReservationUtilizationRequest",
    "ReservationCoverageRequest",
    "ReservationPurchaseRecommendationRequest",
    "ReservationUtilizationResponse",
    "ReservationCoverageResponse",
    "ReservationPurchaseRecommendationResponse",
    # SP parameter models
    "SavingsPlansUtilizationParams",
    "SavingsPlansCoverageParams",
    "SavingsPlansPurchaseRecommendationParams",
    "SavingsPlansUtilizationDetailsParams",
]
