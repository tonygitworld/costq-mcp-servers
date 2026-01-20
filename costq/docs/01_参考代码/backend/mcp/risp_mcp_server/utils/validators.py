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

"""Data validation utilities for RISP MCP Server.

This module provides validation functions for RISP-related data,
based on the upstream Cost Explorer MCP Server validation patterns.
"""

import copy
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

from ..constants import (
    ERROR_MESSAGES,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
    VALID_ACCOUNT_SCOPES,
    VALID_GRANULARITIES,
    VALID_LOOKBACK_PERIODS,
    VALID_PAYMENT_OPTIONS,
    VALID_RI_SERVICES,
    VALID_SAVINGS_PLANS_TYPES,
    VALID_TERM_IN_YEARS,
)

# 定义有效的MatchOptions
VALID_MATCH_OPTIONS = {
    "Dimensions": ["EQUALS"],
    "Tags": ["EQUALS", "CASE_SENSITIVE", "CASE_INSENSITIVE"],
    "CostCategories": ["EQUALS"],
}

# 定义不支持MatchOptions的AWS Cost Explorer API
# 这些API在调用时会返回"MatchOptions contain not allowed match option"错误
APIS_WITHOUT_MATCH_OPTIONS_SUPPORT = {
    "get_reservation_utilization",
    "get_reservation_coverage",
    "get_reservation_purchase_recommendation",
    "get_savings_plans_utilization",
    "get_savings_plans_coverage",
    "get_savings_plans_purchase_recommendation",
}


def validate_date_format(date_str: str) -> tuple[bool, str]:
    """Validate date format (YYYY-MM-DD).

    Args:
        date_str: Date string to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not date_str:
        return False, "Date string cannot be empty"

    # Check format using regex
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(date_pattern, date_str):
        return False, f"Invalid date format '{date_str}'. Expected format: YYYY-MM-DD"

    # Check if it's a valid date
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, ""
    except ValueError:
        return False, f"Invalid date '{date_str}'. Please provide a valid date in YYYY-MM-DD format"


def validate_date_range(
    start_date: str, end_date: str, granularity: str | None = None
) -> tuple[bool, str]:
    """Validate date range.

    Args:
        start_date: Start date string
        end_date: End date string
        granularity: Optional granularity for additional validation

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Validate individual dates
    start_valid, start_error = validate_date_format(start_date)
    if not start_valid:
        return False, f"Start date error: {start_error}"

    end_valid, end_error = validate_date_format(end_date)
    if not end_valid:
        return False, f"End date error: {end_error}"

    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        return False, f"Date parsing error: {str(e)}"

    # Check date order
    if start_dt >= end_dt:
        return False, "Start date must be before end date"

    # Check maximum range (13 months)
    max_range = timedelta(days=395)  # ~13 months
    if end_dt - start_dt > max_range:
        return False, "Date range cannot exceed 13 months"

    # Granularity-specific validation
    if granularity == "HOURLY":
        # Hourly data is limited to 7 days
        if end_dt - start_dt > timedelta(days=7):
            return False, "For hourly granularity, date range cannot exceed 7 days"

    return True, ""


def validate_savings_plans_type(sp_type: str) -> tuple[bool, str]:
    """Validate Savings Plans type.

    Args:
        sp_type: Savings Plans type to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if sp_type not in VALID_SAVINGS_PLANS_TYPES:
        return False, ERROR_MESSAGES["INVALID_SAVINGS_PLANS_TYPE"]
    return True, ""


def validate_term_in_years(term: str) -> tuple[bool, str]:
    """Validate term in years.

    Args:
        term: Term to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if term not in VALID_TERM_IN_YEARS:
        return False, ERROR_MESSAGES["INVALID_TERM_IN_YEARS"]
    return True, ""


def validate_payment_option(payment_option: str) -> tuple[bool, str]:
    """Validate payment option.

    Args:
        payment_option: Payment option to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if payment_option not in VALID_PAYMENT_OPTIONS:
        return False, ERROR_MESSAGES["INVALID_PAYMENT_OPTION"]
    return True, ""


def validate_lookback_period(lookback_period: str) -> tuple[bool, str]:
    """Validate lookback period.

    Args:
        lookback_period: Lookback period to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if lookback_period not in VALID_LOOKBACK_PERIODS:
        return False, ERROR_MESSAGES["INVALID_LOOKBACK_PERIOD"]
    return True, ""


def validate_account_scope(account_scope: str) -> tuple[bool, str]:
    """Validate account scope.

    Args:
        account_scope: Account scope to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if account_scope not in VALID_ACCOUNT_SCOPES:
        return False, ERROR_MESSAGES["INVALID_ACCOUNT_SCOPE"]
    return True, ""


def validate_granularity(granularity: str) -> tuple[bool, str]:
    """Validate granularity.

    Args:
        granularity: Granularity to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if granularity not in VALID_GRANULARITIES:
        return False, ERROR_MESSAGES["INVALID_GRANULARITY"]
    return True, ""


def validate_ri_service(service: str) -> tuple[bool, str]:
    """Validate RI service.

    Args:
        service: RI service to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if service not in VALID_RI_SERVICES:
        return False, ERROR_MESSAGES["INVALID_RI_SERVICE"]
    return True, ""


def validate_page_size(page_size: int | None) -> tuple[bool, str]:
    """Validate page size.

    Args:
        page_size: Page size to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if page_size is None:
        return True, ""

    if not isinstance(page_size, int) or page_size < MIN_PAGE_SIZE or page_size > MAX_PAGE_SIZE:
        return False, ERROR_MESSAGES["INVALID_PAGE_SIZE"]

    return True, ""


