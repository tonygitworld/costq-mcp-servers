"""
GCP Cost Management MCP Server - Constants and Configuration

Defines all constants, enums, and configuration values for the GCP Cost MCP Server.
"""

# GCP Service Names Mapping
GCP_SERVICES = {
    "billing": "cloudbilling.googleapis.com",
    "bigquery": "bigquery.googleapis.com",
    "recommender": "recommender.googleapis.com",
    "budgets": "billingbudgets.googleapis.com",
    "resource_manager": "cloudresourcemanager.googleapis.com",
}

# Recommender Types for Cost Optimization
RECOMMENDER_TYPES = {
    # Compute Engine Recommenders
    "IDLE_VM": "google.compute.instance.IdleResourceRecommender",
    "VM_RIGHTSIZING": "google.compute.instance.MachineTypeRecommender",
    "IDLE_DISK": "google.compute.disk.IdleResourceRecommender",
    "SNAPSHOT_SCHEDULE": "google.compute.disk.SnapshotScheduleRecommender",
    "IDLE_IP": "google.compute.address.IdleResourceRecommender",
    "COMMITMENT": "google.compute.commitment.UsageCommitmentRecommender",
    # Cloud SQL Recommenders
    "IDLE_CLOUDSQL": "google.cloudsql.instance.IdleRecommender",
    "OVERPROVISIONED_CLOUDSQL": "google.cloudsql.instance.OverprovisionedRecommender",
    # BigQuery Recommenders
    "BIGQUERY_CAPACITY": "google.bigquery.capacityCommitments.Recommender",
    # Cloud Run Recommenders
    "CLOUD_RUN_CPU": "google.run.service.CostRecommender",
    # Logging Recommenders
    "LOGGING_OPTIMIZATION": "google.logging.productSuggestion.LoggingOptimization",
}

# Recommender States
RECOMMENDER_STATES = {
    "ACTIVE": "Active recommendations",
    "CLAIMED": "User marked as planned to implement",
    "SUCCEEDED": "Successfully applied",
    "FAILED": "Application failed",
    "DISMISSED": "User dismissed the recommendation",
}

# BigQuery Default Configuration
BIGQUERY_DEFAULTS = {
    "dataset_name": "billing_export",
    "table_prefix": "gcp_billing_export_resource_v1_",
    "standard_table_prefix": "gcp_billing_export_v1_",
    "max_scan_bytes": 10 * 1024 * 1024 * 1024,  # 10 GB default limit
    "query_timeout_seconds": 60,
}

# Cost Query Default Values
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MAX_RESULTS = 100
DEFAULT_CURRENCY_CODE = "USD"

# Date Format Patterns
DATE_FORMAT_BIGQUERY = "%Y-%m-%d"  # For BigQuery WHERE clauses
DATE_FORMAT_ISO = "%Y-%m-%dT%H:%M:%SZ"  # ISO 8601

# Error Messages (English & Chinese)
ERROR_MESSAGES = {
    "BIGQUERY_NOT_CONFIGURED": {
        "en": "BigQuery billing export not configured",
        "zh": "BigQuery 账单导出未配置",
    },
    "INVALID_DATE_RANGE": {"en": "Invalid date range provided", "zh": "提供的日期范围无效"},
    "API_CALL_FAILED": {"en": "GCP API call failed", "zh": "GCP API 调用失败"},
    "INSUFFICIENT_PERMISSIONS": {"en": "Insufficient GCP permissions", "zh": "GCP 权限不足"},
    "ACCOUNT_NOT_FOUND": {"en": "GCP account not found", "zh": "GCP 账号未找到"},
    "BIGQUERY_QUERY_ERROR": {
        "en": "BigQuery query execution failed",
        "zh": "BigQuery 查询执行失败",
    },
}

# Success Messages
SUCCESS_MESSAGES = {
    "COST_QUERY_SUCCESS": {"en": "Cost data retrieved successfully", "zh": "成本数据检索成功"},
    "RECOMMENDATIONS_RETRIEVED": {
        "en": "Cost optimization recommendations retrieved successfully",
        "zh": "成本优化建议检索成功",
    },
    "BUDGET_RETRIEVED": {
        "en": "Budget information retrieved successfully",
        "zh": "预算信息检索成功",
    },
}

