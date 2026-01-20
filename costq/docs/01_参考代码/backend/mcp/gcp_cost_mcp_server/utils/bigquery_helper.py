"""
BigQuery Helper - SQL Query Builder and Utilities

Provides SQL query templates and helper functions for BigQuery billing export queries.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from ..constants import DATE_FORMAT_BIGQUERY


class BigQueryHelper:
    """Helper class for building BigQuery SQL queries"""

    def __init__(self, table_name: str):
        """
        Initialize BigQuery Helper

        Args:
            table_name: Fully qualified table name
                       (e.g., 'project.dataset.gcp_billing_export_resource_v1_...')
        """
        self.table_name = table_name
        # logger.debug(f"BigQuery Helper initialized - Table: {table_name}")  # 已静默

    def build_cost_by_service_query(
        self,
        start_date: str,
        end_date: str,
        project_ids: list[str] | None = None,
        billing_account_id: str | None = None,
        limit: int = 100,
    ) -> str:
        """Build query for cost grouped by service

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            project_ids: Optional list of project IDs to filter
            billing_account_id: Optional billing account ID to filter (org-level query)
            limit: Maximum number of results

        Returns:
            SQL query string
        """
        # Build scope filter: billing_account_id OR project_ids OR all
        scope_filter = ""
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
        elif project_ids:
            project_list = "', '".join(project_ids)
            scope_filter = f"AND project.id IN ('{project_list}')"
        # else: no filter, query all projects in the table

        query = f"""
        SELECT
            service.description AS service_name,
            SUM(cost) AS total_cost,
            SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS total_credits,
            (SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))) AS net_cost,
            currency,
            COUNT(DISTINCT project.id) AS project_count
        FROM `{self.table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            {scope_filter}
        GROUP BY service_name, currency
        HAVING total_cost > 0 OR total_credits != 0
        ORDER BY ABS(net_cost) DESC
        LIMIT {limit}
        """

        # logger.debug(f"Built cost by service query - Date range: {start_date} to {end_date}")  # 已静默
        return query.strip()

    def build_cost_by_project_query(
        self,
        start_date: str,
        end_date: str,
        service_filter: str | None = None,
        billing_account_id: str | None = None,
        limit: int = 100,
    ) -> str:
        """Build query for cost grouped by project

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            service_filter: Optional service name to filter (e.g., 'Compute Engine')
            billing_account_id: Optional billing account ID to filter
            limit: Maximum number of results

        Returns:
            SQL query string
        """
        filters = []
        if service_filter:
            filters.append(f"service.description = '{service_filter}'")
        if billing_account_id:
            filters.append(f"billing_account_id = '{billing_account_id}'")

        additional_where = ""
        if filters:
            additional_where = "AND " + " AND ".join(filters)

        query = f"""
        SELECT
            project.id AS project_id,
            project.name AS project_name,
            SUM(cost) AS total_cost,
            SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS total_credits,
            (SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))) AS net_cost,
            currency,
            COUNT(DISTINCT service.description) AS service_count
        FROM `{self.table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            {additional_where}
        GROUP BY project_id, project_name, currency
        HAVING total_cost > 0 OR total_credits != 0
        ORDER BY ABS(net_cost) DESC
        LIMIT {limit}
        """

        # logger.debug(f"Built cost by project query - Date range: {start_date} to {end_date}")  # 已静默
        return query.strip()

    def build_daily_cost_trend_query(
        self,
        start_date: str,
        end_date: str,
        project_ids: list[str] | None = None,
        service_filter: str | None = None,
    ) -> str:
        """Build query for daily cost trend

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            project_ids: Optional list of project IDs to filter
            service_filter: Optional service name to filter

        Returns:
            SQL query string
        """
        filters = []
        if project_ids:
            project_list = "', '".join(project_ids)
            filters.append(f"project.id IN ('{project_list}')")
        if service_filter:
            filters.append(f"service.description = '{service_filter}'")

        additional_where = ""
        if filters:
            additional_where = "AND " + " AND ".join(filters)

        query = f"""
        SELECT
            DATE(_PARTITIONDATE) AS date,
            SUM(cost) AS daily_cost,
            SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS daily_credits,
            (SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))) AS daily_net_cost,
            currency,
            COUNT(DISTINCT service.description) AS services_used,
            COUNT(DISTINCT project.id) AS projects_count
        FROM `{self.table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            {additional_where}
        GROUP BY date, currency
        ORDER BY date ASC
        """

        # logger.debug(f"Built daily cost trend query - Date range: {start_date} to {end_date}")  # 已静默
        return query.strip()

    def build_cost_by_label_query(
        self,
        start_date: str,
        end_date: str,
        label_key: str,
        project_ids: list[str] | None = None,
        billing_account_id: str | None = None,
        limit: int = 100,
    ) -> str:
        """Build query for cost grouped by label (cost allocation)

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            label_key: Label key to group by (e.g., 'team', 'department', 'env')
            project_ids: Optional list of project IDs to filter
            billing_account_id: Optional billing account ID to filter
            limit: Maximum number of results

        Returns:
            SQL query string
        """
        scope_filter = ""
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
        elif project_ids:
            project_list = "', '".join(project_ids)
            scope_filter = f"AND project.id IN ('{project_list}')"

        query = f"""
        SELECT
            label.value AS label_value,
            SUM(cost) AS total_cost,
            SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS total_credits,
            (SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))) AS net_cost,
            currency,
            COUNT(DISTINCT project.id) AS project_count,
            COUNT(DISTINCT service.description) AS service_count
        FROM `{self.table_name}`,
        UNNEST(labels) AS label
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            AND label.key = '{label_key}'
            {scope_filter}
        GROUP BY label_value, currency
        HAVING total_cost > 0 OR total_credits != 0
        ORDER BY ABS(net_cost) DESC
        LIMIT {limit}
        """

        # logger.debug(f"Built cost by label query - Label: {label_key}, Date range: {start_date} to {end_date}")  # 已静默
        return query.strip()

    def build_cost_by_sku_query(
        self,
        start_date: str,
        end_date: str,
        service_filter: str | None = None,
        project_ids: list[str] | None = None,
        billing_account_id: str | None = None,
        limit: int = 50,
    ) -> str:
        """Build query for cost grouped by SKU (detailed breakdown)

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            service_filter: Optional service name to filter
            project_ids: Optional list of project IDs to filter
            billing_account_id: Optional billing account ID to filter
            limit: Maximum number of results

        Returns:
            SQL query string
        """
        filters = []
        if service_filter:
            filters.append(f"service.description = '{service_filter}'")
        if billing_account_id:
            filters.append(f"billing_account_id = '{billing_account_id}'")
        elif project_ids:
            project_list = "', '".join(project_ids)
            filters.append(f"project.id IN ('{project_list}')")

        additional_where = ""
        if filters:
            additional_where = "AND " + " AND ".join(filters)

        query = f"""
        SELECT
            service.description AS service_name,
            sku.description AS sku_description,
            SUM(cost) AS total_cost,
            SUM(usage.amount) AS total_usage_amount,
            ANY_VALUE(usage.unit) AS usage_unit,
            currency,
            COUNT(DISTINCT project.id) AS project_count
        FROM `{self.table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            {additional_where}
        GROUP BY service_name, sku_description, currency
        HAVING total_cost > 0
        ORDER BY total_cost DESC
        LIMIT {limit}
        """

        # logger.debug(f"Built cost by SKU query - Service: {service_filter}, Date range: {start_date} to {end_date}")  # 已静默
        return query.strip()

    def build_cost_summary_query(
        self,
        start_date: str,
        end_date: str,
        project_ids: list[str] | None = None,
        billing_account_id: str | None = None,
    ) -> str:
        """Build query for overall cost summary

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            project_ids: Optional list of project IDs to filter
            billing_account_id: Optional billing account ID to filter

        Returns:
            SQL query string
        """
        scope_filter = ""
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
        elif project_ids:
            project_list = "', '".join(project_ids)
            scope_filter = f"AND project.id IN ('{project_list}')"

        query = f"""
        SELECT
            SUM(cost) AS total_cost,
            SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS total_credits,
            (SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))) AS net_cost,
            currency,
            COUNT(DISTINCT service.description) AS services_count,
            COUNT(DISTINCT project.id) AS projects_count,
            COUNT(DISTINCT DATE(_PARTITIONDATE)) AS days_count,
            MIN(DATE(_PARTITIONDATE)) AS start_date,
            MAX(DATE(_PARTITIONDATE)) AS end_date
        FROM `{self.table_name}`
        WHERE _PARTITIONDATE BETWEEN '{start_date}' AND '{end_date}'
            {scope_filter}
        GROUP BY currency
        """

        # logger.debug(f"Built cost summary query - Date range: {start_date} to {end_date}")  # 已静默
        return query.strip()

    @staticmethod
    def format_date_for_query(date_obj: datetime) -> str:
        """Format datetime object for BigQuery query

        Args:
            date_obj: datetime object

        Returns:
            Date string in YYYY-MM-DD format
        """
        return date_obj.strftime(DATE_FORMAT_BIGQUERY)

    @staticmethod
    def get_default_date_range(days_back: int = 30) -> tuple[str, str]:
        """Get default date range (last N days)

        Args:
            days_back: Number of days to look back

        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return (
            BigQueryHelper.format_date_for_query(start_date),
            BigQueryHelper.format_date_for_query(end_date),
        )


def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate date range format and logic

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        True if valid, False otherwise
    """
    try:
        start = datetime.strptime(start_date, DATE_FORMAT_BIGQUERY)
        end = datetime.strptime(end_date, DATE_FORMAT_BIGQUERY)

        if start > end:
            logger.warning(f"Invalid date range: start ({start_date}) > end ({end_date})")
            return False

        if end > datetime.now():
            logger.warning(f"End date ({end_date}) is in the future")
            return False

        return True
    except ValueError as e:
        logger.error(f"Date format validation failed: {e}", exc_info=True)
        return False


def sanitize_string_for_sql(value: str) -> str:
    """Sanitize string to prevent SQL injection

    Args:
        value: Input string

    Returns:
        Sanitized string
    """
    # Replace single quotes with escaped quotes
    return value.replace("'", "\\'")
