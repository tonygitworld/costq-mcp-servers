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

"""Reserved Instance handler for RISP MCP Server.

This module provides handler functions for Reserved Instance operations
including utilization, coverage, and purchase recommendation analysis.
"""

import logging
import os
import sys
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

from models.ri_models import (
    ReservationCoverageParams,
    ReservationPurchaseRecommendationParams,
    # Simplified parameter models for handler functions
    ReservationUtilizationParams,
)
from utils.aws_client import (
    call_aws_api_with_retry,
    get_cost_explorer_client,
    map_service_name,
    validate_service_name,
)
from utils.formatters import (
    format_date_for_api,
    format_error_response,
    format_ri_coverage_summary,
    format_ri_utilization_summary,
    format_success_response,
)

# Configure Loguru logging


async def get_reservation_utilization(
    context: Context, params: ReservationUtilizationParams, target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """Get Reserved Instance (RI) utilization analysis from AWS Cost Explorer.

    **Use this tool when the user asks for:**
    - Reserved Instance utilization or usage analysis
    - RI utilization rate or percentage
    - How well Reserved Instances are being used
    - Underutilized or unused Reserved Instances
    - RI efficiency or effectiveness analysis
    - Reserved capacity utilization trends
    - RI waste or unused capacity

    **What this tool provides:**
    - RI utilization percentage (how much of purchased RI capacity is being used)
    - Purchased hours vs. used hours for Reserved Instances
    - Unutilized hours and associated costs
    - Net RI savings (savings from using RIs vs. On-Demand)
    - On-Demand cost equivalent for RI usage
    - Amortized upfront costs and recurring charges
    - Time-series utilization data (daily or monthly)
    - Utilization breakdown by subscription ID (optional)

    **Key features:**
    - Helps identify underutilized Reserved Instances
    - Shows actual cost savings from RI usage
    - Supports filtering by service, instance type, region, etc.
    - Provides historical utilization trends
    - Useful for RI portfolio optimization

    Args:
        context: MCP context
        params: Parameters for RI utilization query (see ReservationUtilizationParams for details)
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing RI utilization analysis with usage percentages and cost savings
    """
    operation = "get_reservation_utilization"
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
        if params.group_by_subscription_id:
            # 使用 GroupBy 时，不添加 Granularity 参数
            request_params["GroupBy"] = [{"Type": "DIMENSION", "Key": "SUBSCRIPTION_ID"}]
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

        logger.info("Making AWS API call: get_reservation_utilization")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_utilizations = []
        current_token = params.next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of RI utilization data...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "get_reservation_utilization", request_params
            )

            # 收集当前页的数据
            page_utilizations = response.get("UtilizationsByTime", [])
            all_utilizations.extend(page_utilizations)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_utilizations)} time periods, Total so far: {len(all_utilizations)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all RI utilization data: {len(all_utilizations)} time periods across {page_count} pages"
        )

        # Format response
        formatted_summary = format_ri_utilization_summary(response)

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "utilization_summary": formatted_summary,
            "utilizations_by_time": all_utilizations,  # ✅ 所有页的数据
            "total_utilization": response.get("Total", {}),
            "total_count": len(all_utilizations),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "time_period": {
                    "start_date": params.time_period.start_date,
                    "end_date": params.time_period.end_date,
                },
                "granularity": params.granularity,
                "grouped_by_subscription": params.group_by_subscription_id,
            },
        }

        return format_success_response(
            data=result_data, operation=operation, summary=formatted_summary
        )

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)


