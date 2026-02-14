"""
Compute Engine Client Utilities

⚠️  DEPRECATED: Functions in this module are no longer usable due to lack of
Compute Engine API permissions.

The Service Account only has BigQuery permissions but not:
- compute.regions.list
- compute.regionCommitments.list
- compute.regionCommitments.get

All functions will fail with 401 Unauthorized errors if called.

RECOMMENDED: Use BigQuery-based CUD analysis instead:
- See: backend/mcp/gcp_cost_mcp_server/handlers/cud_handler_bigquery_v2.py
- All CUD queries now use BigQuery, which provides:
  * Faster performance
  * More accurate cost data
  * No additional permissions required
"""

import logging
from typing import Any

from google.cloud import compute_v1

logger = logging.getLogger(__name__)


from services.gcp_credentials_provider import get_gcp_credentials_provider


def get_compute_client_for_account(account_id: str | None = None):
    """Get Compute Engine client for specified account

    ⚠️  WARNING: This function will fail with 401 Unauthorized
    Service Account lacks Compute Engine API permissions.
    Use BigQuery-based CUD analysis instead.

    Args:
        account_id: Optional GCP account ID. If None, uses default credentials.

    Returns:
        Compute Engine Client wrapper with appropriate resource clients
    """
    try:
        if account_id:
            logger.info(f"🔑 Creating Compute Engine client - Account: {account_id}")

            provider = get_gcp_credentials_provider()
            credentials = provider.create_credentials(account_id)

            # Create a wrapper object that provides access to various Compute Engine clients
            class ComputeClientWrapper:
                def __init__(self, credentials):
                    self.credentials = credentials
                    self._regions_client = None
                    self._region_commitments_client = None
                    self._instances_client = None

                def regions(self):
                    if not self._regions_client:
                        self._regions_client = compute_v1.RegionsClient(
                            credentials=self.credentials
                        )
                    return self._regions_client

                def region_commitments(self):
                    if not self._region_commitments_client:
                        self._region_commitments_client = compute_v1.RegionCommitmentsClient(
                            credentials=self.credentials
                        )
                    return self._region_commitments_client

                def instances(self):
                    if not self._instances_client:
                        self._instances_client = compute_v1.InstancesClient(
                            credentials=self.credentials
                        )
                    return self._instances_client

            client = ComputeClientWrapper(credentials)

            account_info = provider.get_account_info(account_id)
            logger.info(f"✅ Compute Engine client created - {account_info['account_name']}")

            return client
        else:
            logger.info("🔑 Creating Compute Engine client with default credentials")

            class ComputeClientWrapper:
                def __init__(self):
                    self._regions_client = None
                    self._region_commitments_client = None
                    self._instances_client = None

                def regions(self):
                    if not self._regions_client:
                        self._regions_client = compute_v1.RegionsClient()
                    return self._regions_client

                def region_commitments(self):
                    if not self._region_commitments_client:
                        self._region_commitments_client = compute_v1.RegionCommitmentsClient()
                    return self._region_commitments_client

                def instances(self):
                    if not self._instances_client:
                        self._instances_client = compute_v1.InstancesClient()
                    return self._instances_client

            return ComputeClientWrapper()

    except Exception as e:
        logger.error(f"❌ Failed to create Compute Engine client: {e}", exc_info=True)
        raise


