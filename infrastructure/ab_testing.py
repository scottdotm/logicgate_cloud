"""
LogicGate A/B Testing Framework
Manages A/B tests for feature experimentation and optimization.
"""

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from logicgate_cloud.config.settings import get_settings
from logicgate_cloud.core.exceptions import ErrorCode, ErrorSeverity, LogicGateException
from logicgate_cloud.infrastructure.cache import get_cache_manager

# Infrastructure imports
from logicgate_cloud.infrastructure.logging import LogLevel, get_logger


class TestStatus(Enum):
    """A/B test status"""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VariantType(Enum):
    """Variant types"""

    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass
class ABTest:
    """A/B test data"""

    id: str
    name: str
    description: str
    status: TestStatus
    traffic_split: dict[str, float]  # variant_name -> percentage
    variants: dict[str, dict]  # variant_name -> configuration
    metrics: list[str]  # Metrics to track
    start_date: datetime
    end_date: datetime | None
    sample_size: int
    created_at: datetime
    updated_at: datetime


@dataclass
class TestAssignment:
    """User assignment to a test variant"""

    id: str
    test_id: str
    user_id: str
    variant: str
    assigned_at: datetime
    converted: bool
    conversion_value: float


class ABTestingManager:
    """Manages A/B testing framework"""

    def __init__(self, db_path: str = None):
        self.logger = get_logger("ab_testing", LogLevel.INFO)
        self.settings = get_settings()
        self.cache_manager = get_cache_manager()

        # Use database path from settings if not provided
        if db_path is None and hasattr(self.settings, "shared_db_path"):
            db_path = self.settings.shared_db_path
        elif db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logicgate_shared.db"
            )

        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Initialize A/B testing database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                status TEXT DEFAULT 'draft',
                traffic_split TEXT NOT NULL,
                variants TEXT NOT NULL,
                metrics TEXT NOT NULL,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                sample_size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_assignments (
                id TEXT PRIMARY KEY,
                test_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                variant TEXT NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                converted BOOLEAN DEFAULT 0,
                conversion_value REAL DEFAULT 0,
                FOREIGN KEY (test_id) REFERENCES ab_tests(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES test_assignments(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                test_id TEXT PRIMARY KEY,
                variant TEXT NOT NULL,
                total_users INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                conversion_rate REAL DEFAULT 0,
                total_value REAL DEFAULT 0,
                average_value REAL DEFAULT 0,
                statistical_significance REAL,
                confidence_interval TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES ab_tests(id)
            )
        """)

        conn.commit()
        conn.close()
        self.logger.info("A/B testing database initialized")

    def create_test(
        self,
        name: str,
        description: str,
        traffic_split: dict[str, float],
        variants: dict[str, dict],
        metrics: list[str],
        start_date: datetime,
        end_date: datetime = None,
    ) -> ABTest:
        """Create a new A/B test"""
        test_id = f"test_{int(datetime.now().timestamp())}"

        # Validate traffic split sums to 100
        total_split = sum(traffic_split.values())
        if abs(total_split - 100) > 0.01:
            raise LogicGateException(
                message="Traffic split must sum to 100%",
                error_code=ErrorCode.INVALID_INPUT,
                severity=ErrorSeverity.ERROR,
                context={"total_split": total_split},
            )

        test = ABTest(
            id=test_id,
            name=name,
            description=description,
            status=TestStatus.DRAFT,
            traffic_split=traffic_split,
            variants=variants,
            metrics=metrics,
            start_date=start_date,
            end_date=end_date,
            sample_size=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self._save_test(test)
        self.logger.info(f"Created A/B test: {name}")

        return test

    def _save_test(self, test: ABTest):
        """Save test to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO ab_tests
            (id, name, description, status, traffic_split, variants, metrics,
             start_date, end_date, sample_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                test.id,
                test.name,
                test.description,
                test.status.value,
                json.dumps(test.traffic_split),
                json.dumps(test.variants),
                json.dumps(test.metrics),
                test.start_date.isoformat(),
                test.end_date.isoformat() if test.end_date else None,
                test.sample_size,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def start_test(self, test_id: str) -> bool:
        """Start an A/B test"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE ab_tests
            SET status = 'running', start_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (test_id,),
        )

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected > 0:
            self.logger.info(f"Started A/B test: {test_id}")
            return True
        return False

    def pause_test(self, test_id: str) -> bool:
        """Pause an A/B test"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE ab_tests
            SET status = 'paused'
            WHERE id = ?
        """,
            (test_id,),
        )

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected > 0:
            self.logger.info(f"Paused A/B test: {test_id}")
            return True
        return False

    def complete_test(self, test_id: str) -> bool:
        """Complete an A/B test"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE ab_tests
            SET status = 'completed', end_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (test_id,),
        )

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected > 0:
            self.logger.info(f"Completed A/B test: {test_id}")
            return True
        return False

    def assign_variant(self, test_id: str, user_id: str) -> str | None:
        """Assign a user to a test variant"""
        # Check if user is already assigned
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT variant FROM test_assignments
            WHERE test_id = ? AND user_id = ?
        """,
            (test_id, user_id),
        )

        result = cursor.fetchone()

        if result:
            conn.close()
            return result[0]

        # Get test configuration
        cursor.execute(
            """
            SELECT status, traffic_split FROM ab_tests WHERE id = ?
        """,
            (test_id,),
        )

        test_result = cursor.fetchone()
        conn.close()

        if not test_result:
            return None

        status, traffic_split_json = test_result

        if status != "running":
            return None

        traffic_split = json.loads(traffic_split_json)

        # Assign variant based on traffic split
        variant = self._select_variant(traffic_split, user_id)

        # Save assignment
        assignment_id = f"assign_{int(datetime.now().timestamp())}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO test_assignments
            (id, test_id, user_id, variant)
            VALUES (?, ?, ?, ?)
        """,
            (assignment_id, test_id, user_id, variant),
        )

        # Update sample size
        cursor.execute(
            """
            UPDATE ab_tests
            SET sample_size = sample_size + 1
            WHERE id = ?
        """,
            (test_id,),
        )

        conn.commit()
        conn.close()

        # Cache assignment
        cache_key = f"ab_test:{test_id}:{user_id}"
        self.cache_manager.set(cache_key, variant, ttl=3600)

        return variant

    def _select_variant(self, traffic_split: dict[str, float], user_id: str) -> str:
        """Select variant based on traffic split using consistent hashing"""
        # Use hash of user_id for consistent assignment
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100

        cumulative = 0
        for variant, percentage in traffic_split.items():
            cumulative += percentage
            if user_hash < cumulative:
                return variant

        # Fallback to control
        return "control"

    def track_conversion(self, test_id: str, user_id: str, value: float = 1.0) -> bool:
        """Track a conversion event for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE test_assignments
            SET converted = 1, conversion_value = ?
            WHERE test_id = ? AND user_id = ?
        """,
            (value, test_id, user_id),
        )

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected > 0:
            # Update results
            self._update_test_results(test_id)
            return True
        return False

    def track_event(self, test_id: str, user_id: str, event_type: str, event_data: dict = None):
        """Track a custom event for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get assignment ID
        cursor.execute(
            """
            SELECT id FROM test_assignments
            WHERE test_id = ? AND user_id = ?
        """,
            (test_id, user_id),
        )

        result = cursor.fetchone()

        if not result:
            conn.close()
            return

        assignment_id = result[0]

        cursor.execute(
            """
            INSERT INTO test_events
            (assignment_id, event_type, event_data)
            VALUES (?, ?, ?)
        """,
            (assignment_id, event_type, json.dumps(event_data) if event_data else None),
        )

        conn.commit()
        conn.close()

    def _update_test_results(self, test_id: str):
        """Update test results with current statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get test configuration
        cursor.execute(
            """
            SELECT traffic_split FROM ab_tests WHERE id = ?
        """,
            (test_id,),
        )

        result = cursor.fetchone()
        if not result:
            conn.close()
            return

        traffic_split = json.loads(result[0])

        # Calculate results for each variant
        for variant in traffic_split:
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_users,
                    SUM(CASE WHEN converted = 1 THEN 1 ELSE 0 END) as conversions,
                    SUM(conversion_value) as total_value
                FROM test_assignments
                WHERE test_id = ? AND variant = ?
            """,
                (test_id, variant),
            )

            stats = cursor.fetchone()
            total_users, conversions, total_value = stats

            conversion_rate = (conversions / total_users * 100) if total_users > 0 else 0
            average_value = (total_value / conversions) if conversions > 0 else 0

            # Calculate statistical significance (simplified)
            significance = self._calculate_significance(conversions, total_users)

            cursor.execute(
                """
                INSERT OR REPLACE INTO test_results
                (test_id, variant, total_users, conversions, conversion_rate,
                 total_value, average_value, statistical_significance, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    test_id,
                    variant,
                    total_users,
                    conversions,
                    conversion_rate,
                    total_value,
                    average_value,
                    significance,
                ),
            )

        conn.commit()
        conn.close()

    def _calculate_significance(self, conversions: int, total_users: int) -> float:
        """Calculate statistical significance (simplified)"""
        if total_users < 30:
            return 0.0

        # Simplified z-test calculation
        p = conversions / total_users
        se = (p * (1 - p) / total_users) ** 0.5

        if se == 0:
            return 0.0

        z = p / se
        # Convert z-score to p-value (simplified)
        significance = min(1.0, abs(z) / 3.0)  # Approximate

        return significance

    def get_test_results(self, test_id: str) -> dict:
        """Get current test results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get test info
        cursor.execute(
            """
            SELECT name, status, traffic_split, start_date, end_date, sample_size
            FROM ab_tests WHERE id = ?
        """,
            (test_id,),
        )

        test_info = cursor.fetchone()

        if not test_info:
            conn.close()
            return {}

        # Get variant results
        cursor.execute(
            """
            SELECT variant, total_users, conversions, conversion_rate,
                   average_value, statistical_significance
            FROM test_results WHERE test_id = ?
        """,
            (test_id,),
        )

        results = cursor.fetchall()
        conn.close()

        return {
            "test_id": test_id,
            "name": test_info[0],
            "status": test_info[1],
            "traffic_split": json.loads(test_info[2]),
            "start_date": test_info[3],
            "end_date": test_info[4],
            "sample_size": test_info[5],
            "variants": [
                {
                    "name": row[0],
                    "total_users": row[1],
                    "conversions": row[2],
                    "conversion_rate": row[3],
                    "average_value": row[4],
                    "statistical_significance": row[5],
                }
                for row in results
            ],
        }

    def get_variant_config(self, test_id: str, variant: str) -> dict:
        """Get configuration for a specific variant"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT variants FROM ab_tests WHERE id = ?
        """,
            (test_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            return {}

        variants = json.loads(result[0])
        return variants.get(variant, {})

    def get_all_tests(self, status: TestStatus = None) -> list[dict]:
        """Get all A/B tests"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status:
            cursor.execute(
                """
                SELECT id, name, description, status, start_date, end_date, sample_size
                FROM ab_tests WHERE status = ?
                ORDER BY created_at DESC
            """,
                (status.value,),
            )
        else:
            cursor.execute("""
                SELECT id, name, description, status, start_date, end_date, sample_size
                FROM ab_tests ORDER BY created_at DESC
            """)

        results = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "status": row[3],
                "start_date": row[4],
                "end_date": row[5],
                "sample_size": row[6],
            }
            for row in results
        ]