async def get_reservation_coverage(
    context: Context, params: ReservationCoverageParams, target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """Get Reserved Instance (RI) coverage analysis from AWS Cost Explorer.

    **Use this tool when the user asks for:**
    - Reserved Instance coverage or coverage percentage
    - How much usage is covered by Reserved Instances
    - RI coverage gaps or uncovered usage
    - On-Demand usage that could be covered by RIs
    - RI coverage trends over time
    - Coverage analysis by service, instance type, or region
    - Opportunities to purchase more Reserved Instances

    **What this tool provides:**
    - RI coverage percentage (what % of usage is covered by RIs)
    - On-Demand hours that are covered by Reserved Instances
    - On-Demand hours that are NOT covered (coverage gap)
    - Total running hours for each resource type
    - Coverage breakdown by service (EC2, RDS, ElastiCache, Redshift, etc.)
    - Time-series coverage data (daily or monthly)
    - Coverage analysis grouped by dimensions (service, instance type, region, etc.)

    **Key features:**
    - Identifies opportunities to purchase additional Reserved Instances
    - Shows which services/resources have low RI coverage
    - Helps optimize RI portfolio to maximize coverage
    - Supports filtering and grouping by multiple dimensions
    - Useful for RI purchase planning and optimization

    Args:
        context: MCP context
        params: Parameters for RI coverage query (see ReservationCoverageParams for details)
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing RI coverage analysis with coverage percentages and uncovered usage
    """
    operation = "get_reservation_coverage"
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

        logger.info("Making AWS API call: get_reservation_coverage")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_coverages = []
        current_token = params.next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of RI coverage data...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "get_reservation_coverage", request_params
            )

            # 收集当前页的数据
            page_coverages = response.get("CoveragesByTime", [])
            all_coverages.extend(page_coverages)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_coverages)} time periods, Total so far: {len(all_coverages)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all RI coverage data: {len(all_coverages)} time periods across {page_count} pages"
        )

        # Format response
        formatted_summary = format_ri_coverage_summary(response)

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "coverage_summary": formatted_summary,
            "coverages_by_time": all_coverages,  # ✅ 所有页的数据
            "total_coverage": response.get("Total", {}),
            "total_count": len(all_coverages),  # ✅ 添加总数
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


