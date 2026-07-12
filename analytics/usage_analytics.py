"""
Usage Analytics System for LogicGate Multi-Tenant SaaS

This system tracks and analyzes:
- API usage per tenant
- Asset utilization metrics
- Storage consumption
- Bandwidth usage
- User activity patterns
- Cost analysis for billing
"""

import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any


class UsageAnalytics:
    """Tracks and analyzes tenant usage metrics"""

    def __init__(self, shared_db_path: str):
        self.shared_db_path = shared_db_path
        self._ensure_analytics_tables()

    def _ensure_analytics_tables(self):
        """Ensure analytics tables exist in shared database"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Hourly usage aggregation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_hourly (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id VARCHAR(36) NOT NULL,
                metric_type VARCHAR(50) NOT NULL,
                metric_value DECIMAL(10,2) NOT NULL,
                hour_timestamp INTEGER NOT NULL
            )
        """)

        # Daily usage aggregation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id VARCHAR(36) NOT NULL,
                metric_type VARCHAR(50) NOT NULL,
                metric_value DECIMAL(10,2) NOT NULL,
                day_date DATE NOT NULL
            )
        """)

        # Create indexes for hourly table
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tenant_hour ON usage_hourly(tenant_id, hour_timestamp)"
            )
        except sqlite3.Error as e:
            print(f"[ANALYTICS] Warning: Could not create idx_tenant_hour index: {e}")

        # Create indexes for daily table
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tenant_day ON usage_daily(tenant_id, day_date)"
            )
        except sqlite3.Error as e:
            print(f"[ANALYTICS] Warning: Could not create idx_tenant_day index: {e}")

        # Real-time usage cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_cache (
                tenant_id VARCHAR(36) PRIMARY KEY,
                api_requests_today INTEGER DEFAULT 0,
                asset_hours_today DECIMAL(10,2) DEFAULT 0,
                storage_gb_today DECIMAL(10,2) DEFAULT 0,
                bandwidth_gb_today DECIMAL(10,2) DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def record_metric(self, tenant_id: str, metric_type: str, value: float):
        """Record a usage metric"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Record in hourly table
        current_hour = int(time.time() // 3600) * 3600
        cursor.execute(
            """
            INSERT INTO usage_hourly (tenant_id, metric_type, metric_value, hour_timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (tenant_id, metric_type, value, current_hour),
        )

        # Update cache
        self._update_cache(conn, tenant_id, metric_type, value)

        conn.commit()
        conn.close()

    def _update_cache(
        self, conn: sqlite3.Connection, tenant_id: str, metric_type: str, value: float
    ):
        """Update real-time usage cache"""
        # Map metric types to cache columns
        metric_mapping = {
            "api_requests": "api_requests_today",
            "asset_hours": "asset_hours_today",
            "storage_gb": "storage_gb_today",
            "bandwidth_gb": "bandwidth_gb_today",
        }

        cache_column = metric_mapping.get(metric_type)
        if not cache_column:
            return

        # Check if cache entry exists
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM usage_cache WHERE tenant_id = ?", (tenant_id,))

        if cursor.fetchone():
            # Update existing
            cursor.execute(
                f"""
                UPDATE usage_cache
                SET {cache_column} = {cache_column} + ?, last_updated = CURRENT_TIMESTAMP
                WHERE tenant_id = ?
                """,
                (value, tenant_id),
            )
        else:
            # Create new
            cursor.execute(
                f"""
                INSERT INTO usage_cache (tenant_id, {cache_column}, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (tenant_id, value),
            )

    def get_tenant_usage_today(self, tenant_id: str) -> dict[str, float]:
        """Get today's usage for a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT api_requests_today, asset_hours_today, storage_gb_today, bandwidth_gb_today
            FROM usage_cache
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "api_requests": result[0] or 0,
                "asset_hours": result[1] or 0.0,
                "storage_gb": result[2] or 0.0,
                "bandwidth_gb": result[3] or 0.0,
            }

        return {"api_requests": 0, "asset_hours": 0.0, "storage_gb": 0.0, "bandwidth_gb": 0.0}

    def get_usage_history(self, tenant_id: str, days: int = 30) -> list[dict[str, Any]]:
        """Get usage history for a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        cursor.execute(
            """
            SELECT day_date, metric_type, SUM(metric_value) as total_value
            FROM usage_daily
            WHERE tenant_id = ? AND day_date >= ?
            GROUP BY day_date, metric_type
            ORDER BY day_date DESC
            """,
            (tenant_id, cutoff_date),
        )

        results = []
        for row in cursor.fetchall():
            results.append({"date": row[0], "metric_type": row[1], "value": row[2]})

        conn.close()
        return results

    def aggregate_hourly_to_daily(self):
        """Aggregate hourly usage to daily (should be run periodically)"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Get distinct dates that need aggregation
        cursor.execute(
            """
            SELECT DISTINCT date(hour_timestamp, 'unixepoch') as day_date
            FROM usage_hourly
            WHERE day_date NOT IN (SELECT day_date FROM usage_daily)
            """
        )

        dates_to_aggregate = [row[0] for row in cursor.fetchall()]

        for day_date in dates_to_aggregate:
            # Aggregate each metric type
            cursor.execute(
                """
                SELECT metric_type, SUM(metric_value)
                FROM usage_hourly
                WHERE date(hour_timestamp, 'unixepoch') = ?
                GROUP BY metric_type
                """,
                (day_date,),
            )

            for metric_type, total_value in cursor.fetchall():
                cursor.execute(
                    """
                    INSERT INTO usage_daily (tenant_id, metric_type, metric_value, day_date)
                    SELECT tenant_id, ?, ?, ?
                    FROM usage_hourly
                    WHERE date(hour_timestamp, 'unixepoch') = ?
                    GROUP BY tenant_id
                    """,
                    (metric_type, total_value, day_date, day_date),
                )

        conn.commit()
        conn.close()

    def get_usage_summary(self, tenant_id: str, period: str = "month") -> dict[str, Any]:
        """Get usage summary for a billing period"""
        if period == "month":
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        elif period == "year":
            cutoff_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        else:
            cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Get summary by metric type
        cursor.execute(
            """
            SELECT metric_type, SUM(metric_value) as total_value
            FROM usage_daily
            WHERE tenant_id = ? AND day_date >= ?
            GROUP BY metric_type
            """,
            (tenant_id, cutoff_date),
        )

        summary = {}
        for metric_type, total_value in cursor.fetchall():
            summary[metric_type] = total_value

        conn.close()
        return summary

    def calculate_billing(self, tenant_id: str, subscription_tier: str) -> dict[str, Any]:
        """Calculate billing based on usage and subscription tier"""
        usage_summary = self.get_usage_summary(tenant_id, "month")

        # Tier-based pricing
        tier_pricing = {
            "starter": {
                "base_price": 49.00,
                "included_api_requests": 10000,
                "included_storage_gb": 10,
                "extra_api_cost": 0.001,  # $0.001 per request
                "extra_storage_cost": 0.50,  # $0.50 per GB
            },
            "professional": {
                "base_price": 199.00,
                "included_api_requests": 100000,
                "included_storage_gb": 100,
                "extra_api_cost": 0.0005,
                "extra_storage_cost": 0.30,
            },
            "enterprise": {
                "base_price": 999.00,
                "included_api_requests": -1,  # Unlimited
                "included_storage_gb": -1,  # Unlimited
                "extra_api_cost": 0,
                "extra_storage_cost": 0,
            },
        }

        pricing = tier_pricing.get(subscription_tier, tier_pricing["starter"])

        total_cost = pricing["base_price"]
        breakdown = {"base_price": pricing["base_price"], "extra_charges": {}}

        # Calculate API request overage
        api_requests = usage_summary.get("api_requests", 0)
        if pricing["included_api_requests"] > 0 and api_requests > pricing["included_api_requests"]:
            overage = api_requests - pricing["included_api_requests"]
            extra_cost = overage * pricing["extra_api_cost"]
            total_cost += extra_cost
            breakdown["extra_charges"]["api_requests"] = {"overage": overage, "cost": extra_cost}

        # Calculate storage overage
        storage_gb = usage_summary.get("storage_gb", 0)
        if pricing["included_storage_gb"] > 0 and storage_gb > pricing["included_storage_gb"]:
            overage = storage_gb - pricing["included_storage_gb"]
            extra_cost = overage * pricing["extra_storage_cost"]
            total_cost += extra_cost
            breakdown["extra_charges"]["storage"] = {"overage": overage, "cost": extra_cost}

        return {"total_cost": round(total_cost, 2), "breakdown": breakdown, "usage": usage_summary}

    def get_top_consumers(self, metric_type: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get top consumers by metric type"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        cursor.execute(
            """
            SELECT t.tenant_id, t.tenant_name, SUM(ud.metric_value) as total_value
            FROM usage_daily ud
            JOIN tenants t ON ud.tenant_id = t.tenant_id
            WHERE ud.metric_type = ? AND ud.day_date >= ?
            GROUP BY t.tenant_id, t.tenant_name
            ORDER BY total_value DESC
            LIMIT ?
            """,
            (metric_type, cutoff_date, limit),
        )

        results = []
        for row in cursor.fetchall():
            results.append({"tenant_id": row[0], "tenant_name": row[1], "total_value": row[2]})

        conn.close()
        return results

    def get_usage_trends(self, tenant_id: str, metric_type: str, days: int = 30) -> dict[str, Any]:
        """Get usage trends for a specific metric"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        cursor.execute(
            """
            SELECT day_date, SUM(metric_value) as daily_value
            FROM usage_daily
            WHERE tenant_id = ? AND metric_type = ? AND day_date >= ?
            GROUP BY day_date
            ORDER BY day_date ASC
            """,
            (tenant_id, metric_type, cutoff_date),
        )

        daily_values = []
        for row in cursor.fetchall():
            daily_values.append({"date": row[0], "value": row[1]})

        conn.close()

        # Calculate trend
        if len(daily_values) >= 2:
            first_value = daily_values[0]["value"]
            last_value = daily_values[-1]["value"]
            trend = ((last_value - first_value) / first_value) * 100 if first_value > 0 else 0
        else:
            trend = 0

        return {
            "daily_values": daily_values,
            "trend_percent": round(trend, 2),
            "average": sum(v["value"] for v in daily_values) / len(daily_values)
            if daily_values
            else 0,
        }

    def reset_daily_cache(self, tenant_id: str = None):
        """Reset daily usage cache (typically run at midnight)"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        if tenant_id:
            cursor.execute(
                """
                UPDATE usage_cache
                SET api_requests_today = 0, asset_hours_today = 0,
                    storage_gb_today = 0, bandwidth_gb_today = 0
                WHERE tenant_id = ?
                """,
                (tenant_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE usage_cache
                SET api_requests_today = 0, asset_hours_today = 0,
                    storage_gb_today = 0, bandwidth_gb_today = 0
                """
            )

        conn.commit()
        conn.close()

    def export_usage_report(self, tenant_id: str, start_date: str, end_date: str) -> str:
        """Export usage report as CSV"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT day_date, metric_type, SUM(metric_value) as total_value
            FROM usage_daily
            WHERE tenant_id = ? AND day_date BETWEEN ? AND ?
            GROUP BY day_date, metric_type
            ORDER BY day_date ASC, metric_type
            """,
            (tenant_id, start_date, end_date),
        )

        csv_lines = ["Date,Metric Type,Value"]
        for row in cursor.fetchall():
            csv_lines.append(f"{row[0]},{row[1]},{row[2]}")

        conn.close()
        return "\n".join(csv_lines)