# API Quotas (for reference and monitoring)
API_QUOTAS = {
    "cloud_billing": {
        "requests_per_minute": 300,
        "cost_per_request": 0.0,  # Free
    },
    "bigquery": {
        "free_tier_tb_per_month": 1.0,
        "cost_per_tb": 5.0,  # $5 per TB
        "first_10gb_storage_free": True,
        "storage_cost_per_gb_month": 0.02,
    },
    "recommender": {
        "requests_per_minute": 1000,
        "cost_per_request": 0.0,  # Free
    },
    "budgets": {
        "read_requests_per_minute": 800,
        "write_requests_per_minute": 100,
        "max_budgets_per_billing_account": 50000,
    },
}

# Retry Configuration
RETRY_CONFIG = {
    "max_attempts": 3,
    "backoff_factor": 2,
    "initial_delay": 1,  # seconds
    "non_retryable_errors": ["PermissionDenied", "InvalidArgument", "NotFound", "AlreadyExists"],
}

# BigQuery Table Schema Fields (for validation)
BILLING_EXPORT_REQUIRED_FIELDS = [
    "billing_account_id",
    "service",
    "sku",
    "project",
    "cost",
    "currency",
    "usage",
]

# Cost Analysis Group By Options
COST_GROUP_BY_OPTIONS = {
    "service": "service.description",
    "project": "project.id",
    "sku": "sku.description",
    "region": "location.region",
    "label": "labels",
    "resource": "resource.name",
}

# Budget Alert Thresholds (common values)
BUDGET_ALERT_THRESHOLDS = [0.5, 0.75, 0.9, 1.0]  # 50%, 75%, 90%, 100%

# Anomaly Detection Configuration
ANOMALY_DETECTION_CONFIG = {
    "z_score_threshold": 2.0,  # Standard deviations
    "min_data_points": 7,  # Minimum 7 days of data
    "lookback_days": 60,  # Analyze last 60 days for statistical baseline
}

# Cache Configuration (for query results caching)
CACHE_CONFIG = {
    "cost_data_ttl_seconds": 3600,  # 1 hour (data has 1-6 hour lag anyway)
    "recommendations_ttl_seconds": 86400,  # 24 hours
    "budgets_ttl_seconds": 300,  # 5 minutes
    "pricing_ttl_seconds": 604800,  # 7 days (pricing rarely changes)
}

# Required IAM Roles
REQUIRED_IAM_ROLES = {
    "billing.viewer": "View billing accounts and billing data",
    "bigquery.dataViewer": "Read BigQuery billing export data",
    "bigquery.jobUser": "Execute BigQuery queries",
    "recommender.viewer": "View cost optimization recommendations",
    "resourcemanager.projectViewer": "View project metadata",
}

# Optional IAM Roles (for advanced features)
OPTIONAL_IAM_ROLES = {
    "billing.costsManager": "Manage budgets (required for budget creation)",
    "recommender.gcpIamPolicyWriter": "Mark recommendations as succeeded/failed",
}

# GCP Billing Export Setup Instructions (for error messages)
BILLING_EXPORT_SETUP_INSTRUCTIONS = """
To enable BigQuery billing export:

1. Open GCP Console → Billing → Billing export
2. Click on "BigQuery export" tab
3. Enable "Detailed usage cost data" (recommended)
4. Select or create a BigQuery dataset (e.g., 'billing_export')
5. Click "Save"

After configuration, data will be available within 24 hours.
Table name format: gcp_billing_export_resource_v1_{BILLING_ACCOUNT_ID}

For more details, visit:
https://cloud.google.com/billing/docs/how-to/export-data-bigquery
"""

# Service Account Permission Setup Instructions
SERVICE_ACCOUNT_SETUP_INSTRUCTIONS = """
Required Service Account permissions:

gcloud projects add-iam-policy-binding PROJECT_ID \\
    --member="serviceAccount:SA_EMAIL" \\
    --role="roles/billing.viewer"

gcloud projects add-iam-policy-binding PROJECT_ID \\
    --member="serviceAccount:SA_EMAIL" \\
    --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding PROJECT_ID \\
    --member="serviceAccount:SA_EMAIL" \\
    --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding PROJECT_ID \\
    --member="serviceAccount:SA_EMAIL" \\
    --role="roles/recommender.viewer"

Replace PROJECT_ID and SA_EMAIL with your values.
"""