async def get_reservation_purchase_recommendation(
    context: Context, params: ReservationPurchaseRecommendationParams, target_account_id: Optional[str] = None
) -> dict[str, Any]:
    """Get Reserved Instance (RI) purchase recommendations from AWS Cost Explorer.

    **Use this tool when the user asks for:**
    - Reserved Instance purchase recommendations or suggestions
    - Which Reserved Instances to buy or purchase
    - RI buying recommendations or opportunities
    - How to save money with Reserved Instances
    - RI purchase advice or guidance
    - Recommendations for RI commitments
    - Cost savings opportunities with Reserved Instances

    **What this tool provides:**
    - Specific RI purchase recommendations with instance types and quantities
    - Estimated monthly savings from purchasing recommended RIs
    - Estimated cost of purchasing the recommended RIs
    - Break-even period (how long until savings offset upfront costs)
    - Recommended RI attributes (instance type, region, platform, tenancy, etc.)
    - Upfront cost, monthly cost, and total cost for each recommendation
    - Savings percentage compared to On-Demand pricing
    - Recommendations based on historical usage patterns

    **Key features:**
    - Provides actionable RI purchase recommendations
    - Supports multiple AWS services (EC2, RDS, ElastiCache, Redshift, etc.)
    - Configurable lookback period (7, 30, or 60 days)
    - Supports different RI terms (1-year or 3-year)
    - Supports different payment options (No Upfront, Partial Upfront, All Upfront)
    - Can generate per-account (LINKED) or organization-wide (PAYER) recommendations

    Args:
        context: MCP context
        params: Parameters for RI purchase recommendation query (see ReservationPurchaseRecommendationParams for details)
        target_account_id: Optional AWS account ID for multi-account access

    Returns:
        Dict containing RI purchase recommendations with estimated savings and costs

    Note:
        - LINKED account scope typically provides more granular recommendations
        - PAYER scope may return no recommendations if organization usage is not stable
        - Recommendations are based on historical usage, not forecasted usage
    """
    operation = "get_reservation_purchase_recommendation"
    logger.info(f"Starting {operation} for service {params.service}")

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

        # 验证并映射服务名称
        if not validate_service_name(params.service):
            return format_error_response(
                error=Exception(f"Invalid service: {params.service}"), operation=operation
            )

        # 映射服务名称到AWS API要求的格式
        mapped_service = map_service_name(params.service)

        # Build request parameters
        request_params = {"Service": mapped_service}

        # Add optional parameters
        if params.account_scope:
            request_params["AccountScope"] = params.account_scope

        if params.lookback_period_in_days:
            request_params["LookbackPeriodInDays"] = params.lookback_period_in_days

        if params.term_in_years:
            request_params["TermInYears"] = params.term_in_years

        if params.payment_option:
            request_params["PaymentOption"] = params.payment_option

        if params.service_specification:
            request_params["ServiceSpecification"] = params.service_specification

        if params.page_size:
            request_params["PageSize"] = params.page_size

        if params.next_page_token:
            request_params["NextPageToken"] = params.next_page_token

        logger.info("Making AWS API call: get_reservation_purchase_recommendation")

        # ✅ 处理分页：循环调用 API 直到获取所有数据
        all_details = []
        current_token = params.next_page_token
        page_count = 0

        while True:
            page_count += 1
            if current_token:
                request_params["NextPageToken"] = current_token

            logger.info(f"Fetching page {page_count} of RI purchase recommendations...")

            # Make API call with retry mechanism
            response = await call_aws_api_with_retry(
                ce_client, "get_reservation_purchase_recommendation", request_params
            )

            # 收集当前页的数据
            recommendation = response.get("Recommendation", {})
            page_details = recommendation.get("RecommendationDetails", [])
            all_details.extend(page_details)
            logger.info(
                f"Page {page_count}: Retrieved {len(page_details)} recommendations, Total so far: {len(all_details)}"
            )

            # 检查是否还有更多页
            current_token = response.get("NextPageToken")
            if not current_token:
                break

        logger.info(
            f"Successfully retrieved all RI purchase recommendations: {len(all_details)} total across {page_count} pages"
        )

        # Format response using the last page's data
        metadata = response.get("Metadata", {})
        recommendation = response.get("Recommendation", {})
        recommendation_summary = recommendation.get("RecommendationSummary", {})

        formatted_summary = {
            "total_estimated_monthly_savings": recommendation_summary.get(
                "TotalEstimatedMonthlySavingsAmount", "0"
            ),
            "total_estimated_monthly_savings_percentage": recommendation_summary.get(
                "TotalEstimatedMonthlySavingsPercentage", "0"
            ),
            "currency_code": recommendation_summary.get("CurrencyCode", "USD"),
            "recommendation_count": len(all_details),  # ✅ 使用所有页的总数
        }

        # Format recommendation details (使用所有页的数据)
        formatted_recommendations = []
        for detail in all_details:  # ✅ 遍历所有页的数据
            instance_details = detail.get("InstanceDetails", {})
            formatted_recommendations.append(
                {
                    "account_id": detail.get("AccountId", ""),
                    "instance_details": instance_details,
                    "recommended_instances": detail.get(
                        "RecommendedNumberOfInstancesToPurchase", "0"
                    ),
                    "minimum_instances_used": detail.get(
                        "MinimumNumberOfInstancesUsedPerHour", "0"
                    ),
                    "maximum_instances_used": detail.get(
                        "MaximumNumberOfInstancesUsedPerHour", "0"
                    ),
                    "average_instances_used": detail.get(
                        "AverageNumberOfInstancesUsedPerHour", "0"
                    ),
                    "estimated_monthly_savings": detail.get("EstimatedMonthlySavingsAmount", "0"),
                    "estimated_monthly_savings_percentage": detail.get(
                        "EstimatedMonthlySavingsPercentage", "0"
                    ),
                    "estimated_monthly_on_demand_cost": detail.get(
                        "EstimatedMonthlyOnDemandCost", "0"
                    ),
                    "estimated_reservation_cost": detail.get(
                        "EstimatedReservationCostForLookbackPeriod", "0"
                    ),
                    "upfront_cost": detail.get("UpfrontCost", "0"),
                    "recurring_monthly_cost": detail.get("RecurringStandardMonthlyCost", "0"),
                    "currency_code": detail.get("CurrencyCode", "USD"),
                }
            )

        # Build detailed response with all paginated data
        result_data = {
            "raw_response": response,  # 最后一页的原始响应
            "recommendation_summary": formatted_summary,
            "recommendations": formatted_recommendations,  # ✅ 所有页的推荐
            "metadata": {
                "recommendation_id": metadata.get("RecommendationId", ""),
                "generation_timestamp": metadata.get("GenerationTimestamp", ""),
                "additional_metadata": metadata.get("AdditionalMetadata", ""),
            },
            "total_count": len(all_details),  # ✅ 添加总数
            "pages_retrieved": page_count,  # ✅ 添加页数
            "request_parameters": {
                "service": params.service,
                "account_scope": params.account_scope,
                "lookback_period": params.lookback_period_in_days,
                "term_in_years": params.term_in_years,
                "payment_option": params.payment_option,
            },
        }

        return format_success_response(
            data=result_data, operation=operation, summary=formatted_summary
        )

    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        return format_error_response(error=e, operation=operation)
