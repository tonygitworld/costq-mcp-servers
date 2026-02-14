# GCP Billing Cost Management MCP Server

A comprehensive Model Context Protocol (MCP) server for Google Cloud Platform cost analysis, optimization, and budget management.

## 🌟 Features

### 📊 Cost Analysis (6 Tools)
- **Cost by Service**: Breakdown costs by GCP services (Compute Engine, Cloud Storage, etc.)
- **Cost by Project**: Multi-project cost tracking and allocation
- **Daily Cost Trend**: Time-series cost data for trend analysis and anomaly detection
- **Cost by Label**: Cost allocation by labels (team, department, environment)
- **Cost by SKU**: Detailed SKU-level cost breakdown
- **Cost Summary**: Overall cost statistics and summaries

### 💡 Cost Optimization (5 Tools)
- **VM Rightsizing**: Recommendations for over-provisioned VMs
- **Idle Resources**: Identify idle VMs, disks, and IP addresses
- **CUD Recommendations**: Committed Use Discounts purchase recommendations
- **All Recommendations**: Aggregated view of all optimization opportunities
- **Recommendation Tracking**: Mark recommendations as claimed/succeeded/failed/dismissed

### 💰 Budget Management (3 Tools)
- **List Budgets**: View all budgets for a billing account
- **Budget Status**: Get detailed budget information
- **Create Budget**: Create new budgets with customizable thresholds

## 📋 Prerequisites

### 1. BigQuery Billing Export (Required for cost queries)

Enable BigQuery billing export in GCP Console:

1. Navigate to **Billing → Billing export → BigQuery export**
2. Enable **"Detailed usage cost data"**
3. Select or create a BigQuery dataset (e.g., `billing_export`)
4. Click **Save**

**Note**: Data appears ~24 hours after enabling.

**Learn more**: https://cloud.google.com/billing/docs/how-to/export-data-bigquery

### 2. Service Account Permissions

Required IAM roles for the Service Account:

```bash
# View billing accounts and billing data
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/billing.viewer"

# Read BigQuery billing export data
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/bigquery.dataViewer"

# Execute BigQuery queries
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/bigquery.jobUser"

# View cost optimization recommendations
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/recommender.viewer"

# Manage budgets (optional, only if creating budgets)
gcloud projects add-iam-policy-binding BILLING_ACCOUNT \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/billing.costsManager"
```

Replace `PROJECT_ID` and `SA_EMAIL` with your values.

### 3. Enable Required APIs

```bash
gcloud services enable bigquery.googleapis.com
gcloud services enable recommender.googleapis.com
gcloud services enable cloudbilling.googleapis.com
gcloud services enable billingbudgets.googleapis.com
```

## 🚀 Installation

### Dependencies

```bash
pip install google-cloud-bigquery>=3.14.1
pip install google-cloud-recommender>=2.17.0
pip install google-cloud-billing-budgets>=1.16.0
pip install mcp
```

Or use the project's `requirements.txt`:

```bash
pip install -r requirements.txt
```

## 📖 Usage

### Standalone Server

Run the server directly:

```bash
python server.py
```

### Integration with Strands Agent

The server is deployed as a Gateway MCP runtime and accessed via AgentCore Gateway.

### Multi-Account Support

All tools support the optional `account_id` parameter:

```python
# Use specific account
result = await gcp_cost_by_service(
    start_date='2024-01-01',
    end_date='2024-01-31',
    account_id='my-gcp-account'
)

# Use default credentials (ADC)
result = await gcp_cost_by_service(
    start_date='2024-01-01',
    end_date='2024-01-31'
)
```

## 📊 Tool Reference

### Cost Analysis Tools

#### `gcp_cost_by_service`
Get costs grouped by GCP service.

**Parameters**:
- `start_date` (optional): Start date in YYYY-MM-DD format (default: 30 days ago)
- `end_date` (optional): End date in YYYY-MM-DD format (default: today)
- `project_ids` (optional): List of project IDs to filter
- `limit` (optional): Maximum number of results (default: 100)
- `account_id` (optional): GCP account ID

**Example**:
```python
result = await gcp_cost_by_service(
    start_date='2024-01-01',
    end_date='2024-01-31'
)
```

#### `gcp_cost_by_project`
Get costs grouped by project.

**Parameters**:
- `start_date` (optional): Start date
- `end_date` (optional): End date
- `service_filter` (optional): Service name to filter (e.g., 'Compute Engine')
- `limit` (optional): Maximum results
- `account_id` (optional): GCP account ID

#### `gcp_daily_cost_trend`
Get daily cost time series.

**Parameters**:
- `start_date` (optional): Start date
- `end_date` (optional): End date
- `project_ids` (optional): Project IDs to filter
- `service_filter` (optional): Service name to filter
- `account_id` (optional): GCP account ID

#### `gcp_cost_by_label`
Get costs grouped by label (cost allocation).

