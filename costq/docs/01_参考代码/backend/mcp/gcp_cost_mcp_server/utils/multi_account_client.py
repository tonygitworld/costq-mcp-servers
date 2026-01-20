"""
Multi-account GCP Client Utilities

Provides account-aware GCP API clients for MCP tools.
Follows the same pattern as AWS multi_account_client.py for consistency.
"""

import logging
import sys

# Add project root to path for imports
from pathlib import Path

from google.cloud import bigquery, billing_v1, recommender_v1
from google.cloud.billing import budgets_v1

logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.services.gcp_credentials_provider import get_gcp_credentials_provider


def get_bigquery_client_for_account(account_id: str | None = None) -> bigquery.Client:
    """Get BigQuery client for specified account

    Args:
        account_id: Optional GCP account ID. If None, uses default credentials (ADC).

    Returns:
        BigQuery Client instance

    Example:
        # Multi-account mode
        client = get_bigquery_client_for_account('gcp-account-id-123')

        # Default credentials mode
        client = get_bigquery_client_for_account()
    """
    try:
        if account_id:
            # Multi-account mode: use stored credentials
            # logger.info(f"🔑 Creating BigQuery client - Account ID: {account_id}")  # 已静默

            provider = get_gcp_credentials_provider()
            credentials = provider.create_credentials(account_id)

            account_info = provider.get_account_info(account_id)
            project_id = account_info["project_id"]

            client = bigquery.Client(credentials=credentials, project=project_id)

            # logger.info(
            #     f"✅ BigQuery client created - "
            #     f"Account: {account_info['account_name']} "
            #     f"(Project: {project_id})"
            # )  # 已静默

            return client
        else:
            # Default credentials mode (Application Default Credentials)
            # logger.info("🔑 Creating BigQuery client with default credentials")  # 已静默
            client = bigquery.Client()
            # logger.info("✅ BigQuery client created (default ADC)")  # 已静默
            return client

    except Exception as e:
        logger.error(f"❌ Failed to create BigQuery client: {e}", exc_info=True)
        raise


def get_billing_client_for_account(account_id: str | None = None) -> billing_v1.CloudBillingClient:
    """Get Cloud Billing client for specified account

    Args:
        account_id: Optional GCP account ID. If None, uses default credentials.

    Returns:
        CloudBillingClient instance
    """
    try:
        if account_id:
            logger.info(f"🔑 Creating Cloud Billing client - Account: {account_id}")

            provider = get_gcp_credentials_provider()
            credentials = provider.create_credentials(account_id)

            client = billing_v1.CloudBillingClient(credentials=credentials)

            account_info = provider.get_account_info(account_id)
            logger.info(f"✅ Cloud Billing client created - {account_info['account_name']}")

            return client
        else:
            logger.info("🔑 Creating Cloud Billing client with default credentials")
            return billing_v1.CloudBillingClient()

    except Exception as e:
        logger.error(f"❌ Failed to create Cloud Billing client: {e}", exc_info=True)
        raise


def get_recommender_client_for_account(
    account_id: str | None = None,
) -> recommender_v1.RecommenderClient:
    """Get Recommender client for specified account

    Args:
        account_id: Optional GCP account ID. If None, uses default credentials.

    Returns:
        RecommenderClient instance
    """
    try:
        if account_id:
            logger.info(f"🔑 Creating Recommender client - Account: {account_id}")

            provider = get_gcp_credentials_provider()
            credentials = provider.create_credentials(account_id)

            client = recommender_v1.RecommenderClient(credentials=credentials)

            account_info = provider.get_account_info(account_id)
            logger.info(f"✅ Recommender client created - {account_info['account_name']}")

            return client
        else:
            logger.info("🔑 Creating Recommender client with default credentials")
            return recommender_v1.RecommenderClient()

    except Exception as e:
        logger.error(f"❌ Failed to create Recommender client: {e}", exc_info=True)
        raise


def get_budget_client_for_account(account_id: str | None = None) -> budgets_v1.BudgetServiceClient:
    """Get Budget Service client for specified account

    Args:
        account_id: Optional GCP account ID. If None, uses default credentials.

    Returns:
        budgets_v1.BudgetServiceClient instance
    """
    try:
        if account_id:
            logger.info(f"🔑 Creating Budget Service client - Account: {account_id}")

            provider = get_gcp_credentials_provider()
            credentials = provider.create_credentials(account_id)

            client = budgets_v1.BudgetServiceClient(credentials=credentials)

            account_info = provider.get_account_info(account_id)
            logger.info(f"✅ Budget Service client created - {account_info['account_name']}")

            return client
        else:
            logger.info("🔑 Creating Budget Service client with default credentials")
            return budgets_v1.BudgetServiceClient()

    except Exception as e:
        logger.error(f"❌ Failed to create Budget Service client: {e}", exc_info=True)
        raise


def get_catalog_client_for_account(account_id: str | None = None) -> billing_v1.CloudCatalogClient:
    """Get Cloud Catalog client for SKU pricing

    Args:
        account_id: Optional GCP account ID. If None, uses default credentials.

    Returns:
        CloudCatalogClient instance
    """
    try:
        if account_id:
            logger.info(f"🔑 Creating Cloud Catalog client - Account: {account_id}")

            provider = get_gcp_credentials_provider()
            credentials = provider.create_credentials(account_id)

            client = billing_v1.CloudCatalogClient(credentials=credentials)

            account_info = provider.get_account_info(account_id)
            logger.info(f"✅ Cloud Catalog client created - {account_info['account_name']}")

            return client
        else:
            logger.info("🔑 Creating Cloud Catalog client with default credentials")
            return billing_v1.CloudCatalogClient()

    except Exception as e:
        logger.error(f"❌ Failed to create Cloud Catalog client: {e}", exc_info=True)
        raise


def get_compute_client_for_account(account_id: str | None = None):
    """Get Compute Engine client for specified account

    Args:
        account_id: Optional GCP account ID. If None, uses default credentials.

    Returns:
        Compute Engine Client wrapper with access to various Compute APIs
    """
    # Import here to avoid circular dependency
    from backend.mcp.gcp_cost_mcp_server.utils.compute_client import (
        get_compute_client_for_account as _get_compute_client,
    )

    return _get_compute_client(account_id)
