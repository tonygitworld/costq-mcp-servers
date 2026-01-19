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

"""AWS RISP (Reserved Instance & Savings Plans) MCP Server implementation.

This server provides tools for analyzing AWS Reserved Instances and Savings Plans
through the AWS Cost Explorer API. It offers comprehensive functionality for
utilization analysis, coverage analysis, and purchase recommendations.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import FastMCP

# Import credential extraction services (绝对导入，支持直接运行 server.py)
from cred_extract_services import (
    extract_aws_credentials,
    set_aws_credentials,
    setup_account_context,
    AccountNotFoundError,
    AssumeRoleError,
    CredentialDecryptionError,
    DatabaseConnectionError,
)

from handlers.commitment_handler import (
    get_commitment_purchase_analysis,
    list_commitment_purchase_analyses,
    start_commitment_purchase_analysis,
)

# Import handler functions
from handlers.ri_handler import (
    get_reservation_coverage,
    get_reservation_purchase_recommendation,
    get_reservation_utilization,
)
from handlers.sp_handler import (
    get_savings_plan_purchase_recommendation_details,
    get_savings_plans_coverage,
    get_savings_plans_purchase_recommendation,
    get_savings_plans_utilization,
    get_savings_plans_utilization_details,
    list_savings_plans_purchase_recommendation_generation,
    start_savings_plans_purchase_recommendation_generation,
)

# Export for tool registration
__all__ = [
    "app",
]

# Define server instructions
SERVER_INSTRUCTIONS = """
# AWS RISP (Reserved Instance & Savings Plans) MCP Server

## IMPORTANT:
- Use Service and specific date ranges on each search.
- The Reserved Instance (RI) and Savings Plans (SP) coverage rate is the aggregated coverage of all selected accounts; it cannot automatically output coverage per sub-account and must be queried individually for a specific account.

This MCP server provides comprehensive tools for analyzing AWS Reserved Instances (RI) and Savings Plans (SP)
through the AWS Cost Explorer API. It enables cost optimization through detailed utilization analysis,
coverage analysis, and intelligent purchase recommendations.

## 🔧 Core Capabilities

### Reserved Instance (RI) Analysis
- **get_reservation_utilization**: Analyze RI utilization rates and efficiency
- **get_reservation_coverage**: Determine how much usage is covered by RIs
- **get_reservation_purchase_recommendation**: Get intelligent RI purchase recommendations

### Savings Plans (SP) Analysis
- **get_savings_plans_utilization**: Analyze SP utilization rates and efficiency
- **get_savings_plans_coverage**: Determine how much spend is covered by SPs
- **get_savings_plans_purchase_recommendation**: Get intelligent SP purchase recommendations
- **start_savings_plans_purchase_recommendation_generation**: Initiate SP recommendation generation
- **get_savings_plans_utilization_details**: Get detailed SP utilization with account-level breakdowns
- **get_savings_plan_purchase_recommendation_details**: Get detailed SP purchase recommendation analysis
- **list_savings_plans_purchase_recommendation_generation**: List SP recommendation generation tasks

### Commitment Purchase Analysis
- **start_commitment_purchase_analysis**: Start comprehensive commitment purchase analysis
- **get_commitment_purchase_analysis**: Get commitment purchase analysis results
- **list_commitment_purchase_analyses**: List commitment purchase analysis tasks

## 📊 Use Cases & Examples

| Question Type | Recommended Tool | Notes |
|---------------|------------------|-------|
| "What's my RI utilization?" | get_reservation_utilization | Shows efficiency of current RIs |
| "How much is covered by RIs?" | get_reservation_coverage | Shows coverage percentage |
| "Should I buy more RIs?" | get_reservation_purchase_recommendation | Provides purchase guidance |
| "What's my SP utilization?" | get_savings_plans_utilization | Shows SP efficiency |
| "How much is covered by SPs?" | get_savings_plans_coverage | Shows SP coverage percentage |
| "Should I buy Savings Plans?" | get_savings_plans_purchase_recommendation | Provides SP purchase guidance |

## 🎯 Cost Optimization Tips

### Reserved Instances
- Monitor utilization regularly - aim for >80% utilization
- Use coverage analysis to identify uncovered usage
- Consider convertible RIs for flexibility
- Analyze by service and instance type for targeted purchases

### Savings Plans
- Compute SPs offer maximum flexibility across services
- EC2 Instance SPs provide higher discounts for specific usage
- Monitor both utilization and coverage metrics
- Consider 1-year vs 3-year terms based on usage predictability

## 🔍 Advanced Analysis
- Compare RI vs SP recommendations for optimal mix
- Use filters to analyze specific services or accounts
- Group by dimensions for detailed breakdowns
- Leverage time-series data for trend analysis

## ⚠️ Important Notes
- SP recommendations require async generation - use start_savings_plans_purchase_recommendation_generation first
- All monetary values are in USD unless specified otherwise
- Utilization data may have up to 24-hour delay
- Recommendations are based on historical usage patterns

## 🔐 Required Permissions
- ce:GetReservationUtilization
- ce:GetReservationCoverage
- ce:GetReservationPurchaseRecommendation
- ce:GetSavingsPlansUtilization
- ce:GetSavingsPlansCoverage
- ce:GetSavingsPlansPurchaseRecommendation
- ce:StartSavingsPlansPurchaseRecommendationGeneration
- ce:GetSavingsPlansUtilizationDetails
- ce:GetSavingsPlanPurchaseRecommendationDetails
- ce:ListSavingsPlansPurchaseRecommendationGeneration
- ce:StartCommitmentPurchaseAnalysis
- ce:GetCommitmentPurchaseAnalysis
- ce:ListCommitmentPurchaseAnalyses
"""

# Create FastMCP server with instructions and AgentCore Runtime configuration
app = FastMCP(
    name="AWS RISP MCP Server",
    instructions=SERVER_INSTRUCTIONS,
    host="0.0.0.0",           # AgentCore Runtime 要求
    stateless_http=True       # AgentCore Runtime 要求
)


# Register Reserved Instance tools
# 工具名称必须 <= 43 字符 (Bedrock 限制 64 - runtime前缀 21 = 43)
app.tool("get_ri_utilization")(get_reservation_utilization)
app.tool("get_ri_coverage")(get_reservation_coverage)
app.tool("get_ri_purchase_recommendation")(get_reservation_purchase_recommendation)

# Register Savings Plans tools
app.tool("get_sp_utilization")(get_savings_plans_utilization)
app.tool("get_sp_coverage")(get_savings_plans_coverage)
app.tool("get_sp_purchase_recommendation")(get_savings_plans_purchase_recommendation)
app.tool("start_sp_recommendation_gen")(
    start_savings_plans_purchase_recommendation_generation
)
app.tool("get_sp_utilization_details")(get_savings_plans_utilization_details)
app.tool("get_sp_recommendation_details")(
    get_savings_plan_purchase_recommendation_details
)
app.tool("list_sp_recommendation_gen")(
    list_savings_plans_purchase_recommendation_generation
)

# Register Commitment Purchase Analysis tools
app.tool("start_commitment_analysis")(start_commitment_purchase_analysis)
app.tool("get_commitment_analysis")(get_commitment_purchase_analysis)
app.tool("list_commitment_analyses")(list_commitment_purchase_analyses)


def main():
    """Run the MCP server with streamable HTTP transport for AgentCore."""
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
