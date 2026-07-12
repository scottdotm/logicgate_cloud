"""
LogicGate Customer Portal with Self-Service Capabilities
Self-service portal for customers to manage their accounts and services.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class PortalSection(Enum):
    """Portal sections"""

    DASHBOARD = "dashboard"
    ASSETS = "assets"
    FLIGHTS = "flights"
    ANALYTICS = "analytics"
    BILLING = "billing"
    SETTINGS = "settings"
    SUPPORT = "support"


class TicketStatus(Enum):
    """Support ticket status"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class CustomerProfile:
    """Customer profile data"""

    user_id: str
    email: str
    name: str
    company: str
    phone: str
    address: dict
    preferences: dict
    created_at: datetime


@dataclass
class SelfServiceAction:
    """Self-service action"""

    id: str
    action_type: str
    description: str
    requires_approval: bool
    created_at: datetime
    status: str


class CustomerPortalManager:
    """Manages customer portal and self-service capabilities"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logicgate_shared.db"
            )
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Initialize customer portal database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_profiles (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                name TEXT NOT NULL,
                company TEXT,
                phone TEXT,
                address TEXT,
                preferences TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS self_service_actions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                description TEXT NOT NULL,
                parameters TEXT,
                requires_approval BOOLEAN DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES customer_profiles(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portal_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                section TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES customer_profiles(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES customer_profiles(user_id)
            )
        """)

        conn.commit()
        conn.close()

    def get_customer_profile(self, user_id: str) -> CustomerProfile | None:
        """Get customer profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM customer_profiles WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return CustomerProfile(
            user_id=result[0],
            email=result[1],
            name=result[2],
            company=result[3],
            phone=result[4],
            address=json.loads(result[5]) if result[5] else {},
            preferences=json.loads(result[6]) if result[6] else {},
            created_at=datetime.fromisoformat(result[7]),
        )

    def update_profile(self, user_id: str, updates: dict) -> bool:
        """Update customer profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        allowed_fields = ["name", "company", "phone", "address", "preferences"]
        set_clauses = []
        params = []

        for field in allowed_fields:
            if field in updates:
                if field in ["address", "preferences"]:
                    set_clauses.append(f"{field} = ?")
                    params.append(json.dumps(updates[field]))
                else:
                    set_clauses.append(f"{field} = ?")
                    params.append(updates[field])

        if set_clauses:
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)

            query = f"UPDATE customer_profiles SET {', '.join(set_clauses)} WHERE user_id = ?"
            cursor.execute(query, params)
            conn.commit()

        conn.close()
        return True

    def get_dashboard_data(self, user_id: str) -> dict:
        """Get dashboard data for customer"""
        # Get customer's assets
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM assets")
        total_assets = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM flight_logs
            WHERE start_time > datetime('now', '-30 days')
        """)
        recent_flights = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM alerts
            WHERE created_at > datetime('now', '-7 days') AND resolved_at IS NULL
        """)
        active_alerts = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM customer_notifications
            WHERE user_id = ? AND is_read = 0
        """,
            (user_id,),
        )
        unread_notifications = cursor.fetchone()[0]

        conn.close()

        return {
            "total_assets": total_assets,
            "recent_flights": recent_flights,
            "active_alerts": active_alerts,
            "unread_notifications": unread_notifications,
            "subscription_status": "active",
            "next_billing_date": (datetime.now() + timedelta(days=30)).isoformat(),
        }

    def request_asset_addition(
        self, user_id: str, asset_name: str, asset_type: str, serial_number: str
    ) -> str:
        """Request addition of a new asset"""
        action_id = f"action_{int(datetime.now().timestamp())}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO self_service_actions
            (id, user_id, action_type, description, parameters, requires_approval, status)
            VALUES (?, ?, ?, ?, ?, 1, 'pending')
        """,
            (
                action_id,
                user_id,
                "add_asset",
                f"Request to add new asset: {asset_name}",
                json.dumps(
                    {
                        "asset_name": asset_name,
                        "asset_type": asset_type,
                        "serial_number": serial_number,
                    }
                ),
            ),
        )

        conn.commit()
        conn.close()

        return action_id

    def request_asset_removal(self, user_id: str, asset_id: str, reason: str) -> str:
        """Request removal of an asset"""
        action_id = f"action_{int(datetime.now().timestamp())}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO self_service_actions
            (id, user_id, action_type, description, parameters, requires_approval, status)
            VALUES (?, ?, ?, ?, ?, 1, 'pending')
        """,
            (
                action_id,
                user_id,
                "remove_asset",
                f"Request to remove asset: {asset_id}",
                json.dumps({"asset_id": asset_id, "reason": reason}),
            ),
        )

        conn.commit()
        conn.close()

        return action_id

    def update_subscription_plan(self, user_id: str, new_plan: str) -> str:
        """Request subscription plan change"""
        action_id = f"action_{int(datetime.now().timestamp())}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO self_service_actions
            (id, user_id, action_type, description, parameters, requires_approval, status)
            VALUES (?, ?, ?, ?, ?, 1, 'pending')
        """,
            (
                action_id,
                user_id,
                "change_plan",
                f"Request to change subscription plan to {new_plan}",
                json.dumps({"new_plan": new_plan}),
            ),
        )

        conn.commit()
        conn.close()

        return action_id

    def submit_support_ticket(
        self, user_id: str, subject: str, description: str, category: str, priority: str = "medium"
    ) -> str:
        """Submit a support ticket"""
        action_id = f"action_{int(datetime.now().timestamp())}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO self_service_actions
            (id, user_id, action_type, description, parameters, requires_approval, status)
            VALUES (?, ?, ?, ?, ?, 0, 'open')
        """,
            (
                action_id,
                user_id,
                "support_ticket",
                subject,
                json.dumps(
                    {"description": description, "category": category, "priority": priority}
                ),
            ),
        )

        conn.commit()
        conn.close()

        return action_id

    def get_action_status(self, action_id: str) -> dict | None:
        """Get status of a self-service action"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM self_service_actions WHERE id = ?", (action_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return {
            "id": result[0],
            "user_id": result[1],
            "action_type": result[2],
            "description": result[3],
            "parameters": json.loads(result[4]) if result[4] else {},
            "requires_approval": bool(result[5]),
            "status": result[6],
            "created_at": result[7],
            "completed_at": result[8],
        }

    def get_user_actions(self, user_id: str, limit: int = 50) -> list[dict]:
        """Get all actions for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM self_service_actions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (user_id, limit),
        )

        results = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "action_type": row[2],
                "description": row[3],
                "status": row[6],
                "created_at": row[7],
                "completed_at": row[8],
            }
            for row in results
        ]

    def log_portal_usage(self, user_id: str, section: PortalSection, action: str):
        """Log portal usage for analytics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO portal_usage_logs
            (user_id, section, action)
            VALUES (?, ?, ?)
        """,
            (user_id, section.value, action),
        )

        conn.commit()
        conn.close()

    def get_usage_analytics(self, user_id: str, days: int = 30) -> dict:
        """Get usage analytics for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=days)

        cursor.execute(
            """
            SELECT section, COUNT(*) as count
            FROM portal_usage_logs
            WHERE user_id = ? AND timestamp > ?
            GROUP BY section
        """,
            (user_id, cutoff_date.isoformat()),
        )

        section_usage = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT COUNT(*) FROM portal_usage_logs
            WHERE user_id = ? AND timestamp > ?
        """,
            (user_id, cutoff_date.isoformat()),
        )

        total_actions = cursor.fetchone()[0]

        conn.close()

        return {
            "total_actions": total_actions,
            "section_usage": section_usage,
            "most_used_section": max(section_usage.items(), key=lambda x: x[1])[0]
            if section_usage
            else None,
        }

    def send_notification(
        self, user_id: str, notification_type: str, title: str, message: str
    ) -> int:
        """Send notification to user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO customer_notifications
            (user_id, notification_type, title, message)
            VALUES (?, ?, ?, ?)
        """,
            (user_id, notification_type, title, message),
        )

        notification_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return notification_id

    def get_notifications(self, user_id: str, unread_only: bool = False) -> list[dict]:
        """Get notifications for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if unread_only:
            cursor.execute(
                """
                SELECT * FROM customer_notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY created_at DESC
            """,
                (user_id,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM customer_notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
            """,
                (user_id,),
            )

        results = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "user_id": row[1],
                "notification_type": row[2],
                "title": row[3],
                "message": row[4],
                "is_read": bool(row[5]),
                "created_at": row[6],
                "read_at": row[7],
            }
            for row in results
        ]

    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE customer_notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (notification_id,),
        )

        conn.commit()
        conn.close()

        return True

    def mark_all_notifications_read(self, user_id: str) -> bool:
        """Mark all notifications as read for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE customer_notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND is_read = 0
        """,
            (user_id,),
        )

        conn.commit()
        conn.close()

        return True

    def get_billing_summary(self, user_id: str) -> dict:
        """Get billing summary for user"""
        # Placeholder for billing data
        return {
            "current_plan": "Professional",
            "monthly_cost": 499.00,
            "next_invoice_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "payment_method": "Visa ending in 4242",
            "usage_this_month": {"flight_hours": 45.5, "data_gb": 12.3, "api_calls": 15000},
        }


# Convenience functions
def get_customer_dashboard(user_id: str) -> dict:
    """Get customer dashboard data"""
    manager = CustomerPortalManager()
    return manager.get_dashboard_data(user_id)


def submit_support_request(user_id: str, subject: str, description: str, category: str) -> str:
    """Submit a support request"""
    manager = CustomerPortalManager()
    return manager.submit_support_ticket(user_id, subject, description, category)


if __name__ == "__main__":
    print("Testing Customer Portal...")

    # Get dashboard
    dashboard = get_customer_dashboard("user_1")
    print(f"Dashboard: {dashboard['total_assets']} assets")

    # Submit support request
    ticket_id = submit_support_request(
        "user_1", "Asset not responding", "Drone is not responding to commands", "technical"
    )
    print(f"Support ticket: {ticket_id}")

    print("Customer Portal test complete!")
