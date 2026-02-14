"""
GCP Cost Management MCP Server

FastMCP server providing GCP cost analysis and optimization tools.

Features:
- Cost queries via BigQuery billing export (6 tools)
- Cost optimization recommendations via Recommender API (5 tools)
- Budget management via Budgets API (3 tools)
- Multi-account support
"""

import logging
import os

logger = logging.getLogger(__name__)
from mcp.server.fastmcp import FastMCP

# Optional default account ID (fallback only)
DEFAULT_ACCOUNT_ID = os.getenv("GCP_ACCOUNT_ID")
if not DEFAULT_ACCOUNT_ID:
    logger.info("GCP_ACCOUNT_ID not set - tools will rely on account_id parameter")

# Import handlers
from handlers.billing_handler import (
    get_cost_by_label,
    get_cost_by_project,
    get_cost_by_service,
    get_cost_by_sku,
    get_cost_summary,
    get_daily_cost_trend,
)
from handlers.budget_handler import (
    create_budget,
    get_budget_status,
    list_budgets,
)
from handlers.cud_handler import (
    get_cud_coverage,
    get_cud_savings_analysis,
    list_commitments,
)
from handlers.cud_handler_advanced import (
    get_cud_resource_usage,
    get_cud_status_check,
)
from handlers.cud_handler_comparison import (
    get_cud_vs_ondemand_comparison,
    get_flexible_cud_analysis,
)
from handlers.recommender_handler import (
    get_all_recommendations,
    get_commitment_recommendations,
    get_idle_resources,
    get_vm_rightsizing_recommendations,
    mark_recommendation_status,
)

# Server Instructions
SERVER_INSTRUCTIONS = """
# GCP Billing Cost Management MCP Server

This server provides comprehensive GCP cost analysis and optimization tools.

## Prerequisites

### 1. BigQuery Billing Export (Required for cost queries)
Enable BigQuery billing export in GCP Console:
1. Go to Billing → Billing export → BigQuery export
2. Enable "Detailed usage cost data"
3. Select/create a BigQuery dataset (e.g., 'billing_export')
4. Wait ~24 hours for data to appear

### 2. Service Account Permissions
Required IAM roles:
- `roles/billing.viewer` - View billing accounts
- `roles/bigquery.dataViewer` - Read billing export data
- `roles/bigquery.jobUser` - Execute BigQuery queries
- `roles/recommender.viewer` - View cost recommendations
- `roles/billing.costsManager` - Manage budgets (optional, for budget creation)

### 3. Enable Required APIs
```bash
gcloud services enable bigquery.googleapis.com
gcloud services enable recommender.googleapis.com
gcloud services enable cloudbilling.googleapis.com
gcloud services enable billingbudgets.googleapis.com
```

## Tool Categories

### 🛠️ Utility Tools
1. **get_today_date** - Get current date information (helps AI understand time context)

### 📊 Cost Analysis Tools (BigQuery-based)
2. **gcp_cost_by_service** - Cost breakdown by GCP service
3. **gcp_cost_by_project** - Cost breakdown by project
4. **gcp_daily_cost_trend** - Daily cost time series
5. **gcp_cost_by_label** - Cost allocation by labels (team, env, etc.)
6. **gcp_cost_by_sku** - Detailed SKU-level cost breakdown
7. **gcp_cost_summary** - Overall cost summary and statistics

### 💡 Cost Optimization Tools (Recommender API)
8. **gcp_vm_rightsizing_recommendations** - VM machine type optimization
9. **gcp_idle_resources** - Identify idle VMs, disks, IPs
10. **gcp_commitment_recommendations** - Committed Use Discounts (CUD) advice
11. **gcp_all_recommendations** - All optimization opportunities
12. **gcp_mark_recommendation_status** - Mark recommendations as applied/dismissed

### 💰 Budget Management Tools (Budgets API)
13. **gcp_list_budgets** - List all budgets
14. **gcp_get_budget_status** - Get budget details
15. **gcp_create_budget** - Create new budget with thresholds

### 🎯 CUD Analysis Tools - 基础分析 (Core Analysis)
16. **gcp_list_commitments** - List all CUD commitments (includes UTILIZATION and COVERAGE)
17. **gcp_cud_coverage** - CUD coverage analysis (% of eligible usage covered)
18. **gcp_cud_savings_analysis** - Calculate CUD savings and ROI

NOTE: gcp_cud_utilization has been DEPRECATED (2025-10-28) due to incorrect formula.
      Use gcp_list_commitments instead, which provides accurate utilization metrics.

### 🚀 CUD Analysis Tools - 高级分析 (Advanced Analysis)
20. **gcp_cud_resource_usage** - Resource-level usage (vCPU/Memory/GPU/SSD)
21. **gcp_cud_status_check** - Automated health check with alerts
22. **gcp_cud_vs_ondemand_comparison** - CUD vs on-demand cost scenarios
23. **gcp_flexible_cud_analysis** - Flexible (Spend-based) CUD analysis

**CUD Tools Support:**
- ✅ Project-level and Organization-level queries (billing_account_id)
- ✅ Resource-based CUD and Flexible CUD
- ✅ Automatic data quality handling (excludes recent 2 days)
- ✅ Comprehensive optimization recommendations

## Usage Examples

### Example 1: Get Monthly Cost by Service
```python
result = await get_cost_by_service(
    ctx,
    start_date='2024-01-01',
    end_date='2024-01-31',
    account_id='my-gcp-account'
)
```

### Example 2: Find Idle Resources
```python
result = await get_idle_resources(
    ctx,
    project_id='my-project-123',
    resource_types=['VM', 'DISK', 'IP'],
    account_id='my-gcp-account'
)
```

### Example 3: Get All Cost Optimization Recommendations
```python
result = await get_all_recommendations(
    ctx,
    project_id='my-project-123',
    account_id='my-gcp-account'
)
```

## Multi-Account Support
All tools support the optional `account_id` parameter:
- If provided: Uses credentials for the specified GCP account
- If omitted: Uses default GCP credentials (ADC)

## Data Freshness
- **BigQuery billing export**: 1-6 hour delay for cost data
- **Recommender API**: Updated daily
- **Budgets API**: Real-time

## Error Handling
All tools return a standard response:
```json
{
  "success": true/false,
  "data": {...},
  "account_id": "account-id",
  "message": "Description",
  "error_message": "Error details (if failed)"
}
```

## Troubleshooting

### "BigQuery billing export not configured"
- Enable billing export in GCP Console
- Configure the export table in the GCP account settings
- Wait 24 hours for initial data

### "PermissionDenied" errors
- Check Service Account has required IAM roles
- Verify APIs are enabled in the project

### "Not found" errors for Recommender
- Enable Recommender API
- Wait 24 hours for initial recommendations to generate

## Cost Information
- BigQuery queries: First 1TB/month free, then $5/TB
- Recommender API: Free
- Budgets API: Free
- Typical cost query uses <10 MB of BigQuery processing

## Learn More
- BigQuery Billing Export: https://cloud.google.com/billing/docs/how-to/export-data-bigquery
- Recommender API: https://cloud.google.com/recommender/docs
- Cloud Billing Budgets: https://cloud.google.com/billing/docs/how-to/budgets
"""


