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

"""Tests for Reserved Instance handler."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from ..handlers.ri_handler import (
    get_reservation_coverage,
    get_reservation_purchase_recommendation,
    get_reservation_utilization,
)
from ..models.common_models import DateRange
from ..models.ri_models import (
    ReservationCoverageParams,
    ReservationPurchaseRecommendationParams,
    ReservationUtilizationParams,
)


class TestReservationUtilization:
    """Test cases for RI utilization analysis."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock MCP context."""
        return Mock()

    @pytest.fixture
    def sample_date_range(self):
        """Create a sample date range for testing."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        return DateRange(start_date=start_date, end_date=end_date)

    @pytest.fixture
    def mock_ce_response(self):
        """Create a mock Cost Explorer response."""
        return {
            "Total": {
                "UtilizationPercentage": "85.5",
                "PurchasedHours": "744",
                "TotalActualHours": "636",
                "UnusedHours": "108",
                "NetRISavings": "150.25",
                "TotalPotentialRISavings": "200.00",
                "AmortizedUpfrontFee": "50.00",
                "AmortizedRecurringFee": "100.00",
                "TotalAmortizedFee": "150.00",
            },
            "UtilizationsByTime": [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-02"},
                    "Total": {"UtilizationPercentage": "85.5"},
                }
            ],
        }

    @patch("mcp-core.risp_mcp_server.handlers.ri_handler.get_cost_explorer_client")
    async def test_get_reservation_utilization_success(
        self, mock_get_client, mock_context, sample_date_range, mock_ce_response
    ):
        """Test successful RI utilization retrieval."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_reservation_utilization.return_value = mock_ce_response
        mock_get_client.return_value = mock_client

        # Execute - using new parameter model
        params = ReservationUtilizationParams(time_period=sample_date_range, granularity="MONTHLY")
        result = await get_reservation_utilization(context=mock_context, params=params)

        # Verify
        assert result["success"] is True
        assert result["operation"] == "get_reservation_utilization"
        assert "utilization_summary" in result["summary"]
        assert "data" in result

        # Verify API call
        mock_client.get_reservation_utilization.assert_called_once()
        call_args = mock_client.get_reservation_utilization.call_args[1]
        assert "TimePeriod" in call_args
        assert call_args["TimePeriod"]["Start"] == sample_date_range.start_date
        assert call_args["TimePeriod"]["End"] == sample_date_range.end_date

    @patch("mcp-core.risp_mcp_server.handlers.ri_handler.get_cost_explorer_client")
    async def test_get_reservation_utilization_with_grouping(
        self, mock_get_client, mock_context, sample_date_range, mock_ce_response
    ):
        """Test RI utilization with subscription ID grouping."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_reservation_utilization.return_value = mock_ce_response
        mock_get_client.return_value = mock_client

        # Execute - using new parameter model
        params = ReservationUtilizationParams(
            time_period=sample_date_range, group_by_subscription_id=True
        )
        result = await get_reservation_utilization(context=mock_context, params=params)

        # Verify
        assert result["success"] is True

        # Verify API call includes GroupBy
        call_args = mock_client.get_reservation_utilization.call_args[1]
        assert "GroupBy" in call_args
        assert call_args["GroupBy"][0]["Type"] == "DIMENSION"
        assert call_args["GroupBy"][0]["Key"] == "SUBSCRIPTION_ID"

    @patch("mcp-core.risp_mcp_server.handlers.ri_handler.get_cost_explorer_client")
    async def test_get_reservation_utilization_error(
        self, mock_get_client, mock_context, sample_date_range
    ):
        """Test RI utilization error handling."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.get_reservation_utilization.side_effect = Exception("AWS API Error")
        mock_get_client.return_value = mock_client

        # Execute - using new parameter model
        params = ReservationUtilizationParams(time_period=sample_date_range)
        result = await get_reservation_utilization(context=mock_context, params=params)

        # Verify
        assert result["success"] is False
        assert result["operation"] == "get_reservation_utilization"
        assert "error" in result
        assert "AWS API Error" in result["error"]