def list_all_commitments_aggregated(
    project_id: str, account_id: str | None = None
) -> list[dict[str, Any]]:
    """List all commitments across all regions using aggregated list

    This is more efficient than iterating through regions individually.

    Args:
        project_id: GCP project ID
        account_id: Optional GCP account ID

    Returns:
        List of commitment dictionaries with region information
    """
    try:
        logger.info(f"📊 Listing all commitments for project: {project_id}")

        # Get client
        compute_client = get_compute_client_for_account(account_id)
        commitments_client = compute_client.region_commitments()

        # Use aggregatedList for efficiency
        request = compute_v1.AggregatedListRegionCommitmentsRequest(project=project_id)

        all_commitments = []
        page_result = commitments_client.aggregated_list(request=request)

        for region_name, response in page_result:
            if not response.commitments:
                continue

            # Extract region name from the scoped name (e.g., "regions/us-central1")
            region = region_name.split("/")[-1] if "/" in region_name else region_name

            for commitment in response.commitments:
                commitment_dict = {
                    "commitment_id": commitment.id,
                    "name": commitment.name,
                    "description": commitment.description or "",
                    "region": region,
                    "status": commitment.status,
                    "plan": commitment.plan,
                    "start_time": commitment.start_timestamp,
                    "end_time": commitment.end_timestamp,
                    "resources": [],
                    "self_link": commitment.self_link,
                }

                # Parse resources
                if commitment.resources:
                    for resource in commitment.resources:
                        commitment_dict["resources"].append(
                            {
                                "type": resource.type_,
                                "amount": str(resource.amount) if resource.amount else "0",
                            }
                        )

                all_commitments.append(commitment_dict)

        logger.info(f"✅ Found {len(all_commitments)} commitments across all regions")
        return all_commitments

    except Exception as e:
        logger.error(f"❌ Failed to list commitments: {e}", exc_info=True)
        raise


def get_commitment_details(
    project_id: str, region: str, commitment_name: str, account_id: str | None = None
) -> dict[str, Any]:
    """Get detailed information about a specific commitment

    Args:
        project_id: GCP project ID
        region: Region where commitment exists
        commitment_name: Name of the commitment
        account_id: Optional GCP account ID

    Returns:
        Detailed commitment information
    """
    try:
        logger.info(f"📋 Getting commitment details: {commitment_name} in {region}")

        compute_client = get_compute_client_for_account(account_id)
        commitments_client = compute_client.region_commitments()

        request = compute_v1.GetRegionCommitmentRequest(
            project=project_id, region=region, commitment=commitment_name
        )

        commitment = commitments_client.get(request=request)

        # Build detailed response
        details = {
            "commitment_id": commitment.id,
            "name": commitment.name,
            "description": commitment.description or "",
            "region": region,
            "status": commitment.status,
            "status_message": commitment.status_message or "",
            "plan": commitment.plan,
            "type": commitment.type_,
            "start_time": commitment.start_timestamp,
            "end_time": commitment.end_timestamp,
            "creation_time": commitment.creation_timestamp,
            "resources": [],
            "self_link": commitment.self_link,
            "kind": commitment.kind,
        }

        # Parse resources with units
        if commitment.resources:
            for resource in commitment.resources:
                details["resources"].append(
                    {
                        "type": resource.type_,
                        "amount": str(resource.amount) if resource.amount else "0",
                        "unit": "count",  # GCP uses count for vCPU, memory measured in GB
                    }
                )

        # Add license resource if present
        if hasattr(commitment, "license_resource") and commitment.license_resource:
            details["license_resource"] = {
                "license": commitment.license_resource.license,
                "amount": (
                    str(commitment.license_resource.amount)
                    if commitment.license_resource.amount
                    else "0"
                ),
            }

        logger.info(f"✅ Retrieved commitment details: {commitment_name}")
        return details

    except Exception as e:
        logger.error(f"❌ Failed to get commitment details: {e}", exc_info=True)
        raise


def get_regions_list(project_id: str, account_id: str | None = None) -> list[str]:
    """Get list of all available regions for a project

    Args:
        project_id: GCP project ID
        account_id: Optional GCP account ID

    Returns:
        List of region names
    """
    try:
        logger.info(f"🌍 Getting regions list for project: {project_id}")

        compute_client = get_compute_client_for_account(account_id)
        regions_client = compute_client.regions()

        request = compute_v1.ListRegionsRequest(project=project_id)

        regions = []
        page_result = regions_client.list(request=request)

        for region in page_result:
            regions.append(region.name)

        logger.info(f"✅ Found {len(regions)} regions")
        return regions

    except Exception as e:
        logger.error(f"❌ Failed to get regions list: {e}", exc_info=True)
        raise
