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

"""Savings Plans handler for RISP MCP Server.

This module provides handler functions for Savings Plans operations
including utilization, coverage, and purchase recommendation analysis.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import Context

# Import credential services from server
from cred_extract_services import (
    setup_account_context,
    AccountNotFoundError,
    AssumeRoleError,
    CredentialDecryptionError,
    DatabaseConnectionError,
)

from models.sp_models import (
    SavingsPlansCoverageParams,
    SavingsPlansPurchaseRecommendationParams,
    SavingsPlansUtilizationDetailsParams,
    # Simplified parameter models for handler functions
    SavingsPlansUtilizationParams,
)
from utils.aws_client import call_aws_api_with_retry, get_cost_explorer_client
from utils.formatters import (
    format_date_for_api,
    format_error_response,
    format_sp_coverage_summary,
    format_sp_purchase_recommendation_summary,
    format_sp_purchase_recommendations,
    format_sp_utilization_summary,
    format_success_response,
)


async def get_savings_plans_utilization(
    context: Context, params: SavingsPlansUtilizationParams, target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """Get Savings Plans (SP) utilization analysis from AWS Cost Explorer.

    **Use this tool when the user asks for:**
    - Savings Plans utilization or usage analysis
    - SP utilization rate or percentage
    - How well Savings Plans are being used
    - Underutilized or unused Savings Plans
    - SP efficiency or effectiveness analysis
    - Savings Plans commitment utilization
    - SP waste or unused commitment

    **What this tool provides:**
    - SP utilization percentage (how much of purchased SP commitment is being used)
    - Committed amount vs. used amount for Savings Plans
    - Unutilized commitment and associated costs
    - Net SP savings (savings from using SPs vs. On-Demand)
    - On-Demand cost equivalent for SP usage
    - Amortized upfront costs and recurring charges
    - Time-series utilization data (daily or monthly)
    - Utilization breakdown by Savings Plan ARN (optional)

    **Key features:**
    - Helps identify underutilized Savings Plans
    - Shows actual cost savings from SP usage
    - Supports filtering by Savings Plan type, region, etc.
    - Provides historical utilization trends
    - Useful for SP portfolio optimization
    - Works with Compute Savings Plans and EC2 Instance Savings Plans

    **CRITICAL LIMITATION - Supported Filter Dimensions:**
    This API only supports filtering by the following dimensions:
    - LINKED_ACCOUNT - Filter by specific AWS account
    - SAVINGS_PLAN_ARN - Filter by specific Savings Plan ARN
    - SAVINGS_PLANS_TYPE - Filter by Savings Plan type (valid values below)
    - REGION - Filter by AWS region
    - PAYMENT_OPTION - Filter by payment option (e.g., "NO_UPFRONT", "PARTIAL_UPFRONT", "ALL_UPFRONT")
    - INSTANCE_TYPE_FAMILY - Filter by instance family (e.g., "m5", "c5")

    **Valid SAVINGS_PLANS_TYPE values:**
    - "COMPUTE_SP" - Covers EC2, Lambda, Fargate (most flexible, up to 66% savings)
    - "EC2_INSTANCE_SP" - Covers specific EC2 instance family (up to 72% savings)
    - "SAGEMAKER_SP" - Covers SageMaker usage (up to 64% savings)
    - "DATABASE_SP" - Covers RDS, DynamoDB, ElastiCache, etc. (up to 35% savings, newer option)

    **NOT SUPPORTED:**
    - ❌ SERVICE dimension filtering is NOT allowed (will cause ValidationException error)
    - ❌ GroupBy is NOT supported (cannot group by any dimension)
    - ✅ To filter by specific services (e.g., EC2, RDS, Lambda), use get_savings_plans_coverage instead with SERVICE filter
    - ✅ For detailed SP utilization by individual Savings Plan, use get_savings_plans_utilization_details

    **IMPORTANT - Savings Plans vs Reserved Instances:**
    - If the user asks about RDS RI or ElastiCache RI, use get_reservation_utilization instead
    - Savings Plans and Reserved Instances are different pricing models

    Args:
        context: MCP context
        params: Parameters for SP utilization query (see SavingsPlansUtilizationParams for details)
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing utilization analysis results
    """
    operation = "get_savings_plans_utilization"
    logger.info(
        f"Starting {operation} for period {params.time_period.start_date} to {params.time_period.end_date}"
    )

    try:
        # 设置账号上下文（如果指定了目标账号）
        if target_account_id:
            try:
                account_info = await setup_account_context(target_account_id)
                logger.info(f"已切换到账号: {account_info['account_id']} ({account_info['account_alias']})")
            except AccountNotFoundError as e:
                logger.error(f"账号不存在: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="account_not_found"
                )
            except CredentialDecryptionError as e:
                logger.error(f"凭证解密失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="credential_decryption_error"
                )
            except AssumeRoleError as e:
                logger.error(f"AssumeRole 失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="assume_role_error"
                )
            except DatabaseConnectionError as e:
                logger.error(f"数据库连接失败")
                return format_error_response(
                    error=e, operation=operation, error_type="database_connection_error"
                )
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {
            "TimePeriod": {
                "Start": format_date_for_api(params.time_period.start_date, params.granularity),
                "End": format_date_for_api(params.time_period.end_date, params.granularity),
            }
        }

        # Add optional parameters
        if params.granularity:
            request_params["Granularity"] = params.granularity

        if params.filter_expression:
            # 注意：MatchOptions的处理已移至AWS客户端层预防性处理
            request_params["Filter"] = params.filter_expression

        if params.sort_key:
            request_params["SortBy"] = {
                "Key": params.sort_key,
                "SortOrder": params.sort_order or "DESCENDING",
            }

        if params.max_results:
            request_params["MaxResults"] = params.max_results

        if params.next_page_token:
            request_params["NextPageToken"] = params.next_page_token

        logger.info("Making AWS API call: get_savings_plans_utilization")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_utilizations_by_time = []
        current_token = params.next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of SP utilization data...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "get_savings_plans_utilization", request_params
            )

            # 收集当前页的数据
            page_utilizations = response.get("SavingsPlansUtilizationsByTime", [])
            all_utilizations_by_time.extend(page_utilizations)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_utilizations)} time periods, Total so far: {len(all_utilizations_by_time)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all SP utilization data: {len(all_utilizations_by_time)} time periods across {page_count} pages"
        )

        # Format response
        formatted_summary = format_sp_utilization_summary(response)

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "utilization_summary": formatted_summary,
            "utilizations_by_time": all_utilizations_by_time,  # ✅ 所有页的数据
            "total_utilization": response.get("Total", {}),
            "total_count": len(all_utilizations_by_time),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "time_period": {
                    "start_date": params.time_period.start_date,
                    "end_date": params.time_period.end_date,
                },
                "granularity": params.granularity,
            },
        }

        return format_success_response(
            data=result_data, operation=operation, summary=formatted_summary
        )

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def get_savings_plans_coverage(
    context: Context, params: SavingsPlansCoverageParams, target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """Get Savings Plans (SP) coverage analysis from AWS Cost Explorer.

    **Use this tool when the user asks for:**
    - Savings Plans coverage or coverage percentage
    - How much spend is covered by Savings Plans
    - SP coverage gaps or uncovered spend
    - On-Demand spend that could be covered by SPs
    - SP coverage trends over time
    - Coverage analysis by service, instance family, or region
    - Opportunities to purchase more Savings Plans
    - **EC2/RDS/Lambda/etc. service-specific SP coverage** (use SERVICE filter/groupby)

    **What this tool provides:**
    - SP coverage percentage (what % of eligible spend is covered by SPs)
    - Spend covered by Savings Plans
    - Spend NOT covered by Savings Plans (coverage gap)
    - Total eligible spend for Savings Plans
    - Coverage breakdown by service (EC2, Fargate, Lambda, SageMaker, etc.)
    - Time-series coverage data (daily or monthly)
    - Coverage analysis grouped by dimensions (service, instance family, region, etc.)

    **Supported Filter Dimensions:**
    - LINKED_ACCOUNT - Filter by specific AWS account
    - REGION - Filter by AWS region
    - SERVICE - Filter by AWS service (see supported services below)
    - INSTANCE_FAMILY - Filter by instance family (e.g., "m5", "c5")

    **Services covered by Savings Plans:**
    - Compute/EC2 Instance Savings Plans: "Amazon Elastic Compute Cloud - Compute" (EC2), "AWS Lambda", "Amazon EC2 Container Service" (Fargate)
    - SageMaker Savings Plans: "Amazon SageMaker"
    - Database Savings Plans (NEW): "Amazon Relational Database Service" (RDS), "Amazon DynamoDB", "Amazon ElastiCache", "Amazon DocumentDB", etc.

    **IMPORTANT - For RDS/ElastiCache Reserved Instances (RI):**
    - If the user asks about RDS RI or ElastiCache RI, use get_reservation_coverage instead
    - Savings Plans and Reserved Instances are different pricing models
    - Database Savings Plans are newer; many customers still use RDS/ElastiCache RIs

    **Supported GroupBy Dimensions:**
    - INSTANCE_FAMILY - Group coverage by instance family
    - REGION - Group coverage by region
    - SERVICE - Group coverage by AWS service (THIS IS THE KEY DIFFERENCE FROM get_savings_plans_utilization!)

    **Key features:**
    - ✅ Supports SERVICE dimension filtering and grouping (unlike get_savings_plans_utilization)
    - Identifies opportunities to purchase additional Savings Plans
    - Shows which services/workloads have low SP coverage
    - Helps optimize SP portfolio to maximize coverage
    - Supports filtering and grouping by multiple dimensions
    - Useful for SP purchase planning and optimization
    - Works with both Compute Savings Plans and EC2 Instance Savings Plans

    **When to use this vs get_savings_plans_utilization:**
    - Use THIS tool when you need to filter/group by SERVICE (e.g., EC2, RDS, Lambda)
    - Use get_savings_plans_utilization when you need to filter by SAVINGS_PLANS_TYPE

    Args:
        context: MCP context
        params: Parameters for SP coverage query (see SavingsPlansCoverageParams for details)
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing SP coverage analysis with coverage percentages and uncovered spend
    """
    operation = "get_savings_plans_coverage"
    logger.info(
        f"Starting {operation} for period {params.time_period.start_date} to {params.time_period.end_date}"
    )

    try:
        # 设置账号上下文（如果指定了目标账号）
        if target_account_id:
            try:
                account_info = await setup_account_context(target_account_id)
                logger.info(f"已切换到账号: {account_info['account_id']} ({account_info['account_alias']})")
            except AccountNotFoundError as e:
                logger.error(f"账号不存在: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="account_not_found"
                )
            except CredentialDecryptionError as e:
                logger.error(f"凭证解密失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="credential_decryption_error"
                )
            except AssumeRoleError as e:
                logger.error(f"AssumeRole 失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="assume_role_error"
                )
            except DatabaseConnectionError as e:
                logger.error(f"数据库连接失败")
                return format_error_response(
                    error=e, operation=operation, error_type="database_connection_error"
                )
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {
            "TimePeriod": {
                "Start": format_date_for_api(params.time_period.start_date, params.granularity),
                "End": format_date_for_api(params.time_period.end_date, params.granularity),
            }
        }

        # Add optional parameters
        # ⚠️ 重要：Granularity 和 GroupBy 是互斥的，不能同时使用
        if params.group_by:
            # 使用 GroupBy 时，不添加 Granularity 参数
            request_params["GroupBy"] = [
                {"Type": "DIMENSION", "Key": key} for key in params.group_by
            ]
        elif params.granularity:
            # 只有在不使用 GroupBy 时，才添加 Granularity
            request_params["Granularity"] = params.granularity

        if params.filter_expression:
            # 注意：MatchOptions的处理已移至AWS客户端层预防性处理
            request_params["Filter"] = params.filter_expression

        if params.sort_key:
            request_params["SortBy"] = {
                "Key": params.sort_key,
                "SortOrder": params.sort_order or "DESCENDING",
            }

        if params.max_results:
            request_params["MaxResults"] = params.max_results

        if params.next_page_token:
            request_params["NextPageToken"] = params.next_page_token

        logger.info("Making AWS API call: get_savings_plans_coverage")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_coverages_by_time = []
        current_token = params.next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of SP coverage data...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "get_savings_plans_coverage", request_params
            )

            # 收集当前页的数据
            page_coverages = response.get("SavingsPlansCoveragesByTime", [])
            all_coverages_by_time.extend(page_coverages)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_coverages)} time periods, Total so far: {len(all_coverages_by_time)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all SP coverage data: {len(all_coverages_by_time)} time periods across {page_count} pages"
        )

        # Format response
        formatted_summary = format_sp_coverage_summary(response)

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "coverage_summary": formatted_summary,
            "coverages_by_time": all_coverages_by_time,  # ✅ 所有页的数据
            "total_coverage": response.get("Total", {}),
            "total_count": len(all_coverages_by_time),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "time_period": {
                    "start_date": params.time_period.start_date,
                    "end_date": params.time_period.end_date,
                },
                "granularity": params.granularity,
                "group_by": params.group_by,
            },
        }

        return format_success_response(
            data=result_data, operation=operation, summary=formatted_summary
        )

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def get_savings_plans_purchase_recommendation(
    context: Context, params: SavingsPlansPurchaseRecommendationParams, target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """Get Savings Plans (SP) purchase recommendations from AWS Cost Explorer.

    **Use this tool when the user asks for:**
    - Savings Plans purchase recommendations or suggestions
    - Which Savings Plans to buy or purchase
    - SP buying recommendations or opportunities
    - How to save money with Savings Plans
    - SP purchase advice or guidance
    - Recommendations for SP commitments
    - Cost savings opportunities with Savings Plans
    - Compute Savings Plans or EC2 Instance Savings Plans recommendations

    **What this tool provides:**
    - Specific SP purchase recommendations with hourly commitment amounts
    - Estimated monthly savings from purchasing recommended SPs
    - Estimated cost of purchasing the recommended SPs
    - Break-even period (how long until savings offset upfront costs)
    - Recommended SP attributes (type, term, payment option, etc.)
    - Upfront cost, monthly cost, and total cost for each recommendation
    - Savings percentage compared to On-Demand pricing
    - Recommendations based on historical usage patterns

    **Key features:**
    - Provides actionable SP purchase recommendations
    - Supports multiple SP types (Compute SP, EC2 Instance SP, SageMaker SP)
    - Configurable lookback period (7, 30, or 60 days)
    - Supports different SP terms (1-year or 3-year)
    - Supports different payment options (No Upfront, Partial Upfront, All Upfront)
    - Can generate per-account (LINKED) or organization-wide (PAYER) recommendations
    - More flexible than Reserved Instances (applies across instance families, sizes, regions)

    Args:
        context: MCP context
        params: Parameters for SP purchase recommendation query (see SavingsPlansPurchaseRecommendationParams for details)
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing SP purchase recommendations with estimated savings and costs

    Note:
        - LINKED account scope typically provides more granular recommendations
        - PAYER scope may return no recommendations if organization usage is not stable
        - Must first call StartSavingsPlansPurchaseRecommendationGeneration to generate recommendations
        - Recommendations are based on historical usage, not forecasted usage
    """
    operation = "get_savings_plans_purchase_recommendation"
    logger.info(f"Starting {operation} for {params.savings_plans_type}")

    try:
        # 设置账号上下文（如果指定了目标账号）
        if target_account_id:
            try:
                account_info = await setup_account_context(target_account_id)
                logger.info(f"已切换到账号: {account_info['account_id']} ({account_info['account_alias']})")
            except AccountNotFoundError as e:
                logger.error(f"账号不存在: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="account_not_found"
                )
            except CredentialDecryptionError as e:
                logger.error(f"凭证解密失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="credential_decryption_error"
                )
            except AssumeRoleError as e:
                logger.error(f"AssumeRole 失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="assume_role_error"
                )
            except DatabaseConnectionError as e:
                logger.error(f"数据库连接失败")
                return format_error_response(
                    error=e, operation=operation, error_type="database_connection_error"
                )
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {
            "SavingsPlansType": params.savings_plans_type,
            "TermInYears": params.term_in_years,
            "PaymentOption": params.payment_option,
            "LookbackPeriodInDays": params.lookback_period_in_days,
        }

        # Add optional parameters
        if params.account_scope:
            request_params["AccountScope"] = params.account_scope

        if params.filter_expression:
            # 注意：MatchOptions的处理已移至AWS客户端层预防性处理
            request_params["Filter"] = params.filter_expression

        if params.page_size:
            request_params["PageSize"] = params.page_size

        if params.next_page_token:
            request_params["NextPageToken"] = params.next_page_token

        logger.info("Making AWS API call: get_savings_plans_purchase_recommendation")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_recommendations = []
        current_token = params.next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of SP purchase recommendations...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "get_savings_plans_purchase_recommendation", request_params
            )

            # 收集当前页的数据
            page_recommendations = response.get("SavingsPlansPurchaseRecommendation", {}).get(
                "SavingsPlansPurchaseRecommendationDetails", []
            )
            all_recommendations.extend(page_recommendations)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_recommendations)} recommendations, Total so far: {len(all_recommendations)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all SP purchase recommendations: {len(all_recommendations)} total across {page_count} pages"
        )

        # Format response using the last page's data
        formatted_summary = format_sp_purchase_recommendation_summary(response)

        # 重新构建完整的recommendations数据
        complete_recommendation = response.get("SavingsPlansPurchaseRecommendation", {}).copy()
        complete_recommendation["SavingsPlansPurchaseRecommendationDetails"] = all_recommendations
        formatted_recommendations = format_sp_purchase_recommendations(
            {"SavingsPlansPurchaseRecommendation": complete_recommendation}
        )

        # Extract metadata
        metadata = response.get("Metadata", {})

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "recommendation_summary": formatted_summary,
            "recommendations": formatted_recommendations,
            "metadata": {
                "recommendation_id": metadata.get("RecommendationId", ""),
                "generation_timestamp": metadata.get("GenerationTimestamp", ""),
                "additional_metadata": metadata.get("AdditionalMetadata", ""),
            },
            "total_count": len(all_recommendations),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "savings_plans_type": params.savings_plans_type,
                "term_in_years": params.term_in_years,
                "payment_option": params.payment_option,
                "lookback_period": params.lookback_period_in_days,
                "account_scope": params.account_scope,
            },
        }

        return format_success_response(
            data=result_data, operation=operation, summary=formatted_summary
        )

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def start_savings_plans_purchase_recommendation_generation(
    context: Context, target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """Start Savings Plans (SP) purchase recommendation generation process.

    **Use this tool when the user asks for:**
    - Generate new Savings Plans recommendations
    - Refresh Savings Plans recommendations
    - Calculate fresh SP purchase recommendations
    - Update SP recommendations with latest usage data
    - Start SP recommendation generation
    - Create new SP purchase analysis

    **What this tool provides:**
    - Initiates a new SP recommendation generation process
    - Returns a recommendation ID for tracking the generation
    - Provides generation start time and estimated completion time
    - Generates recommendations for ALL Savings Plans types automatically

    **Key features:**
    - Uses the latest usage data and current SP inventory
    - Generates fresh recommendations based on recent patterns
    - Required before calling get_savings_plans_purchase_recommendation()
    - No input parameters needed (generates for all SP types)
    - Asynchronous process (may take a few minutes to complete)

    **Workflow:**
    1. Call this tool to start generation
    2. Wait for generation to complete (check status with list_savings_plans_purchase_recommendation_generation)
    3. Retrieve recommendations with get_savings_plans_purchase_recommendation()

    Args:
        context: MCP context
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing generation request results including RecommendationId and estimated completion time

    Note:
        - This API has NO input parameters per AWS documentation
        - Generates recommendations for ALL Savings Plans types automatically
        - Use get_savings_plans_purchase_recommendation() to retrieve results with specific filters
    """
    operation = "start_savings_plans_purchase_recommendation_generation"
    logger.info(f"Starting {operation}")

    try:
        # 设置账号上下文（如果指定了目标账号）
        if target_account_id:
            try:
                account_info = await setup_account_context(target_account_id)
                logger.info(f"已切换到账号: {account_info['account_id']} ({account_info['account_alias']})")
            except AccountNotFoundError as e:
                logger.error(f"账号不存在: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="account_not_found"
                )
            except CredentialDecryptionError as e:
                logger.error(f"凭证解密失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="credential_decryption_error"
                )
            except AssumeRoleError as e:
                logger.error(f"AssumeRole 失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="assume_role_error"
                )
            except DatabaseConnectionError as e:
                logger.error(f"数据库连接失败")
                return format_error_response(
                    error=e, operation=operation, error_type="database_connection_error"
                )
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # ⚠️ CRITICAL: AWS API 不接受任何参数！
        # 根据 boto3 文档: "StartSavingsPlansPurchaseRecommendationGeneration has no request
        # syntax because no input parameters are needed to support this operation."
        request_params = {}

        logger.info(
            "Making AWS API call: start_savings_plans_purchase_recommendation_generation (no parameters)"
        )

        # Make API call with retry mechanism
        response = await call_aws_api_with_retry(
            ce_client, "start_savings_plans_purchase_recommendation_generation", request_params
        )

        logger.info("Successfully started SP recommendation generation")

        # Build response
        result_data = {
            "raw_response": response,
            "recommendation_id": response.get("RecommendationId", ""),
            "generation_started_time": response.get("GenerationStartedTime", ""),
            "estimated_completion_time": response.get("EstimatedCompletionTime", ""),
            "note": "Use get_savings_plans_purchase_recommendation() to retrieve recommendations after generation completes",
        }

        formatted_summary = {
            "recommendation_id": response.get("RecommendationId", ""),
            "status": "Generation started",
            "estimated_completion": response.get("EstimatedCompletionTime", "Unknown"),
            "next_step": "Call get_savings_plans_purchase_recommendation() to retrieve results",
        }

        return format_success_response(
            data=result_data, operation=operation, summary=formatted_summary
        )

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


# ===== 新增API实现 =====


async def get_savings_plans_utilization_details(
    context: Context,
    params: SavingsPlansUtilizationDetailsParams,
    target_account_id: Optional[str] = None,
) -> dict[str, Any]:
    """Get detailed Savings Plans (SP) utilization analysis with account-level breakdowns.

    **Use this tool when the user asks for:**
    - Detailed Savings Plans utilization by account
    - SP utilization breakdown by individual Savings Plan
    - Account-level SP usage analysis
    - Detailed SP metrics for specific Savings Plans
    - SP utilization with attributes and savings details
    - Granular SP utilization data

    **What this tool provides:**
    - Detailed utilization for each individual Savings Plan
    - Account-level utilization breakdowns
    - SP attributes (ARN, type, region, start/end dates, etc.)
    - Utilization percentage for each SP
    - Savings amount for each SP
    - Amortized commitment costs
    - Used commitment vs. total commitment
    - Unused commitment

    **Key features:**
    - More granular than get_savings_plans_utilization (which provides aggregated data)
    - Shows utilization for each individual Savings Plan
    - Supports filtering by account, SP ARN, SP type, etc.
    - Useful for identifying specific underutilized Savings Plans
    - Provides detailed cost and savings breakdown

    Args:
        context: MCP context
        params: Savings Plans utilization details parameters
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing detailed SP utilization analysis with account-level and SP-level breakdowns
    """
    operation = "get_savings_plans_utilization_details"
    logger.info(
        f"Starting {operation} for period {params.time_period.start_date} to {params.time_period.end_date}"
    )

    try:
        # 设置账号上下文（如果指定了目标账号）
        if target_account_id:
            try:
                account_info = await setup_account_context(target_account_id)
                logger.info(f"已切换到账号: {account_info['account_id']} ({account_info['account_alias']})")
            except AccountNotFoundError as e:
                logger.error(f"账号不存在: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="account_not_found"
                )
            except CredentialDecryptionError as e:
                logger.error(f"凭证解密失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="credential_decryption_error"
                )
            except AssumeRoleError as e:
                logger.error(f"AssumeRole 失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="assume_role_error"
                )
            except DatabaseConnectionError as e:
                logger.error(f"数据库连接失败")
                return format_error_response(
                    error=e, operation=operation, error_type="database_connection_error"
                )
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {
            "TimePeriod": {
                "Start": format_date_for_api(params.time_period.start_date, "MONTHLY"),
                "End": format_date_for_api(params.time_period.end_date, "MONTHLY"),
            }
        }

        # Add optional parameters
        if params.data_type:
            request_params["DataType"] = params.data_type

        if params.filter_expression:
            request_params["Filter"] = params.filter_expression

        if params.sort_by:
            request_params["SortBy"] = params.sort_by

        if params.max_results:
            request_params["MaxResults"] = params.max_results

        if params.next_page_token:
            request_params["NextPageToken"] = params.next_page_token

        logger.info("🔍 Making AWS API call: get_savings_plans_utilization_details")
        logger.info(
            f"🔍 Request params - TimePeriod: {request_params.get('TimePeriod')}, DataType: {request_params.get('DataType')}, MaxResults: {request_params.get('MaxResults')}"
        )

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_details = []
        all_account_ids = set()
        current_token = params.next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token
                logger.info(f"🔍 Using NextPageToken for page {page_count}")

            logger.info(f"📄 Fetching page {page_count} of SP utilization details...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "get_savings_plans_utilization_details", request_params
            )

            # 收集当前页的数据
            page_details = response.get("SavingsPlansUtilizationDetails", [])
            all_details.extend(page_details)

            # 收集账号ID用于诊断
            page_accounts = set()
            for detail in page_details:
                account_id = detail.get("Attributes", {}).get("AccountId")
                if account_id:
                    page_accounts.add(account_id)
                    all_account_ids.add(account_id)

            logger.info(
                f"📄 Page {page_count}: Retrieved {len(page_details)} SP details, Total so far: {len(all_details)}"
            )
            logger.info(f"📄 Page {page_count}: Account IDs in this page: {sorted(page_accounts)}")
            logger.info(f"📄 All unique account IDs so far: {sorted(all_account_ids)}")

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                logger.info("📄 No more pages - pagination complete")
                break
            else:
                logger.info(f"📄 NextPageToken found, will fetch page {page_count + 1}")

        logger.info("✅ Successfully retrieved all SP detailed utilization data:")
        logger.info(f"✅ Total Savings Plans: {len(all_details)}")
        logger.info(f"✅ Total Pages Retrieved: {page_count}")
        logger.info(f"✅ Unique Account IDs ({len(all_account_ids)}): {sorted(all_account_ids)}")
        logger.info(
            f"✅ Missing Account 864899873504: {'YES' if '864899873504' not in all_account_ids else 'NO'}"
        )

        # 使用最后一页的响应来获取汇总信息
        formatted_summary = format_sp_utilization_summary(response)

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "utilization_summary": formatted_summary,
            "savings_plans_utilization_details": all_details,  # ✅ 所有页的数据
            "time_period": response.get("TimePeriod", {}),
            "total": response.get("Total", {}),
            "total_count": len(all_details),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "time_period": {
                    "start_date": params.time_period.start_date,
                    "end_date": params.time_period.end_date,
                },
                "data_type": params.data_type,
                "max_results": params.max_results,
            },
        }

        return format_success_response(data=result_data, operation=operation)

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def get_savings_plan_purchase_recommendation_details(
    context: Context,
    recommendation_detail_id: str,
    target_account_id: Optional[str] = None,
) -> dict[str, Any]:
    """Get detailed information for a specific Savings Plan (SP) purchase recommendation.

    **Use this tool when the user asks for:**
    - Detailed information about a specific SP recommendation
    - More details about a recommendation ID
    - Cost analysis for a specific SP recommendation
    - Savings projections for a specific SP recommendation
    - Implementation details for a specific SP purchase

    **What this tool provides:**
    - Complete recommendation details including all metadata
    - Hourly commitment amount recommendation
    - Estimated monthly savings and costs
    - Break-even period calculation
    - Current On-Demand spend that would be covered
    - Upfront cost, monthly cost, and total cost
    - Savings percentage compared to On-Demand
    - Recommended SP attributes (type, term, payment option, region, etc.)

    **Key features:**
    - Provides comprehensive details for a single SP recommendation
    - Useful for deep-dive analysis of specific recommendations
    - Includes detailed cost-benefit analysis
    - Shows exact commitment amounts and savings projections

    Args:
        context: MCP context
        recommendation_detail_id: Unique identifier for the recommendation detail
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing detailed SP recommendation information with cost analysis and savings projections
    """
    operation = "get_savings_plan_purchase_recommendation_details"
    logger.info(f"Starting {operation} for recommendation ID: {recommendation_detail_id}")

    try:
        # 设置账号上下文（如果指定了目标账号）
        if target_account_id:
            try:
                account_info = await setup_account_context(target_account_id)
                logger.info(f"已切换到账号: {account_info['account_id']} ({account_info['account_alias']})")
            except AccountNotFoundError as e:
                logger.error(f"账号不存在: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="account_not_found"
                )
            except CredentialDecryptionError as e:
                logger.error(f"凭证解密失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="credential_decryption_error"
                )
            except AssumeRoleError as e:
                logger.error(f"AssumeRole 失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="assume_role_error"
                )
            except DatabaseConnectionError as e:
                logger.error(f"数据库连接失败")
                return format_error_response(
                    error=e, operation=operation, error_type="database_connection_error"
                )
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {"RecommendationDetailId": recommendation_detail_id}

        logger.info("Making AWS API call: get_savings_plan_purchase_recommendation_details")

        # Make API call with retry mechanism
        response = await call_aws_api_with_retry(
            ce_client, "get_savings_plan_purchase_recommendation_details", request_params
        )

        logger.info("Successfully retrieved SP detailed recommendation data")

        # Build detailed response
        result_data = {
            "raw_response": response,
            "recommendation_detail_id": recommendation_detail_id,
            "recommendation_detail_data": response.get("RecommendationDetailData", {}),
            "account_scope": response.get("AccountScope"),
            "savings_plans_type": response.get("SavingsPlansType"),
            "term_in_years": response.get("TermInYears"),
            "payment_option": response.get("PaymentOption"),
            "lookback_period_in_days": response.get("LookbackPeriodInDays"),
            "request_parameters": {"recommendation_detail_id": recommendation_detail_id},
        }

        return format_success_response(data=result_data, operation=operation)

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def list_savings_plans_purchase_recommendation_generation(
    context: Context,
    target_account_id: Optional[str] = None,
    generation_status: str | None = None,
    recommendation_ids: list[str] | None = None,
    page_size: int | None = 20,
    next_page_token: str | None = None,
) -> dict[str, Any]:
    """List Savings Plans (SP) purchase recommendation generation tasks and check their status.

    **Use this tool when the user asks for:**
    - Check status of SP recommendation generation
    - List SP recommendation generation tasks
    - See if SP recommendations are ready
    - Check if recommendation generation completed
    - View recommendation generation history
    - Find recommendation ID for a generation task

    **What this tool provides:**
    - List of recommendation generation tasks with their status
    - Recommendation IDs for each generation task
    - Generation start time and completion time
    - Generation status (SUCCEEDED, PROCESSING, FAILED)
    - Estimated completion time for in-progress tasks
    - Error details for failed tasks

    **Key features:**
    - Useful for checking if recommendation generation is complete
    - Supports filtering by status (SUCCEEDED, PROCESSING, FAILED)
    - Supports filtering by specific recommendation IDs
    - Shows generation history
    - Required to get recommendation ID before calling get_savings_plans_purchase_recommendation()

    **Workflow:**
    1. Call start_savings_plans_purchase_recommendation_generation() to start generation
    2. Call this tool to check status and get recommendation ID
    3. Once status is SUCCEEDED, call get_savings_plans_purchase_recommendation() with the recommendation ID

    Args:
        context: MCP context
        target_account_id: Optional AWS account ID for multi-account access
        generation_status: Filter by generation status (SUCCEEDED, PROCESSING, FAILED)
        recommendation_ids: List of recommendation IDs to filter by
        page_size: Number of results per page
        next_page_token: Token for pagination

    Returns:
        Dict containing list of SP recommendation generation tasks with status and metadata
    """
    operation = "list_savings_plans_purchase_recommendation_generation"
    logger.info(f"Starting {operation} with status filter: {generation_status}")

    try:
        # 设置账号上下文（如果指定了目标账号）
        if target_account_id:
            try:
                account_info = await setup_account_context(target_account_id)
                logger.info(f"已切换到账号: {account_info['account_id']} ({account_info['account_alias']})")
            except AccountNotFoundError as e:
                logger.error(f"账号不存在: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="account_not_found"
                )
            except CredentialDecryptionError as e:
                logger.error(f"凭证解密失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="credential_decryption_error"
                )
            except AssumeRoleError as e:
                logger.error(f"AssumeRole 失败: {target_account_id}")
                return format_error_response(
                    error=e, operation=operation, error_type="assume_role_error"
                )
            except DatabaseConnectionError as e:
                logger.error(f"数据库连接失败")
                return format_error_response(
                    error=e, operation=operation, error_type="database_connection_error"
                )
        # Get Cost Explorer client
        ce_client = get_cost_explorer_client()

        # Build request parameters
        request_params = {}

        # Add optional parameters
        if generation_status:
            request_params["GenerationStatus"] = generation_status

        if recommendation_ids:
            request_params["RecommendationIds"] = recommendation_ids

        if page_size:
            request_params["PageSize"] = page_size

        if next_page_token:
            request_params["NextPageToken"] = next_page_token

        logger.info("Making AWS API call: list_savings_plans_purchase_recommendation_generation")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_summaries = []
        current_token = next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of SP recommendation generation list...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "list_savings_plans_purchase_recommendation_generation", request_params
            )

            # 收集当前页的数据
            page_summaries = response.get("GenerationSummaryList", [])
            all_summaries.extend(page_summaries)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_summaries)} generation tasks, Total so far: {len(all_summaries)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all SP recommendation generation tasks: {len(all_summaries)} total across {page_count} pages"
        )

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "generation_summary_list": all_summaries,  # ✅ 所有页的数据
            "total_count": len(all_summaries),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "generation_status": generation_status,
                "recommendation_ids": recommendation_ids,
                "page_size": page_size,
            },
        }

        return format_success_response(data=result_data, operation=operation)

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)