# Create FastMCP server instance
mcp = FastMCP(
    name="gcp-billing-cost-management-mcp-server",
    instructions=SERVER_INSTRUCTIONS,
    host="0.0.0.0",
    stateless_http=True,
    port=8000,
)


# ============================================================================
# Register Utility Tools
# ============================================================================


@mcp.tool()
async def get_today_date():
    """Get current date information

    Returns the current date in multiple formats to help the AI assistant understand
    the current time context when processing user queries about "today", "this month",
    "this year", etc.

    Returns:
        dict: Current date information including:
            - date: Current date in YYYY-MM-DD format
            - year: Current year
            - month: Current month (1-12)
            - day: Current day of month
            - year_month: YYYY-MM format
            - formatted: Human-readable date string
    """
    import json
    from datetime import datetime

    now = datetime.now()

    result = {
        "success": True,
        "data": {
            "date": now.strftime("%Y-%m-%d"),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "year_month": now.strftime("%Y-%m"),
            "formatted": now.strftime("%Y年%m月%d日"),
            "iso_format": now.isoformat(),
        },
        "message": f"当前日期: {now.strftime('%Y年%m月%d日')}",
    }

    return json.dumps(result, ensure_ascii=False, default=str)


# ============================================================================
# Register Billing Tools (BigQuery Cost Analysis)
# ============================================================================


