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

"""Constants for CostQ RISP MCP Server.

This module contains all the constants used for Reserved Instance and Savings Plans operations.
"""

# Savings Plans 类型
VALID_SAVINGS_PLANS_TYPES: list[str] = [
    "COMPUTE_SP",  # 计算型 Savings Plans
    "EC2_INSTANCE_SP",  # EC2 实例 Savings Plans
    "SAGEMAKER_SP",  # SageMaker Savings Plans
]

# 期限选项
VALID_TERM_IN_YEARS: list[str] = ["ONE_YEAR", "THREE_YEARS"]

# 付款选项
VALID_PAYMENT_OPTIONS: list[str] = [
    "NO_UPFRONT",  # 无预付费
    "PARTIAL_UPFRONT",  # 部分预付费
    "ALL_UPFRONT",  # 全额预付费
    "LIGHT_UTILIZATION",  # 轻度使用（RI专用）
    "MEDIUM_UTILIZATION",  # 中度使用（RI专用）
    "HEAVY_UTILIZATION",  # 重度使用（RI专用）
]

# 回看期间
VALID_LOOKBACK_PERIODS: list[str] = ["SEVEN_DAYS", "THIRTY_DAYS", "SIXTY_DAYS"]

# 账户范围
VALID_ACCOUNT_SCOPES: list[str] = [
    "PAYER",  # 付款账户（包含组织内所有账户）
    "LINKED",  # 关联账户（仅单个成员账户）
]

# 服务名称映射 - 简化名称到AWS API名称
SERVICE_NAME_MAPPING: dict[str, str] = {
    "RDS": "Amazon Relational Database Service",
    "EC2-Instance": "Amazon Elastic Compute Cloud - Compute",
    "ElastiCache": "Amazon ElastiCache",
    "Redshift": "Amazon Redshift",
    "OpenSearch": "Amazon OpenSearch Service",
    "MemoryDB": "Amazon MemoryDB Service",
    "DynamoDB": "Amazon DynamoDB Service",
}

# RI 服务类型 - 使用AWS API要求的完整名称
VALID_RI_SERVICES: list[str] = [
    "Amazon Elastic Compute Cloud - Compute",
    "Amazon Relational Database Service",
    "Amazon ElastiCache",
    "Amazon Redshift",
    "Amazon OpenSearch Service",
]

# 简化的RI服务类型（用于用户输入）
VALID_RI_SERVICES_SIMPLE: list[str] = [
    "EC2-Instance",
    "RDS",
    "ElastiCache",
    "Redshift",
    "OpenSearch",
]

# 粒度选项
VALID_GRANULARITIES: list[str] = ["DAILY", "MONTHLY"]

# RI 推荐服务规格
VALID_RI_SERVICE_SPECIFICATIONS: list[str] = [
    "EC2-Instance",
    "RDS",
    "ElastiCache",
    "Redshift",
    "OpenSearch",
]

# 排序键
VALID_RI_SORT_KEYS: list[str] = [
    "UtilizationPercentage",
    "UtilizationPercentageInUnits",
    "PurchasedHours",
    "PurchasedUnits",
    "TotalActualHours",
    "TotalActualUnits",
    "UnusedHours",
    "UnusedUnits",
    "OnDemandCostOfRIHoursUsed",
    "NetRISavings",
    "TotalPotentialRISavings",
    "AmortizedUpfrontFee",
    "AmortizedRecurringFee",
    "TotalAmortizedFee",
    "RICostForUnusedHours",
    "RealizedSavings",
    "UnrealizedSavings",
]

# SP 排序键
VALID_SP_SORT_KEYS: list[str] = [
    "UtilizationPercentage",
    "TotalCommitment",
    "UsedCommitment",
    "UnusedCommitment",
    "UtilizationPercentageInUnits",
    "SavingsPlansAmortizedCommitment",
    "OnDemandCostEquivalent",
    "NetSavings",
]

# SP 详细利用率数据类型
VALID_SP_DATA_TYPES: list[str] = [
    "ATTRIBUTES",  # 属性数据
    "UTILIZATION",  # 利用率数据
    "COST_AND_USAGE",  # 成本和使用量数据
]

# 承诺购买分析类型
VALID_ANALYSIS_TYPES: list[str] = [
    "MAX_SAVINGS",  # 最大节省分析
    "CUSTOM_COMMITMENT",  # 自定义承诺分析
]

# 承诺购买分析状态
VALID_ANALYSIS_STATUSES: list[str] = [
    "SUCCEEDED",  # 成功
    "PROCESSING",  # 处理中
    "FAILED",  # 失败
]

# 排序顺序
VALID_SORT_ORDERS: list[str] = ["ASCENDING", "DESCENDING"]

# 默认值
DEFAULT_GRANULARITY = "MONTHLY"
DEFAULT_ACCOUNT_SCOPE = "PAYER"
DEFAULT_LOOKBACK_PERIOD = "SEVEN_DAYS"
DEFAULT_TERM_IN_YEARS = "ONE_YEAR"
DEFAULT_PAYMENT_OPTION = "NO_UPFRONT"
DEFAULT_PAGE_SIZE = 20

# API 限制
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1

# 错误消息
ERROR_MESSAGES = {
    "INVALID_SAVINGS_PLANS_TYPE": f"Invalid savings_plans_type. Valid values: {VALID_SAVINGS_PLANS_TYPES}",
    "INVALID_TERM_IN_YEARS": f"Invalid term_in_years. Valid values: {VALID_TERM_IN_YEARS}",
    "INVALID_PAYMENT_OPTION": f"Invalid payment_option. Valid values: {VALID_PAYMENT_OPTIONS}",
    "INVALID_LOOKBACK_PERIOD": f"Invalid lookback_period_in_days. Valid values: {VALID_LOOKBACK_PERIODS}",
    "INVALID_ACCOUNT_SCOPE": f"Invalid account_scope. Valid values: {VALID_ACCOUNT_SCOPES}",
    "INVALID_GRANULARITY": f"Invalid granularity. Valid values: {VALID_GRANULARITIES}",
    "INVALID_RI_SERVICE": f"Invalid RI service. Valid values: {VALID_RI_SERVICES}",
    "INVALID_PAGE_SIZE": f"Invalid page_size. Must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}",
    "INVALID_SP_DATA_TYPE": f"Invalid data_type. Valid values: {VALID_SP_DATA_TYPES}",
    "INVALID_ANALYSIS_TYPE": f"Invalid analysis_type. Valid values: {VALID_ANALYSIS_TYPES}",
    "INVALID_ANALYSIS_STATUS": f"Invalid analysis_status. Valid values: {VALID_ANALYSIS_STATUSES}",
    "MISSING_TIME_PERIOD": "TimePeriod is required for this operation",
    "AWS_CLIENT_ERROR": "Failed to create AWS Cost Explorer client",
    "API_CALL_FAILED": "AWS Cost Explorer API call failed",
}