class TestReservationCoverage:
    """Test cases for RI coverage analysis."""

    @pytest.fixture
    def mock_coverage_response(self):
        """Create a mock RI coverage response."""
        return {
            "Total": {
                "CoveragePercentage": "75.0",
                "OnDemandHours": "200",
                "ReservedHours": "600",
                "TotalRunningHours": "800",
                "OnDemandCost": "100.00",
                "CoverageCostPercentage": "80.0",
            },
            "CoveragesByTime": [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-02"},
                    "Total": {"CoveragePercentage": "75.0"},
                }
            ],
        }

    @patch("mcp-core.risp_mcp_server.handlers.ri_handler.get_cost_explorer_client")
    async def test_get_reservation_coverage_success(self, mock_get_client, mock_coverage_response):
        """Test successful RI coverage retrieval."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_reservation_coverage.return_value = mock_coverage_response
        mock_get_client.return_value = mock_client

        # Create test data
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_range = DateRange(start_date=start_date, end_date=end_date)

        # Execute - using new parameter model
        params = ReservationCoverageParams(time_period=date_range)
        result = await get_reservation_coverage(context=Mock(), params=params)

        # Verify
        assert result["success"] is True
        assert result["operation"] == "get_reservation_coverage"
        assert "coverage_summary" in result["summary"]
        assert result["summary"]["coverage_percentage"] == "75.00%"


class TestReservationPurchaseRecommendation:
    """Test cases for RI purchase recommendations."""

    @pytest.fixture
    def mock_recommendation_response(self):
        """Create a mock RI recommendation response."""
        return {
            "Metadata": {
                "RecommendationId": "rec-123456",
                "GenerationTimestamp": "2024-01-01T00:00:00Z",
            },
            "Recommendation": {
                "RecommendationSummary": {
                    "TotalEstimatedMonthlySavingsAmount": "500.00",
                    "TotalEstimatedMonthlySavingsPercentage": "25.0",
                    "CurrencyCode": "USD",
                },
                "RecommendationDetails": [
                    {
                        "AccountId": "123456789012",
                        "RecommendedNumberOfInstancesToPurchase": "2",
                        "EstimatedMonthlySavingsAmount": "250.00",
                        "EstimatedMonthlySavingsPercentage": "20.0",
                        "InstanceDetails": {"InstanceType": "m5.large", "Region": "us-east-1"},
                    }
                ],
            },
        }

    @patch("mcp-core.risp_mcp_server.handlers.ri_handler.get_cost_explorer_client")
    async def test_get_reservation_purchase_recommendation_success(
        self, mock_get_client, mock_recommendation_response
    ):
        """Test successful RI purchase recommendation retrieval."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_reservation_purchase_recommendation.return_value = (
            mock_recommendation_response
        )
        mock_get_client.return_value = mock_client

        # Execute - using new parameter model
        params = ReservationPurchaseRecommendationParams(
            service="EC2-Instance", term_in_years="ONE_YEAR", payment_option="NO_UPFRONT"
        )
        result = await get_reservation_purchase_recommendation(context=Mock(), params=params)

        # Verify
        assert result["success"] is True
        assert result["operation"] == "get_reservation_purchase_recommendation"
        assert "recommendation_summary" in result["summary"]
        assert result["summary"]["recommendation_count"] == 1
        assert len(result["data"]["recommendations"]) == 1

    @patch("mcp-core.risp_mcp_server.handlers.ri_handler.get_cost_explorer_client")
    async def test_get_reservation_purchase_recommendation_with_service_spec(
        self, mock_get_client, mock_recommendation_response
    ):
        """Test RI purchase recommendation with service specification."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_reservation_purchase_recommendation.return_value = (
            mock_recommendation_response
        )
        mock_get_client.return_value = mock_client

        service_spec = {
            "EC2Specification": {
                "InstanceType": "m5.large",
                "Platform": "Linux/UNIX",
                "Tenancy": "default",
                "AvailabilityZone": "us-east-1a",
            }
        }

        # Execute - using new parameter model
        params = ReservationPurchaseRecommendationParams(
            service="EC2-Instance", service_specification=service_spec
        )
        result = await get_reservation_purchase_recommendation(context=Mock(), params=params)

        # Verify
        assert result["success"] is True

        # Verify API call includes service specification
        call_args = mock_client.get_reservation_purchase_recommendation.call_args[1]
        assert "ServiceSpecification" in call_args
        assert call_args["ServiceSpecification"] == service_spec


if __name__ == "__main__":
    pytest.main([__file__])