@mcp.tool()
async def gcp_cost_by_service(
    start_date: str = None,
    end_date: str = None,
    project_ids: list[str] = None,
    billing_account_id: str = None,
    limit: int = 100,
    account_id: str | None = None,
):
    """Get GCP costs grouped by service

    Query BigQuery billing export to analyze costs by GCP service (Compute Engine,
    Cloud Storage, BigQuery, etc.). Returns top services by cost with credits breakdown.

    **Supports both project-level and organization-level queries.**

    Args:
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        project_ids: Optional list of project IDs to filter
        billing_account_id: Optional billing account ID (for org-level query)
        limit: Maximum number of services to return (default: 100)

    Returns:
        List of services with total_cost, credits, and net_cost
    """
    logger.info(
        f"🎯 gcp_cost_by_service - start={start_date}, end={end_date}, billing_account={billing_account_id}, limit={limit}"
    )
    # Use account ID from environment variable
    import json

    from models import CostByServiceParams

    params = CostByServiceParams(
        start_date=start_date,
        end_date=end_date,
        project_ids=project_ids,
        billing_account_id=billing_account_id,
        limit=limit,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_cost_by_service(None, params)
    logger.info("✅ gcp_cost_by_service - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_cost_by_project(
    start_date: str = None,
    end_date: str = None,
    service_filter: str = None,
    billing_account_id: str = None,
    limit: int = 100,
    account_id: str | None = None,
):
    """Get GCP costs grouped by project

    Analyze costs across GCP projects. Useful for multi-project organizations to track
    per-project spending. Optionally filter by a specific service or billing account.

    **Supports organization-level filtering via billing_account_id.**

    Args:
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        service_filter: Optional service name filter (e.g., 'Compute Engine')
        billing_account_id: Optional billing account ID (for org-level filtering)
        limit: Maximum number of projects to return (default: 100)

    Returns:
        List of projects with costs and service count
    """
    import json

    from models import CostByProjectParams

    params = CostByProjectParams(
        start_date=start_date,
        end_date=end_date,
        service_filter=service_filter,
        billing_account_id=billing_account_id,
        limit=limit,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_cost_by_project(None, params)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_daily_cost_trend(
    start_date: str = None,
    end_date: str = None,
    project_ids: list[str] = None,
    service_filter: str = None,
    account_id: str | None = None,
):
    """Get daily cost trend over time

    Returns daily cost data points for trend analysis and anomaly detection. Useful
    for identifying cost spikes and understanding spending patterns.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        project_ids: Optional list of project IDs to filter
        service_filter: Optional service name filter
        account_id: Optional GCP account ID

    Returns:
        Daily time series with cost, credits, and metadata
    """
    logger.info(f"🎯 gcp_daily_cost_trend - start={start_date}, end={end_date}")
    import json

    from models import DailyCostTrendParams

    params = DailyCostTrendParams(
        start_date=start_date,
        end_date=end_date,
        project_ids=project_ids,
        service_filter=service_filter,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_daily_cost_trend(None, params)
    logger.info("✅ gcp_daily_cost_trend - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_cost_by_label(
    label_key: str,
    start_date: str = None,
    end_date: str = None,
    project_ids: list[str] = None,
    billing_account_id: str = None,
    limit: int = 100,
    account_id: str | None = None,
):
    """Get costs grouped by resource label (cost allocation/chargeback)

    Analyze costs by label values for cost allocation to teams, departments, or
    environments. Requires resources to be labeled (e.g., team:backend, env:prod).

    **Supports both project-level and organization-level queries.**

    Args:
        label_key: Label key to group by (e.g., 'team', 'department', 'env')
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        project_ids: Optional list of project IDs to filter
        billing_account_id: Optional billing account ID (for org-level query)
        limit: Maximum number of label values to return (default: 100)

    Returns:
        Cost breakdown by label value with project and service counts
    """
    import json

    from models import CostByLabelParams

    params = CostByLabelParams(
        label_key=label_key,
        start_date=start_date,
        end_date=end_date,
        project_ids=project_ids,
        billing_account_id=billing_account_id,
        limit=limit,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_cost_by_label(None, params)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_cost_by_sku(
    start_date: str = None,
    end_date: str = None,
    service_filter: str = None,
    project_ids: list[str] = None,
    billing_account_id: str = None,
    limit: int = 50,
    account_id: str | None = None,
):
    """Get detailed costs grouped by SKU

    Provides SKU-level cost details (e.g., 'N1 Predefined Instance Core running in
    Americas'). Useful for understanding exact resource pricing and usage patterns.

    **Supports both project-level and organization-level queries.**

    Args:
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        service_filter: Optional service name filter
        project_ids: Optional list of project IDs to filter
        billing_account_id: Optional billing account ID (for org-level query)
        limit: Maximum number of SKUs to return (default: 50)

    Returns:
        SKU details with cost, usage amount, and usage unit
    """
    import json

    from models import CostBySkuParams

    params = CostBySkuParams(
        start_date=start_date,
        end_date=end_date,
        service_filter=service_filter,
        project_ids=project_ids,
        billing_account_id=billing_account_id,
        limit=limit,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_cost_by_sku(None, params)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_test_simple():
    """Simple test tool to verify MCP communication"""
    logger.info("🧪 Test tool called!")
    return {"success": True, "message": "Test successful", "data": {"value": 42}}


@mcp.tool()
async def gcp_cost_summary(
    start_date: str = None,
    end_date: str = None,
    project_ids: list[str] = None,
    billing_account_id: str = None,
    account_id: str | None = None,
):
    """Get overall cost summary and statistics

    High-level cost overview including total cost, credits, number of services and
    projects, and average daily cost. Perfect for dashboards and reports.

    **Supports both project-level and organization-level summaries.**

    Args:
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        project_ids: Optional list of project IDs to filter
        billing_account_id: Optional billing account ID (for org-level summary)

    Returns:
        Summary statistics with totals, averages, and counts
    """
    import json

    logger.info(f"🎯 gcp_cost_summary - start={start_date}, end={end_date}, projects={project_ids}")

    try:
        # logger.info("📍 Step 1: Getting context...")  # 已静默
        # logger.info("✅ Context obtained")  # 已静默

        # logger.info(f"📍 Step 2: Calling get_cost_summary - account: {DEFAULT_ACCOUNT_ID}")  # 已静默
        from models import CostSummaryParams

        params = CostSummaryParams(
            start_date=start_date,
            end_date=end_date,
            project_ids=project_ids,
            billing_account_id=billing_account_id,
            account_id=account_id or DEFAULT_ACCOUNT_ID,
        )
        result = await get_cost_summary(None, params)
        # logger.info(f"✅ get_cost_summary returned: success={result.get('success')}")  # 已静默

        # logger.info("📍 Step 3: Converting to JSON...")  # 已静默
        json_result = json.dumps(result, ensure_ascii=False, default=str)
        # logger.info(f"✅ JSON created ({len(json_result)} chars)")  # 已静默

        logger.info("✅ gcp_cost_summary - 完成")
        return json_result
    except Exception as e:
        logger.error(f"❌ gcp_cost_summary failed at step: {e}", exc_info=True)
        import traceback

        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        error_result = json.dumps({"success": False, "error_message": str(e), "data": None})
        logger.error("📤 TOOL EXIT: gcp_cost_summary - FAILED", exc_info=True)
        return error_result


# ============================================================================
# Register Recommender Tools (Cost Optimization)
# ============================================================================


@mcp.tool()
async def gcp_vm_rightsizing_recommendations(
    project_id: str,
    location: str = "-",
    max_results: int = None,
    account_id: str | None = None,
):
    """Get VM machine type rightsizing recommendations

    Identifies over-provisioned VMs and suggests smaller machine types to reduce costs
    while maintaining performance. Based on actual CPU/memory usage patterns.

    Args:
        project_id: GCP project ID
        location: Location/region (use '-' for all locations, or specific zone/region)
        max_results: Maximum number of recommendations
        account_id: Optional GCP account ID

    Returns:
        Recommendations with estimated monthly/annual savings
    """
    import json

    from models import VmRightsizingRecommendationsParams

    params = VmRightsizingRecommendationsParams(
        project_id=project_id,
        location=location,
        max_results=max_results,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_vm_rightsizing_recommendations(None, params)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_idle_resources(
    project_id: str,
    resource_types: list[str] = None,
    location: str = "-",
    account_id: str | None = None,
):
    """Get idle resource recommendations (VMs, disks, IPs)

    Identifies resources with zero or minimal usage that can be deleted to save costs.
    Checks VMs, persistent disks, and static IP addresses.

    Args:
        project_id: GCP project ID
        resource_types: List of types to check: 'VM', 'DISK', 'IP' (default: all)
        location: Location (use '-' for all)
        account_id: Optional GCP account ID

    Returns:
        Idle resources by type with potential savings
    """
    import json

    from models import IdleResourcesParams

    params = IdleResourcesParams(
        project_id=project_id,
        resource_types=resource_types,
        location=location,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_idle_resources(None, params)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_commitment_recommendations(
    project_id: str = None,
    billing_account_id: str = None,
    location: str = "-",
    account_id: str | None = None,
):
    """Get Committed Use Discounts (CUD) purchase recommendations

    Suggests purchasing 1-year or 3-year commitments for predictable workloads to save
    up to 57% compared to on-demand pricing. Based on usage patterns.

    **Supports both project-level and organization-level queries.**

    Args:
        project_id: GCP project ID (for single project query). Optional.
        billing_account_id: Billing account ID (for org-level query across all projects). Optional.
        location: Location (use '-' for all). Optional.

    Returns:
        CUD recommendations with estimated savings

    ⚠️ IMPORTANT PARAMETER USAGE:
        1. When user mentions "billing account" or "organization" or "all projects":
           → DO NOT pass any parameters (let the tool use smart defaults)
           → DO NOT pass project_id
           → DO NOT pass billing_account_id="null"

        2. When user mentions a specific project name:
           → ONLY pass project_id="the-project-name"

        3. Smart defaults (when no parameters provided):
           → Tool automatically uses the account's billing_account_id
           → This queries ALL projects under the billing account

        4. DO NOT pass string "null" or "None" - just omit the parameter

    Example Usage:
        User: "Get CUD recommendations for billing account"
        → Call: gcp_commitment_recommendations() (no parameters!)

        User: "Show CUD recommendations for project my-gcp-project"
        → Call: gcp_commitment_recommendations(project_id="my-gcp-project")

        User: "List all CUD recommendations"
        → Call: gcp_commitment_recommendations() (no parameters!)

    ⚠️ NOTE: Requires recommender.googleapis.com API to be enabled and
             Service Account to have roles/recommender.viewer permission.
    """
    import json

    result = await get_commitment_recommendations(
        None, project_id, billing_account_id, location, account_id or DEFAULT_ACCOUNT_ID
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_all_cost_recommendations(
    project_id: str = None,
    billing_account_id: str = None,
    location: str = "-",
    account_id: str | None = None,
):
    """Get all cost optimization recommendations across all types

    Aggregates VM rightsizing, idle resources, and CUD recommendations into a single
    response. Provides total potential savings across all recommendation types.

    **Supports both project-level and organization-level queries.**

    Args:
        project_id: GCP project ID (for single project query). Optional.
        billing_account_id: Billing account ID (for org-level query across all projects). Optional.
        location: Location (use '-' for all). Optional.

    Returns:
        All recommendations grouped by type with total savings

    ⚠️ IMPORTANT PARAMETER USAGE:
        Same as gcp_commitment_recommendations - supports smart defaults.
        Will automatically use billing_account_id from account config if not specified.

    ⚠️ NOTE: Requires recommender.googleapis.com API to be enabled and
             Service Account to have roles/recommender.viewer permission.
    """
    import json

    result = await get_all_recommendations(
        None, project_id, billing_account_id, location, account_id or DEFAULT_ACCOUNT_ID
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_mark_recommendation_status(
    recommendation_name: str,
    state: str,
    state_metadata: dict = None,
    account_id: str | None = None,
):
    """Mark recommendation status (track implementation)

    Update recommendation state to track which recommendations have been applied,
    dismissed, or failed. Helps maintain recommendation history.

    Args:
        recommendation_name: Full recommendation name (from list/get operations)
        state: New state: 'CLAIMED', 'SUCCEEDED', 'FAILED', or 'DISMISSED'
        state_metadata: Optional metadata dict
        account_id: Optional GCP account ID

    Returns:
        Updated recommendation status
    """
    return await mark_recommendation_status(
        None, recommendation_name, state, state_metadata, account_id or DEFAULT_ACCOUNT_ID
    )


# ============================================================================
# Register Budget Tools
# ============================================================================


@mcp.tool()
async def gcp_list_budgets(
    billing_account_id: str = None,
    account_id: str | None = None,
):
    """List all budgets for a billing account

    Retrieves all configured budgets with their thresholds and alert settings.

    Args:
        billing_account_id: GCP billing account ID (e.g., '012345-6789AB-CDEF01')
                           If not provided, uses account metadata
        account_id: Optional GCP account ID

    Returns:
        List of budgets with amounts, thresholds, and filters
    """
    return await list_budgets(None, billing_account_id, account_id or DEFAULT_ACCOUNT_ID)


@mcp.tool()
async def gcp_get_budget_status(
    budget_name: str,
    account_id: str | None = None,
):
    """Get budget details and status

    Retrieves detailed information about a specific budget.

    Args:
        budget_name: Full budget name (e.g., 'billingAccounts/123/budgets/456')
        account_id: Optional GCP account ID

    Returns:
        Budget details with amount, thresholds, and filter settings
    """
    import json

    result = await get_budget_status(None, budget_name, account_id or DEFAULT_ACCOUNT_ID)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_create_budget(
    billing_account_id: str,
    display_name: str,
    amount: float,
    currency_code: str = "USD",
    project_ids: list[str] = None,
    threshold_percents: list[float] = None,
    account_id: str | None = None,
):
    """Create a new budget with alert thresholds

    Creates a monthly budget with customizable alert thresholds (e.g., at 50%, 90%, 100%).

    Args:
        billing_account_id: GCP billing account ID
        display_name: Budget display name
        amount: Monthly budget amount
        currency_code: Currency code (default: USD)
        project_ids: Optional list of project IDs to apply budget to
        threshold_percents: Alert thresholds (default: [0.5, 0.75, 0.9, 1.0])
        account_id: Optional GCP account ID

    Returns:
        Created budget information
    """
    import json

    from models import CreateBudgetParams

    params = CreateBudgetParams(
        billing_account_id=billing_account_id,
        display_name=display_name,
        amount=amount,
        currency_code=currency_code,
        project_ids=project_ids,
        threshold_percents=threshold_percents,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await create_budget(None, params)
    return json.dumps(result, ensure_ascii=False, default=str)


# ============================================================================
# Register CUD (Committed Use Discounts) Tools
# ============================================================================


@mcp.tool()
async def gcp_list_commitments(
    project_id: str = None,
    billing_account_id: str = None,
    region: str = None,
    status_filter: str = None,
    account_id: str | None = None,
):
    """List GCP CUD commitments with UTILIZATION and COVERAGE metrics

    ✅ **USE THIS TOOL WHEN USER ASKS FOR:**
    - "CUD 覆盖率" or "coverage"
    - "CUD 利用率" or "utilization"
    - "按项目查询 CUD" or "CUD by project"
    - Any CUD-related metrics or analysis

    ✅ **RETURNS (for each project+region):**
    - Commitment details (cost, term, resource type)
    - **commitment_cost** (承诺成本): Amount you pay for the commitment
    - **utilization_percentage** (利用率): How much of commitment is used (0-100%)
    - **unused_commitment** (浪费金额): Wasted cost = commitment_cost × (1 - utilization)
    - **Coverage percentage** (覆盖率): How much eligible usage is covered by CUD
    - **status** (状态): ACTIVE, PARTIAL, EXPIRED
    - Boolean flags (is_fully_utilized, is_insufficient)

    🚨 **DISPLAY REQUIREMENT - MUST FOLLOW:**
    When showing CUD data, you MUST display these fields together in a table:
    - commitment_cost (承诺成本)
    - utilization_percentage (利用率)
    - unused_commitment (浪费金额)
    - status (状态)

    Why? Only showing utilization% is misleading:
    - Project A: $10 commitment, 0% utilization → $10 wasted (small issue)
    - Project B: $10,000 commitment, 0% utilization → $10,000 wasted (critical!)

    Both have 0% utilization, but the impact is completely different!

    **Supports both project-level and organization-level queries.**

    Args:
        project_id: GCP project ID (for single project query). Optional.
        billing_account_id: Billing account ID (for org-level query across all projects). Optional.
        region: Specific region (e.g., 'us-central1') or None for all regions. Optional.
        status_filter: Filter by status (ACTIVE, EXPIRED, CANCELED, CREATING). Optional.

    Returns:
        List of commitments with utilization, coverage, and optimization details

    ⚠️ IMPORTANT PARAMETER USAGE:
        1. When user mentions "billing account" or "organization" or "all projects":
           → DO NOT pass any parameters (let the tool use smart defaults)
           → DO NOT pass project_id
           → DO NOT pass billing_account_id="null"

        2. When user mentions a specific project name:
           → ONLY pass project_id="the-project-name"

        3. Smart defaults (when no parameters provided):
           → Tool automatically uses the account's billing_account_id
           → This queries ALL projects under the billing account

        4. DO NOT pass string "null" or "None" - just omit the parameter

    Example Usage:
        User: "List CUD commitments for billing account"
        → Call: gcp_list_commitments() (no parameters!)

        User: "Show CUD for project my-gcp-project"
        → Call: gcp_list_commitments(project_id="my-gcp-project")

        User: "List all CUD commitments"
        → Call: gcp_list_commitments() (no parameters!)
    """
    import json

    from models import ListCommitmentsParams

    logger.info(
        f"🎯 gcp_list_commitments - project={project_id}, billing_account={billing_account_id}, region={region}, status={status_filter}"
    )
    params = ListCommitmentsParams(
        project_id=project_id,
        billing_account_id=billing_account_id,
        region=region,
        status_filter=status_filter,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await list_commitments(None, params)
    logger.info("✅ gcp_list_commitments - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


# ❌ DEPRECATED: gcp_cud_utilization 工具已废弃
# 原因: 计算公式错误，utilization = cud_credits / commitment_cost 导致结果>100%
# 问题: 分子是按需价格，分母是折扣价格，单位不统一
# 替代: 使用 gcp_list_commitments，它提供准确的利用率计算
# 日期: 2025-10-28
#
# @mcp.tool()
# async def gcp_cud_utilization(
#     project_id: str = None,
#     billing_account_id: str = None,
#     start_date: str = None,
#     end_date: str = None,
#     granularity: str = "DAILY",
#     region: str = None
# ):
#     """Get CUD utilization analysis (similar to AWS RI Utilization)
#
#     Analyzes how much of your purchased CUD commitments are being utilized.
#     Shows utilization percentage, unused commitment costs, and time-series breakdown.
#
#     **Supports both project-level and organization-level queries.**
#
#     **Important**: Data excludes last 2 days due to CUD credit attribution delay.
#
#     Args:
#         project_id: GCP project ID (for single project query)
#         billing_account_id: Billing account ID (for org-level query)
#         start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
#         end_date: End date in YYYY-MM-DD format (default: 2 days ago)
#         granularity: DAILY or MONTHLY aggregation
#         region: Filter by specific region (e.g., 'us-central1')
#
#     Returns:
#         Utilization summary with percentage, unused commitment, and daily/monthly breakdown
#
#     Example Usage:
#         "What's our CUD utilization for project X this month?"
#         "Show daily CUD utilization for us-central1 in October"
#     """
#     import json
#     logger.info(f"🎯 gcp_cud_utilization - project={project_id}, billing_account={billing_account_id}, {start_date} to {end_date}")
#     result = await get_cud_utilization(None, project_id, billing_account_id, start_date, end_date, granularity, region, DEFAULT_ACCOUNT_ID)
#     logger.info(f"✅ gcp_cud_utilization - 完成")
#     return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_cud_coverage(
    project_id: str = None,
    billing_account_id: str = None,
    start_date: str = None,
    end_date: str = None,
    granularity: str = "DAILY",
    service_filter: str = "Compute Engine",
    region: str = None,
    account_id: str | None = None,
):
    """Get CUD coverage analysis (similar to AWS RI Coverage)

    Analyzes what percentage of your eligible usage is covered by CUD commitments
    vs running at on-demand rates. Helps identify opportunities to increase CUD coverage.

    **Supports both project-level and organization-level queries.**

    **Important**: Data excludes last 2 days due to billing lag.

    Args:
        project_id: GCP project ID (for single project query)
        billing_account_id: Billing account ID (for org-level query)
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: 2 days ago)
        granularity: DAILY or MONTHLY aggregation
        service_filter: Service to analyze (default: Compute Engine)
        region: Filter by specific region

    Returns:
        Coverage summary with percentage, on-demand costs, and time-series data

    Example Usage:
        "What's our CUD coverage for Compute Engine?"
        "How much usage is running on-demand vs covered by CUDs?"
    """
    import json

    from models import CudCoverageParams

    logger.info(
        f"🎯 gcp_cud_coverage - project={project_id}, billing_account={billing_account_id}, service={service_filter}"
    )
    params = CudCoverageParams(
        project_id=project_id,
        billing_account_id=billing_account_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        service_filter=service_filter,
        region=region,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_cud_coverage(None, params)
    logger.info("✅ gcp_cud_coverage - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_cud_savings_analysis(
    project_id: str = None,
    billing_account_id: str = None,
    start_date: str = None,
    end_date: str = None,
    granularity: str = "MONTHLY",
    account_id: str | None = None,
):
    """Analyze cost savings from CUD commitments

    Calculates actual savings achieved by using CUDs vs on-demand pricing.
    Shows ROI of commitment purchases and net savings over time.

    **Supports both project-level and organization-level queries.**

    Args:
        project_id: GCP project ID (for single project query)
        billing_account_id: Billing account ID (for org-level query)
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: 2 days ago)
        granularity: DAILY or MONTHLY aggregation

    Returns:
        Savings summary with net savings, ROI percentage, and period breakdown

    Example Usage:
        "How much money are we saving with CUDs?"
        "Show me the ROI on our CUD commitments for the entire organization"
    """
    import json

    from models import CudSavingsAnalysisParams

    logger.info(
        f"🎯 gcp_cud_savings_analysis - project={project_id}, billing_account={billing_account_id}"
    )
    params = CudSavingsAnalysisParams(
        project_id=project_id,
        billing_account_id=billing_account_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        account_id=account_id or DEFAULT_ACCOUNT_ID,
    )
    result = await get_cud_savings_analysis(None, params)
    logger.info("✅ gcp_cud_savings_analysis - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


# ============================================================================
# ============================================================================
# Register CUD Advanced Analysis Tools
# ============================================================================
# ============================================================================


@mcp.tool()
async def gcp_cud_resource_usage(
    project_id: str = None,
    billing_account_id: str = None,
    start_date: str = None,
    end_date: str = None,
    resource_type: str = None,
    region: str = None,
    granularity: str = "DAILY",
    account_id: str | None = None,
):
    """Analyze CUD usage by resource type (vCPU, Memory, GPU, SSD)

    Provides detailed analysis of CUD usage at resource type level to identify
    which resource types are underutilized. Helps optimize commitment configurations.

    **Supports organization-level queries** via billing_account_id.

    Args:
        project_id: GCP project ID (for project-level query)
        billing_account_id: Billing account ID (for org-level query)
        start_date: Start date YYYY-MM-DD (default: 30 days ago)
        end_date: End date YYYY-MM-DD (default: 2 days ago)
        resource_type: Filter by VCPU, MEMORY, GPU, LOCAL_SSD, or ALL
        region: Filter by region
        granularity: DAILY or MONTHLY

    Returns:
        Resource-level usage with utilization percentages and optimization recommendations

    Example Usage:
        "Show me GPU utilization in our CUD commitments"
        "Analyze resource usage across all commitments for project X"
        "Check if we're wasting any resource types"
    """
    import json

    logger.info(
        f"🎯 gcp_cud_resource_usage - project={project_id}, billing_account={billing_account_id}"
    )
    result = await get_cud_resource_usage(
        None,
        project_id,
        billing_account_id,
        start_date,
        end_date,
        resource_type,
        region,
        granularity,
        account_id or DEFAULT_ACCOUNT_ID,
    )
    logger.info("✅ gcp_cud_resource_usage - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_cud_status_check(
    project_id: str = None,
    billing_account_id: str = None,
    utilization_threshold: float = 80.0,
    coverage_threshold: float = 75.0,
    days_before_expiry: int = 30,
    account_id: str | None = None,
):
    """Perform comprehensive CUD health check with alerts

    Automatically checks CUD status across multiple dimensions:
    - Utilization levels
    - Coverage percentages
    - Expiring commitments
    - Cost efficiency

    Generates actionable alerts and optimization recommendations.

    **Supports organization-level health checks** via billing_account_id.

    Args:
        project_id: GCP project ID
        billing_account_id: Billing account ID (org-level)
        utilization_threshold: Alert if below this % (default: 80)
        coverage_threshold: Alert if below this % (default: 75)
        days_before_expiry: Alert N days before expiry (default: 30)

    Returns:
        Health status report with alerts, checks, and recommendations

    Example Usage:
        "Perform CUD health check for project X"
        "Check if any of our commitments are expiring soon"
        "Are there any CUD optimization opportunities?"
    """
    import json

    logger.info(
        f"🎯 gcp_cud_status_check - project={project_id}, billing_account={billing_account_id}"
    )
    result = await get_cud_status_check(
        None,
        project_id,
        billing_account_id,
        utilization_threshold,
        coverage_threshold,
        days_before_expiry,
        account_id or DEFAULT_ACCOUNT_ID,
    )
    logger.info("✅ gcp_cud_status_check - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_cud_vs_ondemand_comparison(
    project_id: str = None,
    billing_account_id: str = None,
    start_date: str = None,
    end_date: str = None,
    scenario: str = "actual",
    account_id: str | None = None,
):
    """Compare CUD costs vs on-demand pricing with scenarios

    Provides cost comparison across multiple scenarios:
    - **actual**: Current situation with CUD
    - **no_cud**: Hypothetical scenario without CUD (proves CUD value)
    - **optimal**: Optimized CUD configuration

    Perfect for justifying CUD investments and decision-making.

    **Supports organization-level analysis** via billing_account_id.

    Args:
        project_id: GCP project ID
        billing_account_id: Billing account ID (org-level)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        scenario: Scenario type (actual, no_cud, optimal)

    Returns:
        Detailed cost comparison with savings analysis and recommendations

    Example Usage:
        "How much would we spend without CUDs?"
        "Compare our actual costs vs optimal CUD configuration"
        "Justify our CUD investment with cost comparison"
    """
    import json

    logger.info(f"🎯 gcp_cud_vs_ondemand_comparison - scenario={scenario}")
    result = await get_cud_vs_ondemand_comparison(
        None,
        project_id,
        billing_account_id,
        start_date,
        end_date,
        scenario,
        account_id or DEFAULT_ACCOUNT_ID,
    )
    logger.info("✅ gcp_cud_vs_ondemand_comparison - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def gcp_flexible_cud_analysis(
    project_id: str = None,
    billing_account_id: str = None,
    start_date: str = None,
    end_date: str = None,
    granularity: str = "MONTHLY",
    account_id: str | None = None,
):
    """Analyze Flexible (Spend-based) CUD usage

    Provides detailed analysis of Flexible CUD commitments including:
    - Subscription details and terms
    - Service-level spend breakdown
    - Utilization across services
    - Comparison with Resource-based CUD

    Helps decide between Flexible and Resource-based CUD types.

    **Supports organization-level analysis** via billing_account_id.

    Args:
        project_id: GCP project ID
        billing_account_id: Billing account ID (org-level)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        granularity: DAILY or MONTHLY

    Returns:
        Flexible CUD analysis with service breakdown and type comparison

    Example Usage:
        "Analyze our Flexible CUD usage"
        "Should we convert to Resource-based CUDs?"
        "Show me which services are using Flexible CUD credits"
    """
    import json

    logger.info(
        f"🎯 gcp_flexible_cud_analysis - project={project_id}, billing_account={billing_account_id}"
    )
    result = await get_flexible_cud_analysis(
        None,
        project_id,
        billing_account_id,
        start_date,
        end_date,
        granularity,
        account_id or DEFAULT_ACCOUNT_ID,
    )
    logger.info("✅ gcp_flexible_cud_analysis - 完成")
    return json.dumps(result, ensure_ascii=False, default=str)


# ============================================================================
# Server Initialization
# ============================================================================


def main():
    """Run the MCP server with streamable HTTP transport for AgentCore."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