def validate_filter_expression(filter_expr: dict[str, Any] | None) -> tuple[bool, str]:
    """Validate filter expression structure.

    Args:
        filter_expr: Filter expression to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if filter_expr is None:
        return True, ""

    if not isinstance(filter_expr, dict):
        return False, "Filter expression must be a dictionary"

    # Basic structure validation
    valid_keys = ["And", "Or", "Not", "Dimensions", "Tags", "CostCategories"]
    for key in filter_expr.keys():
        if key not in valid_keys:
            return False, f"Invalid filter key: {key}. Valid keys: {valid_keys}"

    return True, ""


def validate_match_options(filter_expression: dict[str, Any] | None) -> dict[str, Any] | None:
    """验证并修复过滤表达式中的MatchOptions

    Args:
        filter_expression: 过滤表达式字典

    Returns:
        修复后的过滤表达式，如果输入为None则返回None
    """
    if not filter_expression:
        return filter_expression

    # 创建深拷贝以避免修改原始数据
    filter_copy = copy.deepcopy(filter_expression)

    def process_filter(filter_obj):
        """递归处理过滤器对象"""
        if not isinstance(filter_obj, dict):
            return filter_obj

        # 处理And/Or/Not逻辑运算符
        if "And" in filter_obj:
            filter_obj["And"] = [process_filter(f) for f in filter_obj["And"]]
        elif "Or" in filter_obj:
            filter_obj["Or"] = [process_filter(f) for f in filter_obj["Or"]]
        elif "Not" in filter_obj:
            filter_obj["Not"] = process_filter(filter_obj["Not"])

        # 处理Dimensions过滤器
        if "Dimensions" in filter_obj:
            dim_filter = filter_obj["Dimensions"]
            if "MatchOptions" in dim_filter:
                # 确保只使用支持的选项
                valid_options = VALID_MATCH_OPTIONS["Dimensions"]
                dim_filter["MatchOptions"] = [
                    opt for opt in dim_filter["MatchOptions"] if opt in valid_options
                ]
                # 如果没有有效选项，使用默认值
                if not dim_filter["MatchOptions"]:
                    dim_filter["MatchOptions"] = ["EQUALS"]

        # 处理Tags过滤器
        if "Tags" in filter_obj:
            tag_filter = filter_obj["Tags"]
            if "MatchOptions" in tag_filter:
                # 确保只使用支持的选项
                valid_options = VALID_MATCH_OPTIONS["Tags"]
                tag_filter["MatchOptions"] = [
                    opt for opt in tag_filter["MatchOptions"] if opt in valid_options
                ]
                # 如果没有有效选项，使用默认值
                if not tag_filter["MatchOptions"]:
                    tag_filter["MatchOptions"] = ["EQUALS"]

        # 处理CostCategories过滤器
        if "CostCategories" in filter_obj:
            cost_cat_filter = filter_obj["CostCategories"]
            if "MatchOptions" in cost_cat_filter:
                # 确保只使用支持的选项
                valid_options = VALID_MATCH_OPTIONS["CostCategories"]
                cost_cat_filter["MatchOptions"] = [
                    opt for opt in cost_cat_filter["MatchOptions"] if opt in valid_options
                ]
                # 如果没有有效选项，使用默认值
                if not cost_cat_filter["MatchOptions"]:
                    cost_cat_filter["MatchOptions"] = ["EQUALS"]

        return filter_obj

    return process_filter(filter_copy)


def remove_match_options_from_filter(params: dict[str, Any]) -> dict[str, Any]:
    """从API参数中移除所有MatchOptions

    Args:
        params: API调用参数字典

    Returns:
        移除MatchOptions后的参数字典
    """
    if "Filter" not in params:
        return params

    params_copy = copy.deepcopy(params)
    filter_copy = params_copy["Filter"]

    def process_filter(filter_obj):
        """递归处理过滤器对象，移除MatchOptions"""
        if not isinstance(filter_obj, dict):
            return filter_obj

        # 处理And/Or/Not
        if "And" in filter_obj:
            filter_obj["And"] = [process_filter(f) for f in filter_obj["And"]]
        elif "Or" in filter_obj:
            filter_obj["Or"] = [process_filter(f) for f in filter_obj["Or"]]
        elif "Not" in filter_obj:
            filter_obj["Not"] = process_filter(filter_obj["Not"])

        # 移除各种过滤器中的MatchOptions
        for filter_type in ["Dimensions", "Tags", "CostCategories"]:
            if filter_type in filter_obj and "MatchOptions" in filter_obj[filter_type]:
                del filter_obj[filter_type]["MatchOptions"]

        return filter_obj

    params_copy["Filter"] = process_filter(filter_copy)
    return params_copy


def should_remove_match_options(api_name: str) -> bool:
    """判断指定的API是否需要预防性移除MatchOptions

    Args:
        api_name: AWS API方法名称

    Returns:
        bool: 如果需要移除MatchOptions返回True，否则返回False
    """
    return api_name in APIS_WITHOUT_MATCH_OPTIONS_SUPPORT


def prepare_api_params_for_ri_apis(api_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """为RI相关API预防性地准备参数，移除不支持的MatchOptions

    Args:
        api_name: AWS API方法名称
        params: 原始API调用参数

    Returns:
        Dict[str, Any]: 处理后的API参数
    """
    if should_remove_match_options(api_name):
        logger.info(f"API {api_name} 不支持MatchOptions，预防性移除所有MatchOptions")
        return remove_match_options_from_filter(params)

    return params
