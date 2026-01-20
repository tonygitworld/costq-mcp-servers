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

"""Tests for Savings Plans handler."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from ..handlers.sp_handler import (
    get_savings_plans_coverage,
    get_savings_plans_purchase_recommendation,
    get_savings_plans_utilization,
    start_savings_plans_purchase_recommendation_generation,
)
from ..models.common_models import DateRange


class TestSavingsPlansUtilization:
    """Test cases for SP utilization analysis."""

    @pytest.fixture
    def sample_date_range(self):
        """Create a sample date range for testing."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        return DateRange(start_date=start_date, end_date=end_date)

    @pytest.fixture
    def mock_sp_utilization_response(self):
        """Create a mock SP utilization response."""
        return {
            "Total": {
                "UtilizationPercentage": "90.5",
                "TotalCommitment": "1000.00",
                "UsedCommitment": "905.00",
                "UnusedCommitment": "95.00",
                "UtilizationPercentageInUnits": "88.0",
                "SavingsPlansAmortizedCommitment": "950.00",
                "OnDemandCostEquivalent": "1200.00",
                "NetSavings": "295.00",
            },
            "SavingsPlansUtilizationsByTime": [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-02"},
                    "Utilization": {"UtilizationPercentage": "90.5"},
                }
            ],
        }

    @patch("mcp-core.risp_mcp_server.handlers.sp_handler.get_cost_explorer_client")
    async def test_get_savings_plans_utilization_success(
        self, mock_get_client, sample_date_range, mock_sp_utilization_response
    ):
        """Test successful SP utilization retrieval."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_savings_plans_utilization.return_value = mock_sp_utilization_response
        mock_get_client.return_value = mock_client

        # Execute
        result = await get_savings_plans_utilization(
            context=Mock(), time_period=sample_date_range, granularity="MONTHLY"
        )

        # Verify
        assert result["success"] is True
        assert result["operation"] == "get_savings_plans_utilization"
        assert "utilization_summary" in result["summary"]
        assert result["summary"]["utilization_percentage"] == "90.50%"

    @patch("mcp-core.risp_mcp_server.handlers.sp_handler.get_cost_explorer_client")
    async def test_get_savings_plans_utilization_with_sort(
        self, mock_get_client, sample_date_range, mock_sp_utilization_response
    ):
        """Test SP utilization with sorting."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_savings_plans_utilization.return_value = mock_sp_utilization_response
        mock_get_client.return_value = mock_client

        # Execute
        result = await get_savings_plans_utilization(
            context=Mock(),
            time_period=sample_date_range,
            sort_key="UtilizationPercentage",
            sort_order="ASCENDING",
        )

        # Verify
        assert result["success"] is True

        # Verify API call includes sort parameters
        call_args = mock_client.get_savings_plans_utilization.call_args[1]
        assert "SortBy" in call_args
        assert call_args["SortBy"]["Key"] == "UtilizationPercentage"
        assert call_args["SortBy"]["SortOrder"] == "ASCENDING"