class UsageMonitor:
    """Real-time usage monitoring and alerting"""

    def __init__(self, analytics: UsageAnalytics):
        self.analytics = analytics
        self.alert_thresholds = {
            "api_requests": 0.9,  # Alert at 90% of limit
            "storage_gb": 0.9,
            "bandwidth_gb": 0.9,
        }

    def check_usage_alerts(self, tenant_id: str, subscription_tier: str) -> list[dict[str, Any]]:
        """Check if tenant is approaching usage limits"""
        alerts = []

        # Get tier limits
        tier_limits = {
            "starter": {"api_requests": 10000, "storage_gb": 10},
            "professional": {"api_requests": 100000, "storage_gb": 100},
            "enterprise": {"api_requests": -1, "storage_gb": -1},
        }

        limits = tier_limits.get(subscription_tier, tier_limits["starter"])

        # Get current usage
        usage = self.analytics.get_tenant_usage_today(tenant_id)

        # Check API requests
        if limits["api_requests"] > 0:
            usage_percent = usage["api_requests"] / limits["api_requests"]
            if usage_percent >= self.alert_thresholds["api_requests"]:
                alerts.append(
                    {
                        "type": "api_requests",
                        "severity": "warning",
                        "message": f"API usage at {usage_percent:.1%} of monthly limit",
                        "current": usage["api_requests"],
                        "limit": limits["api_requests"],
                    }
                )

        # Check storage
        if limits["storage_gb"] > 0:
            usage_percent = usage["storage_gb"] / limits["storage_gb"]
            if usage_percent >= self.alert_thresholds["storage_gb"]:
                alerts.append(
                    {
                        "type": "storage",
                        "severity": "warning",
                        "message": f"Storage usage at {usage_percent:.1%} of monthly limit",
                        "current": usage["storage_gb"],
                        "limit": limits["storage_gb"],
                    }
                )

        return alerts

    def generate_usage_report(self, tenant_id: str) -> dict[str, Any]:
        """Generate comprehensive usage report"""
        return {
            "today": self.analytics.get_tenant_usage_today(tenant_id),
            "month_summary": self.analytics.get_usage_summary(tenant_id, "month"),
            "trends": {
                "api_requests": self.analytics.get_usage_trends(tenant_id, "api_requests"),
                "storage": self.analytics.get_usage_trends(tenant_id, "storage_gb"),
            },
            "alerts": self.check_usage_alerts(tenant_id, "starter"),  # Would get actual tier
        }
