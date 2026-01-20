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

"""Commitment Purchase Analysis handler for RISP MCP Server.

This module provides handler functions for Commitment Purchase Analysis operations
including starting analysis, retrieving results, and listing analysis tasks.
"""

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context

from ..utils.aws_client import call_aws_api_with_retry, get_cost_explorer_client
from ..utils.formatters import format_error_response, format_success_response

# Configure Loguru logging


async def start_commitment_purchase_analysis(
    context: Context, commitment_purchase_analysis_configuration: dict[str, Any]
) -> dict[str, Any]:
    """Start a commitment purchase analysis.

    Initiates a comprehensive analysis of commitment purchase opportunities,
    comparing Reserved Instances and Savings Plans to identify optimal cost savings.

    Args:
        context: MCP context
        commitment_purchase_analysis_configuration: Analysis configuration

    Returns:
        Dict containing analysis initiation results
    """
    operation = "start_commitment_purchase_analysis"
    logger.info(f"Starting {operation}")

    try:
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {
            "CommitmentPurchaseAnalysisConfiguration": commitment_purchase_analysis_configuration
        }

        logger.info("Making AWS API call: start_commitment_purchase_analysis")

        # Make API call with retry mechanism
        response = await call_aws_api_with_retry(
            ce_client, "start_commitment_purchase_analysis", request_params
        )

        logger.info("Successfully started commitment purchase analysis")

        # Build detailed response
        result_data = {
            "raw_response": response,
            "analysis_id": response.get("AnalysisId"),
            "analysis_started_time": response.get("AnalysisStartedTime"),
            "estimated_completion_time": response.get("EstimatedCompletionTime"),
            "request_parameters": {"configuration": commitment_purchase_analysis_configuration},
        }

        return format_success_response(data=result_data, operation=operation)

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def get_commitment_purchase_analysis(context: Context, analysis_id: str) -> dict[str, Any]:
    """Get commitment purchase analysis results.

    Retrieves the results of a commitment purchase analysis, including
    recommendations and savings projections.

    Args:
        context: MCP context
        analysis_id: Unique identifier for the analysis

    Returns:
        Dict containing analysis results
    """
    operation = "get_commitment_purchase_analysis"
    logger.info(f"Starting {operation} for analysis ID: {analysis_id}")

    try:
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {"AnalysisId": analysis_id}

        logger.info("Making AWS API call: get_commitment_purchase_analysis")

        # Make API call with retry mechanism
        response = await call_aws_api_with_retry(
            ce_client, "get_commitment_purchase_analysis", request_params
        )

        logger.info("Successfully retrieved commitment purchase analysis results")

        # Extract analysis result
        analysis_result = response.get("CommitmentPurchaseAnalysisResult", {})

        # Build detailed response
        result_data = {
            "raw_response": response,
            "commitment_purchase_analysis_result": analysis_result,
            "analysis_id": analysis_result.get("CommitmentPurchaseAnalysisId"),
            "analysis_status": analysis_result.get("CommitmentPurchaseAnalysisStatus"),
            "analysis_started_time": analysis_result.get("AnalysisStartedTime"),
            "analysis_completion_time": analysis_result.get("AnalysisCompletionTime"),
            "estimated_monthly_savings": analysis_result.get("EstimatedMonthlySavings"),
            "estimated_on_demand_cost": analysis_result.get("EstimatedOnDemandCost"),
            "recommended_commitment_purchases": analysis_result.get(
                "RecommendedCommitmentPurchases", []
            ),
            "error_message": analysis_result.get("ErrorMessage"),
            "request_parameters": {"analysis_id": analysis_id},
        }

        return format_success_response(data=result_data, operation=operation)

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def list_commitment_purchase_analyses(
    context: Context,
    analysis_status: str | None = None,
    analysis_ids: list[str] | None = None,
    page_size: int | None = 20,
    next_page_token: str | None = None,
) -> dict[str, Any]:
    """List commitment purchase analyses.

    Retrieves a list of commitment purchase analyses with optional filtering
    by status and analysis IDs.

    Args:
        context: MCP context
        analysis_status: Filter by analysis status (SUCCEEDED, PROCESSING, FAILED)
        analysis_ids: List of analysis IDs to filter by
        page_size: Number of results per page
        next_page_token: Token for pagination

    Returns:
        Dict containing list of analyses
    """
    operation = "list_commitment_purchase_analyses"
    logger.info(f"Starting {operation} with status filter: {analysis_status}")

    try:
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {}

        # Add optional parameters
        if analysis_status:
            request_params["AnalysisStatus"] = analysis_status

        if analysis_ids:
            request_params["AnalysisIds"] = analysis_ids

        if page_size:
            request_params["PageSize"] = page_size

        if next_page_token:
            request_params["NextPageToken"] = next_page_token

        logger.info("Making AWS API call: list_commitment_purchase_analyses")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_summaries = []
        current_token = next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of commitment purchase analyses...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "list_commitment_purchase_analyses", request_params
            )

            # 收集当前页的数据
            page_summaries = response.get("CommitmentPurchaseAnalysisSummaries", [])
            all_summaries.extend(page_summaries)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_summaries)} analyses, Total so far: {len(all_summaries)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all commitment purchase analyses: {len(all_summaries)} total across {page_count} pages"
        )

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "commitment_purchase_analysis_summaries": all_summaries,  # ✅ 所有页的数据
            "total_count": len(all_summaries),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "analysis_status": analysis_status,
                "analysis_ids": analysis_ids,
                "page_size": page_size,
            },
        }

        analysis_count = len(all_summaries)

        return format_success_response(data=result_data, operation=operation)

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)