class TestSavingsPlansCoverage:
    """Test cases for SP coverage analysis."""

    @pytest.fixture
    def mock_sp_coverage_response(self):
        """Create a mock SP coverage response."""
        return {
            "Total": {
                "CoveragePercentage": "85.0",
                "OnDemandSpend": "300.00",
                "SpendCoveredBySavingsPlans": "1700.00",
                "TotalSpend": "2000.00",
            },
            "SavingsPlansCoveragesByTime": [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-02"},
                    "Coverage": {"CoveragePercentage": "85.0"},
                }
            ],
        }

    @patch("mcp-core.risp_mcp_server.handlers.sp_handler.get_cost_explorer_client")
    async def test_get_savings_plans_coverage_success(
        self, mock_get_client, mock_sp_coverage_response
    ):
        """Test successful SP coverage retrieval."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_savings_plans_coverage.return_value = mock_sp_coverage_response
        mock_get_client.return_value = mock_client

        # Create test data
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_range = DateRange(start_date=start_date, end_date=end_date)

        # Execute
        result = await get_savings_plans_coverage(context=Mock(), time_period=date_range)

        # Verify
        assert result["success"] is True
        assert result["operation"] == "get_savings_plans_coverage"
        assert "coverage_summary" in result["summary"]
        assert result["summary"]["coverage_percentage"] == "85.00%"


class TestSavingsPlansPurchaseRecommendation:
    """Test cases for SP purchase recommendations."""

    @pytest.fixture
    def mock_sp_recommendation_response(self):
        """Create a mock SP recommendation response."""
        return {
            "Metadata": {
                "RecommendationId": "sp-rec-123456",
                "GenerationTimestamp": "2024-01-01T00:00:00Z",
            },
            "SavingsPlansPurchaseRecommendation": {
                "SavingsPlansPurchaseRecommendationSummary": {
                    "TotalRecommendationCount": "2",
                    "EstimatedMonthlySavingsAmount": "800.00",
                    "EstimatedSavingsPercentage": "30.0",
                    "EstimatedROI": "25.5",
                    "HourlyCommitmentToPurchase": "1.50",
                    "DailyCommitmentToPurchase": "36.00",
                    "CurrentOnDemandSpend": "2000.00",
                    "EstimatedTotalCost": "1200.00",
                    "CurrencyCode": "USD",
                },
                "SavingsPlansPurchaseRecommendationDetails": [
                    {
                        "RecommendationDetailId": "detail-1",
                        "AccountId": "123456789012",
                        "HourlyCommitmentToPurchase": "0.75",
                        "EstimatedMonthlySavingsAmount": "400.00",
                        "EstimatedSavingsPercentage": "25.0",
                        "EstimatedROI": "20.0",
                        "SavingsPlansDetails": {
                            "OfferingId": "offering-123",
                            "InstanceFamily": "m5",
                            "Region": "us-east-1",
                        },
                    }
                ],
            },
        }

    @patch("mcp-core.risp_mcp_server.handlers.sp_handler.get_cost_explorer_client")
    async def test_get_savings_plans_purchase_recommendation_success(
        self, mock_get_client, mock_sp_recommendation_response
    ):
        """Test successful SP purchase recommendation retrieval."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_savings_plans_purchase_recommendation.return_value = (
            mock_sp_recommendation_response
        )
        mock_get_client.return_value = mock_client

        # Execute
        result = await get_savings_plans_purchase_recommendation(
            context=Mock(),
            savings_plans_type="COMPUTE_SP",
            term_in_years="ONE_YEAR",
            payment_option="NO_UPFRONT",
            lookback_period_in_days="THIRTY_DAYS",
        )

        # Verify
        assert result["success"] is True
        assert result["operation"] == "get_savings_plans_purchase_recommendation"
        assert "recommendation_summary" in result["summary"]
        assert result["summary"]["total_recommendations"] == "2"
        assert len(result["data"]["recommendations"]) == 1

    @patch("mcp-core.risp_mcp_server.handlers.sp_handler.get_cost_explorer_client")
    async def test_get_savings_plans_purchase_recommendation_with_filter(
        self, mock_get_client, mock_sp_recommendation_response
    ):
        """Test SP purchase recommendation with filter."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_savings_plans_purchase_recommendation.return_value = (
            mock_sp_recommendation_response
        )
        mock_get_client.return_value = mock_client

        filter_expr = {
            "Dimensions": {"Key": "SERVICE", "Values": ["Amazon Elastic Compute Cloud - Compute"]}
        }

        # Execute
        result = await get_savings_plans_purchase_recommendation(
            context=Mock(),
            savings_plans_type="EC2_INSTANCE_SP",
            term_in_years="THREE_YEARS",
            payment_option="PARTIAL_UPFRONT",
            lookback_period_in_days="SIXTY_DAYS",
            filter_expression=filter_expr,
        )

        # Verify
        assert result["success"] is True

        # Verify API call includes filter
        call_args = mock_client.get_savings_plans_purchase_recommendation.call_args[1]
        assert "Filter" in call_args
        assert call_args["Filter"] == filter_expr


class TestSavingsPlansRecommendationGeneration:
    """Test cases for SP recommendation generation."""

    @pytest.fixture
    def mock_generation_response(self):
        """Create a mock generation response."""
        return {
            "RecommendationId": "gen-123456",
            "GenerationStartedTime": "2024-01-01T00:00:00Z",
            "EstimatedCompletionTime": "2024-01-01T00:30:00Z",
        }

    @patch("mcp-core.risp_mcp_server.handlers.sp_handler.get_cost_explorer_client")
    async def test_start_savings_plans_purchase_recommendation_generation_success(
        self, mock_get_client, mock_generation_response
    ):
        """Test successful SP recommendation generation start."""
        # Setup mock
        mock_client = Mock()
        mock_client.start_savings_plans_purchase_recommendation_generation.return_value = (
            mock_generation_response
        )
        mock_get_client.return_value = mock_client

        # Execute - 注意：API 不接受任何参数！
        result = await start_savings_plans_purchase_recommendation_generation(context=Mock())

        # Verify
        assert result["success"] is True
        assert result["operation"] == "start_savings_plans_purchase_recommendation_generation"
        assert result["data"]["recommendation_id"] == "gen-123456"
        assert result["summary"]["status"] == "Generation started"

    @patch("mcp-core.risp_mcp_server.handlers.sp_handler.get_cost_explorer_client")
    async def test_start_savings_plans_purchase_recommendation_generation_error(
        self, mock_get_client
    ):
        """Test SP recommendation generation error handling."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.start_savings_plans_purchase_recommendation_generation.side_effect = Exception(
            "Generation failed"
        )
        mock_get_client.return_value = mock_client

        # Execute - 注意：API 不接受任何参数！
        result = await start_savings_plans_purchase_recommendation_generation(context=Mock())

        # Verify
        assert result["success"] is False
        assert result["operation"] == "start_savings_plans_purchase_recommendation_generation"
        assert "Generation failed" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])