**Parameters**:
- `label_key` (required): Label key (e.g., 'team', 'env', 'department')
- `start_date` (optional): Start date
- `end_date` (optional): End date
- `project_ids` (optional): Project IDs to filter
- `limit` (optional): Maximum results
- `account_id` (optional): GCP account ID

#### `gcp_cost_by_sku`
Get detailed SKU-level cost breakdown.

**Parameters**:
- `start_date` (optional): Start date
- `end_date` (optional): End date
- `service_filter` (optional): Service name to filter
- `project_ids` (optional): Project IDs to filter
- `limit` (optional): Maximum results (default: 50)
- `account_id` (optional): GCP account ID

#### `gcp_cost_summary`
Get overall cost summary.

**Parameters**:
- `start_date` (optional): Start date
- `end_date` (optional): End date
- `project_ids` (optional): Project IDs to filter
- `account_id` (optional): GCP account ID

### Cost Optimization Tools

#### `gcp_vm_rightsizing_recommendations`
Get VM machine type rightsizing recommendations.

**Parameters**:
- `project_id` (required): GCP project ID
- `location` (optional): Location (use '-' for all, default: '-')
- `max_results` (optional): Maximum recommendations
- `account_id` (optional): GCP account ID

#### `gcp_idle_resources`
Identify idle VMs, disks, and IP addresses.

**Parameters**:
- `project_id` (required): GCP project ID
- `resource_types` (optional): List of types ['VM', 'DISK', 'IP'] (default: all)
- `location` (optional): Location (default: '-')
- `account_id` (optional): GCP account ID

#### `gcp_commitment_recommendations`
Get Committed Use Discounts (CUD) purchase recommendations.

**Parameters**:
- `project_id` (required): GCP project ID
- `location` (optional): Location (default: '-')
- `account_id` (optional): GCP account ID

#### `gcp_all_cost_recommendations`
Get all optimization recommendations across all types.

**Parameters**:
- `project_id` (required): GCP project ID
- `location` (optional): Location (default: '-')
- `account_id` (optional): GCP account ID

#### `gcp_mark_recommendation_status`
Mark recommendation status for tracking.

**Parameters**:
- `recommendation_name` (required): Full recommendation name
- `state` (required): New state ('CLAIMED', 'SUCCEEDED', 'FAILED', 'DISMISSED')
- `state_metadata` (optional): Metadata dict
- `account_id` (optional): GCP account ID

### Budget Management Tools

#### `gcp_list_budgets`
List all budgets for a billing account.

**Parameters**:
- `billing_account_id` (optional): Billing account ID
- `account_id` (optional): GCP account ID

#### `gcp_get_budget_status`
Get budget details.

**Parameters**:
- `budget_name` (required): Full budget name
- `account_id` (optional): GCP account ID

#### `gcp_create_budget`
Create a new budget.

**Parameters**:
- `billing_account_id` (required): Billing account ID
- `display_name` (required): Budget name
- `amount` (required): Monthly budget amount
- `currency_code` (optional): Currency (default: 'USD')
- `project_ids` (optional): Project IDs to apply budget to
- `threshold_percents` (optional): Alert thresholds (default: [0.5, 0.75, 0.9, 1.0])
- `account_id` (optional): GCP account ID

## ⚡ Performance

### BigQuery Costs
- **Free Tier**: First 1 TB/month of query processing
- **Pricing**: $5 per TB after free tier
- **Typical Query**: <10 MB of data processed
- **Monthly estimate**: Most users stay within free tier

### Data Freshness
- **BigQuery billing export**: 1-6 hour delay
- **Recommender API**: Updated daily
- **Budgets API**: Real-time

## 🔧 Troubleshooting

### "BigQuery billing export not configured"
1. Enable billing export in GCP Console
2. Configure export table in account settings
3. Wait 24 hours for initial data

### "PermissionDenied" errors
1. Verify Service Account has required IAM roles
2. Check that APIs are enabled
3. Ensure billing account permissions for budget operations

### "Not found" errors for Recommender
1. Enable Recommender API in project
2. Wait 24 hours for initial recommendations to generate
3. Verify project has resources (VMs, disks, etc.)

### No cost data returned
1. Verify BigQuery export is configured correctly
2. Check that billing data exists for the date range
3. Ensure Service Account has `bigquery.dataViewer` role
4. Verify the correct table name is configured

## 📚 Learn More

- [BigQuery Billing Export](https://cloud.google.com/billing/docs/how-to/export-data-bigquery)
- [Recommender API Documentation](https://cloud.google.com/recommender/docs)
- [Cloud Billing Budgets](https://cloud.google.com/billing/docs/how-to/budgets)
- [IAM Permissions Reference](https://cloud.google.com/iam/docs/permissions-reference)

## 🤝 Contributing

Contributions are welcome! Please follow the existing code patterns and add tests for new features.

## 📄 License

This project is part of costq-agents and follows the same license.

## 🙏 Acknowledgments

Built with:
- [mcp](https://github.com/modelcontextprotocol/python-sdk) - MCP server framework
- [Google Cloud Python SDK](https://github.com/googleapis/google-cloud-python) - GCP API clients
