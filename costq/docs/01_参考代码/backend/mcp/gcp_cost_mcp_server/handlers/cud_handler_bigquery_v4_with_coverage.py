"""
✅ V4 WITH COVERAGE - GCP CUD BigQuery Handler
基于 ChatGPT 二次审阅的完善版本

新增功能:
1. ✅ 覆盖率（Coverage）计算 - ChatGPT 强调的关键指标
2. ✅ 使用 subscription.instance_id 识别 CUD 覆盖
3. ✅ Eligible SKU 过滤 - 确保分母准确
4. ✅ 支持 FEE_UTILIZATION_OFFSET（支出型 CUD）
5. ✅ 明确时区处理（Asia/Tokyo）
6. ✅ 布尔标签和优化建议
7. ✅ 双口径验证（金额法 + 量法）

核心改进（基于 ChatGPT 建议）:
1. Coverage = CUD覆盖的用量 ÷ 总符合条件的用量
2. Eligible SKU = 只统计有 CUD 覆盖的 SKU（避免分母污染）
3. subscription.instance_id 用于精确识别覆盖
4. 金额法和量法双轨验证数据一致性
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import pytz
from google.cloud import bigquery

logger = logging.getLogger(__name__)


async def list_commitments_with_coverage(
    account_id: str,
    project_id: str | None = None,
    billing_account_id: str | None = None,
    region: str | None = None,
    status: str | None = None,
    days_lookback: int = 30,
) -> dict[str, Any]:
    """
    ✅ V4: 添加覆盖率计算的完整版本

    新增指标:
    - coverage_percentage_by_amount: 金额法覆盖率
    - coverage_percentage_by_quantity: 量法覆盖率
    - is_commitment_fully_utilized: 是否充分利用
    - is_commitment_insufficient: 是否需要增加
    - optimization_recommendation: 优化建议
    """
    operation = "list_commitments_with_coverage_v4"
    logger.info(f"🔍 {operation} - V4版本，包含覆盖率和优化建议")

    try:
        from backend.services.gcp_credentials_provider import get_gcp_credentials_provider

        provider = get_gcp_credentials_provider()
        credentials = provider.create_credentials(account_id)
        bq_client = bigquery.Client(credentials=credentials, project=credentials.project_id)

        # 获取 BigQuery 表名
        account_info = provider.get_account_info(account_id)
        table_name = provider.get_bigquery_table_name(account_id)

        # ✅ 时区处理（Asia/Tokyo）
        tz = pytz.timezone("Asia/Tokyo")
        now = datetime.now(tz)
        end_date = now.date() - timedelta(days=2)
        start_date = end_date - timedelta(days=days_lookback)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.info(f"🕐 时区: Asia/Tokyo, 查询范围: {start_date_str} ~ {end_date_str}")

        # 智能处理参数
        if billing_account_id in [None, "", "null", "None", "undefined"]:
            billing_account_id = None
        if project_id in [None, "", "null", "None", "undefined"]:
            project_id = None

        # 构建查询条件
        if billing_account_id:
            scope_filter = f"AND billing_account_id = '{billing_account_id}'"
            logger.info(f"📊 查询范围: Billing Account {billing_account_id}")
        elif project_id:
            scope_filter = f"AND project.id = '{project_id}'"
            logger.info(f"📊 查询范围: Project {project_id}")
        else:
            ba_id = account_info.get("billing_account_id")
            if ba_id:
                scope_filter = f"AND billing_account_id = '{ba_id}'"
                logger.info(f"🎯 智能默认: Billing Account {ba_id}")
            else:
                default_project = account_info.get("project_id")
                if default_project:
                    scope_filter = f"AND project.id = '{default_project}'"
                    logger.warning(f"⚠️ 使用默认项目: {default_project}")
                else:
                    scope_filter = ""
                    logger.warning("⚠️ 未指定查询范围")

        region_filter = f"AND location.region = '{region}'" if region else ""

        # ✅ V4 QUERY - 添加覆盖率计算
        query = f"""
        -- ============================================================
        -- V4 Query: 包含覆盖率、利用率和优化建议
        -- 基于 ChatGPT 二次审阅的最佳实践
        -- ============================================================

        -- Step 1: 枚举有 CUD 覆盖的 SKU（Eligible SKU）
        WITH cud_skus AS (
          SELECT DISTINCT sku.id AS sku_id
          FROM `{table_name}` b,
               UNNEST(b.credits) c
          WHERE b.service.description = 'Compute Engine'
            AND b._PARTITIONDATE BETWEEN '{start_date_str}' AND '{end_date_str}'
            -- ✅ 支持两种 CUD 类型
            AND c.type IN ('COMMITTED_USAGE_DISCOUNT', 'FEE_UTILIZATION_OFFSET')
            -- ❌ 明确排除 SUD
            AND c.type != 'SUSTAINED_USAGE_DISCOUNT'
            {scope_filter}
            {region_filter}
        ),

        -- Step 2: Commitment 费用聚合（按 project+region）
        commitment_fees_detail AS (
          SELECT
            project.id AS project_id,
            project.name AS project_name,
            location.region AS region,
            sku.description AS sku_description,
            SUM(cost) AS commitment_cost_discounted,
            CASE
              WHEN sku.description LIKE '%1 Year%' THEN 0.28
              WHEN sku.description LIKE '%3 Year%' THEN 0.46
              ELSE 0.37
            END AS discount_rate,
            currency,
            MIN(_PARTITIONDATE) AS first_seen,
            MAX(_PARTITIONDATE) AS last_seen,
            COUNT(DISTINCT _PARTITIONDATE) AS days_active,
            CASE
              WHEN LOWER(sku.description) LIKE '%cpu%' THEN 'CPU'
              WHEN LOWER(sku.description) LIKE '%ram%' OR LOWER(sku.description) LIKE '%memory%' THEN 'RAM'
              WHEN LOWER(sku.description) LIKE '%gpu%' THEN 'GPU'
              WHEN LOWER(sku.description) LIKE '%ssd%' THEN 'Local SSD'
              ELSE 'Other'
            END AS resource_type,
            CASE
              WHEN sku.description LIKE '%1 Year%' THEN '1-Year'
              WHEN sku.description LIKE '%3 Year%' THEN '3-Year'
              ELSE 'Unknown'
            END AS commitment_term
          FROM `{table_name}`
          WHERE _PARTITIONDATE BETWEEN '{start_date_str}' AND '{end_date_str}'
            AND service.description = 'Compute Engine'
            AND sku.description LIKE 'Commitment v1:%'
            {scope_filter}
            {region_filter}
          GROUP BY project_id, project_name, region, sku_description, currency
          HAVING SUM(cost) > 0
        ),
        commitment_fees AS (
          SELECT
            project_id,
            project_name,
            region,
            SUM(commitment_cost_discounted) AS commitment_cost_discounted,
            SUM(commitment_cost_discounted * discount_rate) / SUM(commitment_cost_discounted) AS discount_rate,
            ANY_VALUE(currency) AS currency,
            MIN(first_seen) AS first_seen,
            MAX(last_seen) AS last_seen,
            MAX(days_active) AS days_active,
            STRING_AGG(DISTINCT resource_type ORDER BY resource_type) AS resource_types,
            STRING_AGG(DISTINCT commitment_term ORDER BY commitment_term) AS commitment_terms,
            STRING_AGG(DISTINCT sku_description ORDER BY sku_description LIMIT 3) AS sku_list
          FROM commitment_fees_detail
          GROUP BY project_id, project_name, region
        ),

        -- Step 3: 计算覆盖率和利用率（ChatGPT 的方法）
        base AS (
          SELECT
            b.project.id AS project_id,
            b.location.region AS region,
            b.subscription.instance_id AS commitment_id,
            -- ✅ 按需原价 = cost + 所有 credits（加回去）
            (b.cost + IFNULL((SELECT SUM(c2.amount) FROM UNNEST(b.credits) c2), 0))
              AS ondemand_equiv_cost,
            -- ✅ CUD 抵扣（负数，取反为正）
            -IFNULL((SELECT SUM(c3.amount)
                     FROM UNNEST(b.credits) c3
                     WHERE c3.type IN ('COMMITTED_USAGE_DISCOUNT', 'FEE_UTILIZATION_OFFSET')), 0)
              AS cud_credits,
            b.usage.amount AS usage_amount
          FROM `{table_name}` b
          WHERE b.service.description = 'Compute Engine'
            AND b._PARTITIONDATE BETWEEN '{start_date_str}' AND '{end_date_str}'
            -- ✅ 只统计 eligible SKU（避免分母污染）
            AND b.sku.id IN (SELECT sku_id FROM cud_skus)
            {scope_filter}
            {region_filter}
        ),

        -- Step 4: 按 project+region 聚合覆盖率
        coverage_by_project_region AS (
          SELECT
            project_id,
            region,
            -- ✅ 覆盖率（金额法）
            SAFE_DIVIDE(
              SUM(cud_credits),
              SUM(ondemand_equiv_cost)
            ) * 100 AS coverage_percent_by_amount,
            -- ✅ 覆盖率（量法，用于验证）
            SAFE_DIVIDE(
              SUM(CASE WHEN commitment_id IS NOT NULL THEN usage_amount ELSE 0 END),
              SUM(usage_amount)
            ) * 100 AS coverage_percent_by_quantity,
            -- 汇总数据
            SUM(ondemand_equiv_cost) AS total_ondemand_cost,
            SUM(cud_credits) AS total_cud_credits,
            SUM(usage_amount) AS total_usage_amount,
            SUM(CASE WHEN commitment_id IS NOT NULL THEN usage_amount ELSE 0 END) AS covered_usage_amount
          FROM base
          GROUP BY project_id, region
        ),

        -- Step 5: CUD 使用量（用于利用率计算）
        cud_covered_usage AS (
          SELECT
            project.id AS project_id,
            location.region AS region,
            SUM(cost) AS usage_cost_on_demand,
            ABS(SUM(
              (SELECT SUM(c.amount)
               FROM UNNEST(credits) AS c
               WHERE c.type IN ('COMMITTED_USAGE_DISCOUNT', 'FEE_UTILIZATION_OFFSET'))
            )) AS cud_credits_discount
          FROM `{table_name}`
          WHERE _PARTITIONDATE BETWEEN '{start_date_str}' AND '{end_date_str}'
            AND service.description = 'Compute Engine'
            AND EXISTS(SELECT 1 FROM UNNEST(credits) AS c
                       WHERE c.type IN ('COMMITTED_USAGE_DISCOUNT', 'FEE_UTILIZATION_OFFSET'))
            {scope_filter}
            {region_filter}
          GROUP BY project_id, region
        ),

        -- Step 6: 合并所有数据
        combined_data AS (
          SELECT
            f.project_id,
            f.project_name,
            f.region,
            f.resource_types,
            f.commitment_terms,
            f.sku_list,
            f.commitment_cost_discounted,
            f.discount_rate,
            ROUND(f.commitment_cost_discounted / (1 - f.discount_rate), 2) AS commitment_on_demand_value,
            COALESCE(u.usage_cost_on_demand, 0) AS usage_cost_on_demand,
            COALESCE(u.cud_credits_discount, 0) AS cud_credits_discount,
            -- ✅ 添加覆盖率数据
            COALESCE(cov.coverage_percent_by_amount, 0) AS coverage_percent_by_amount,
            COALESCE(cov.coverage_percent_by_quantity, 0) AS coverage_percent_by_quantity,
            COALESCE(cov.total_ondemand_cost, 0) AS total_ondemand_cost,
            COALESCE(cov.total_cud_credits, 0) AS total_cud_credits,
            f.currency,
            f.first_seen,
            f.last_seen,
            f.days_active
          FROM commitment_fees f
          LEFT JOIN cud_covered_usage u
            ON f.project_id = u.project_id
            AND (f.region = u.region OR (f.region IS NULL AND u.region IS NULL))
          LEFT JOIN coverage_by_project_region cov
            ON f.project_id = cov.project_id
            AND (f.region = cov.region OR (f.region IS NULL AND cov.region IS NULL))
        )

        -- Step 7: 最终结果（包含所有指标）
        SELECT
          project_id,
          project_name,
          region,
          sku_list AS sku_description,
          resource_types AS resource_type,
          commitment_terms AS commitment_term,
          ROUND(commitment_cost_discounted, 2) AS commitment_cost,
          commitment_on_demand_value,
          ROUND(usage_cost_on_demand, 2) AS usage_cost_on_demand,
          ROUND(cud_credits_discount, 2) AS cud_credits_used,
          -- ✅ 利用率
          ROUND(SAFE_DIVIDE(usage_cost_on_demand, commitment_on_demand_value) * 100, 2) AS utilization_percentage,
          -- ✅ 覆盖率（双口径）
          ROUND(coverage_percent_by_amount, 2) AS coverage_percentage_by_amount,
          ROUND(coverage_percent_by_quantity, 2) AS coverage_percentage_by_quantity,
          -- ✅ 覆盖率差距（用于验证）
          ROUND(ABS(coverage_percent_by_amount - coverage_percent_by_quantity), 2) AS coverage_delta,
          -- ✅ 其他指标
          ROUND(commitment_on_demand_value - usage_cost_on_demand, 2) AS unused_commitment,
          ROUND(commitment_cost_discounted * (30.0 / days_active), 2) AS estimated_monthly_cost,
          ROUND(total_ondemand_cost, 2) AS total_eligible_cost,
          ROUND(total_cud_credits, 2) AS total_cud_savings,
          currency,
          first_seen,
          last_seen,
          days_active,
          CASE
            WHEN days_active >= {days_lookback} - 5 THEN 'ACTIVE'
            WHEN days_active < 5 THEN 'POTENTIALLY_EXPIRED'
            ELSE 'PARTIAL'
          END AS status
        FROM combined_data
        ORDER BY estimated_monthly_cost DESC, project_id, region
        """

        logger.debug("执行 V4 BigQuery 查询（包含覆盖率）...")
        query_job = bq_client.query(query)
        results = query_job.result()

        # 处理结果
        commitments = []
        total_monthly_cost = 0.0
        total_commitment_cost = 0.0
        total_commitment_on_demand_value = 0.0
        total_usage_cost = 0.0
        total_utilization_sum = 0.0
        total_coverage_by_amount_sum = 0.0
        total_coverage_by_quantity_sum = 0.0
        total_eligible_cost = 0.0
        total_cud_savings = 0.0
        commitment_count = 0
        project_set = set()
        region_set = set()
        resource_type_counts = {}
        currency = "USD"

        # 用于验证
        high_coverage_delta_count = 0

        for row in results:
            utilization = float(row.utilization_percentage or 0)
            coverage_by_amount = float(row.coverage_percentage_by_amount or 0)
            coverage_by_quantity = float(row.coverage_percentage_by_quantity or 0)
            coverage_delta = float(row.coverage_delta or 0)

            # ✅ 生成优化建议
            recommendation = generate_optimization_recommendation(utilization)

            commitment = {
                "project_id": row.project_id,
                "project_name": row.project_name or row.project_id,
                "region": row.region or "global",
                "sku_description": row.sku_description,
                "resource_type": row.resource_type,
                "commitment_term": row.commitment_term,
                "commitment_cost": float(row.commitment_cost or 0),
                "commitment_on_demand_value": float(row.commitment_on_demand_value or 0),
                "usage_cost_on_demand": float(row.usage_cost_on_demand or 0),
                "cud_credits_used": float(row.cud_credits_used or 0),
                # ✅ 利用率
                "utilization_percentage": utilization,
                # ✅ 覆盖率（新增）
                "coverage_percentage_by_amount": coverage_by_amount,
                "coverage_percentage_by_quantity": coverage_by_quantity,
                "coverage_delta": coverage_delta,
                # ✅ 布尔标签（新增）
                "is_commitment_fully_utilized": utilization >= 99.5,
                "is_commitment_insufficient": utilization > 105,
                # ✅ 优化建议（新增）
                "optimization_recommendation": recommendation,
                # 其他指标
                "unused_commitment": float(row.unused_commitment or 0),
                "estimated_monthly_cost": float(row.estimated_monthly_cost or 0),
                "total_eligible_cost": float(row.total_eligible_cost or 0),
                "total_cud_savings": float(row.total_cud_savings or 0),
                "currency": row.currency,
                "first_seen": str(row.first_seen),
                "last_seen": str(row.last_seen),
                "days_active": int(row.days_active),
                "status": row.status,
            }

            commitments.append(commitment)
            total_monthly_cost += commitment["estimated_monthly_cost"]
            total_commitment_cost += commitment["commitment_cost"]
            total_commitment_on_demand_value += commitment["commitment_on_demand_value"]
            total_usage_cost += commitment["usage_cost_on_demand"]
            total_utilization_sum += utilization
            total_coverage_by_amount_sum += coverage_by_amount
            total_coverage_by_quantity_sum += coverage_by_quantity
            total_eligible_cost += commitment["total_eligible_cost"]
            total_cud_savings += commitment["total_cud_savings"]
            commitment_count += 1
            project_set.add(row.project_id)
            region_set.add(row.region or "global")

            resource_type = row.resource_type
            resource_type_counts[resource_type] = resource_type_counts.get(resource_type, 0) + 1

            currency = row.currency

            # ✅ 验证覆盖率一致性
            if coverage_delta > 5:
                high_coverage_delta_count += 1
                logger.warning(
                    f"⚠️ 覆盖率差距较大: {row.project_id}/{row.region} - "
                    f"金额法 {coverage_by_amount:.1f}% vs 量法 {coverage_by_quantity:.1f}%"
                )

        # 计算汇总指标
        avg_utilization = (total_utilization_sum / commitment_count) if commitment_count > 0 else 0
        overall_utilization = (
            (total_usage_cost / total_commitment_on_demand_value * 100)
            if total_commitment_on_demand_value > 0
            else 0
        )
        avg_coverage_by_amount = (
            (total_coverage_by_amount_sum / commitment_count) if commitment_count > 0 else 0
        )
        avg_coverage_by_quantity = (
            (total_coverage_by_quantity_sum / commitment_count) if commitment_count > 0 else 0
        )
        overall_coverage = (
            (total_cud_savings / total_eligible_cost * 100) if total_eligible_cost > 0 else 0
        )

        # 构建汇总
        summary = {
            # 原有指标
            "total_count": len(commitments),
            "total_commitment_cost": round(total_commitment_cost, 2),
            "total_commitment_on_demand_value": round(total_commitment_on_demand_value, 2),
            "total_usage_cost_on_demand": round(total_usage_cost, 2),
            "total_unused_commitment": round(
                total_commitment_on_demand_value - total_usage_cost, 2
            ),
            "total_estimated_monthly_cost": round(total_monthly_cost, 2),
            "average_utilization_percentage": round(avg_utilization, 2),
            "overall_utilization_percentage": round(overall_utilization, 2),
            # ✅ 新增覆盖率指标
            "average_coverage_by_amount": round(avg_coverage_by_amount, 2),
            "average_coverage_by_quantity": round(avg_coverage_by_quantity, 2),
            "overall_coverage_percentage": round(overall_coverage, 2),
            "total_eligible_cost": round(total_eligible_cost, 2),
            "total_cud_savings": round(total_cud_savings, 2),
            # 其他统计
            "unique_projects": len(project_set),
            "unique_regions": len(region_set),
            "resource_type_breakdown": resource_type_counts,
            "currency": currency,
            "analysis_period": f"{start_date_str} to {end_date_str}",
            "timezone": "Asia/Tokyo",
            "data_source": "BigQuery Billing Export",
            "version": "V4 - With Coverage & Optimization",
            "method": "✅ ChatGPT 审阅后的最佳实践",
            # ✅ 数据质量指标
            "high_coverage_delta_count": high_coverage_delta_count,
            "data_quality_note": f"覆盖率差距 >5% 的项目: {high_coverage_delta_count}/{commitment_count}",
        }

        logger.info(
            f"✅ {operation} 完成 - "
            f"找到 {len(commitments)} 个承诺, "
            f"整体利用率: {overall_utilization:.1f}%, "
            f"整体覆盖率: {overall_coverage:.1f}%"
        )

        # ✅ 验证数据质量
        if overall_utilization > 150:
            logger.warning(f"⚠️ 利用率异常高: {overall_utilization:.1f}%")
        if overall_coverage > 100:
            logger.warning(f"⚠️ 覆盖率超过100%: {overall_coverage:.1f}%，请检查")
        if high_coverage_delta_count > commitment_count * 0.2:
            logger.warning(f"⚠️ {high_coverage_delta_count} 个项目覆盖率差距较大，建议检查数据")

        return {
            "success": True,
            "data": {"commitments": commitments, "summary": summary},
            "message": f"V4: 提取了 {len(commitments)} 个 CUD 承诺（包含覆盖率和优化建议）",
        }

    except Exception as e:
        logger.error(f"❌ {operation} 失败: {str(e)}", exc_info=True)
        import traceback

        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e), "message": f"{operation} 执行失败"}


def generate_optimization_recommendation(utilization: float) -> str:
    """
    ✅ 生成优化建议（ChatGPT 建议的布尔标签逻辑）
    """
    if utilization < 0:
        return "❌ 数据异常：利用率为负数，请检查数据"
    elif utilization < 50:
        return f"⚠️ 利用率过低（{utilization:.1f}%），建议降配或取消承诺以减少浪费"
    elif utilization < 80:
        return f"💡 利用率偏低（{utilization:.1f}%），建议优化资源使用或调整承诺规模"
    elif utilization <= 100:
        return f"✅ 利用率良好（{utilization:.1f}%），承诺被充分利用"
    elif utilization <= 120:
        return f"⚡ 轻度过载（{utilization:.1f}%），实际使用超出承诺 {utilization - 100:.1f}%，考虑增加承诺"
    elif utilization <= 150:
        return f"🔥 显著过载（{utilization:.1f}%），建议增加约 {utilization - 100:.1f}% 的承诺容量"
    else:
        return f"🚨 严重过载（{utilization:.1f}%），强烈建议增加承诺或检查数据准确性"