# Convenience functions
def get_variant(test_name: str, user_id: str) -> str | None:
    """Get the variant assignment for a user in a test"""
    manager = get_ab_testing_manager()

    # Find test by name
    tests = manager.get_all_tests()
    test = next((t for t in tests if t["name"] == test_name), None)

    if not test:
        return None

    return manager.assign_variant(test["id"], user_id)


def track_conversion(test_name: str, user_id: str, value: float = 1.0) -> bool:
    """Track a conversion for a user in a test"""
    manager = get_ab_testing_manager()

    tests = manager.get_all_tests()
    test = next((t for t in tests if t["name"] == test_name), None)

    if not test:
        return False

    return manager.track_conversion(test["id"], user_id, value)


# Global manager instance
_ab_manager = None


def get_ab_testing_manager() -> ABTestingManager:
    """Get the global A/B testing manager instance"""
    global _ab_manager
    if _ab_manager is None:
        _ab_manager = ABTestingManager()
    return _ab_manager


if __name__ == "__main__":
    print("Testing A/B Testing Framework...")

    manager = ABTestingManager()

    # Create a test
    test = manager.create_test(
        name="ui_redesign_test",
        description="Test new UI design vs current design",
        traffic_split={"control": 50, "treatment": 50},
        variants={
            "control": {"ui_version": "v1", "color_scheme": "blue"},
            "treatment": {"ui_version": "v2", "color_scheme": "green"},
        },
        metrics=["conversion_rate", "time_on_page"],
        start_date=datetime.now(),
    )
    print(f"Created test: {test.name}")

    # Start the test
    manager.start_test(test.id)
    print("Test started")

    # Assign variants to users
    variant_1 = manager.assign_variant(test.id, "user_1")
    variant_2 = manager.assign_variant(test.id, "user_2")
    print(f"User 1 variant: {variant_1}")
    print(f"User 2 variant: {variant_2}")

    # Track conversions
    manager.track_conversion(test.id, "user_1", value=10.0)
    print("Conversion tracked for user_1")

    # Get test results
    results = manager.get_test_results(test.id)
    print(f"Test results: {results}")

    print("A/B Testing Framework test complete!")
