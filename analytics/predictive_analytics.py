"""
LogicGate Predictive Analytics Service (Consolidated)
AI/ML-powered maintenance prediction, anomaly detection, and scheduling.
Consolidates predictive_analytics.py and predictive_maintenance.py functionality.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from logicgate_cloud.core.exceptions import BusinessException


class MaintenancePriority(Enum):
    """Maintenance priority levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MaintenanceType(Enum):
    """Types of maintenance"""

    ROUTINE = "routine"
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"


class MaintenanceStatus(Enum):
    """Maintenance status"""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class AnomalySeverity(Enum):
    """Anomaly severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyDetection:
    """Anomaly detection result"""

    asset_id: int
    anomaly_type: str
    severity: AnomalySeverity
    detected_at: datetime
    description: str
    metrics: dict
    confidence: float


@dataclass
class MaintenancePrediction:
    """Maintenance prediction result"""

    asset_id: int
    component: str
    predicted_failure_date: datetime
    confidence: float
    recommended_action: str
    urgency: MaintenancePriority


@dataclass
class BatteryHealth:
    """Battery health analysis"""

    asset_id: int
    current_capacity: float
    degradation_rate: float
    estimated_cycles_remaining: int
    predicted_health: str


@dataclass
class MaintenanceSchedule:
    """Maintenance schedule entry"""

    schedule_id: str
    asset_id: int
    maintenance_type: MaintenanceType
    priority: MaintenancePriority
    scheduled_date: datetime
    estimated_duration: int
    description: str
    status: MaintenanceStatus
    created_at: datetime
    completed_at: datetime | None


class PredictiveAnalyticsService:
    """Consolidated predictive analytics service"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logicgate_shared.db"
            )
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Initialize predictive analytics database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT NOT NULL,
                metrics TEXT NOT NULL,
                confidence REAL NOT NULL,
                resolved BOOLEAN DEFAULT 0,
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                component TEXT NOT NULL,
                predicted_failure_date TIMESTAMP NOT NULL,
                confidence REAL NOT NULL,
                recommended_action TEXT NOT NULL,
                urgency TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battery_health (
                asset_id INTEGER PRIMARY KEY,
                current_capacity REAL NOT NULL,
                degradation_rate REAL NOT NULL,
                estimated_cycles_remaining INTEGER NOT NULL,
                predicted_health TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_schedules (
                schedule_id TEXT PRIMARY KEY,
                asset_id INTEGER NOT NULL,
                maintenance_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                scheduled_date TIMESTAMP NOT NULL,
                estimated_duration INTEGER NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        """)

        conn.commit()
        conn.close()

    def detect_anomalies(self, asset_id: int, telemetry_data: dict) -> list[AnomalyDetection]:
        """Detect anomalies in telemetry data"""
        anomalies = []

        # Check for unusual patterns
        if "temperature" in telemetry_data:
            temp = telemetry_data["temperature"]
            if temp > 50:  # High temperature
                anomalies.append(
                    AnomalyDetection(
                        asset_id=asset_id,
                        anomaly_type="high_temperature",
                        severity=AnomalySeverity.HIGH,
                        detected_at=datetime.now(),
                        description=f"Unusually high temperature: {temp}°C",
                        metrics={"temperature": temp},
                        confidence=0.85,
                    )
                )

        if "vibration" in telemetry_data:
            vibration = telemetry_data["vibration"]
            if vibration > 10:  # High vibration
                anomalies.append(
                    AnomalyDetection(
                        asset_id=asset_id,
                        anomaly_type="high_vibration",
                        severity=AnomalySeverity.MEDIUM,
                        detected_at=datetime.now(),
                        description=f"Unusually high vibration: {vibration} mm/s",
                        metrics={"vibration": vibration},
                        confidence=0.75,
                    )
                )

        if "battery_voltage" in telemetry_data:
            voltage = telemetry_data["battery_voltage"]
            if voltage < 11.0:  # Low voltage
                anomalies.append(
                    AnomalyDetection(
                        asset_id=asset_id,
                        anomaly_type="low_battery_voltage",
                        severity=AnomalySeverity.CRITICAL,
                        detected_at=datetime.now(),
                        description=f"Low battery voltage: {voltage}V",
                        metrics={"battery_voltage": voltage},
                        confidence=0.95,
                    )
                )

        # Save anomalies
        for anomaly in anomalies:
            self._save_anomaly(anomaly)

        return anomalies

    def _save_anomaly(self, anomaly: AnomalyDetection):
        """Save anomaly to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO anomaly_detections
            (asset_id, anomaly_type, severity, detected_at, description, metrics, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                anomaly.asset_id,
                anomaly.anomaly_type,
                anomaly.severity.value,
                anomaly.detected_at.isoformat(),
                anomaly.description,
                json.dumps(anomaly.metrics),
                anomaly.confidence,
            ),
        )

        conn.commit()
        conn.close()

    def predict_maintenance(
        self, asset_id: int, component: str, telemetry_history: list[dict]
    ) -> MaintenancePrediction:
        """Predict when maintenance will be needed"""
        # Simple ML prediction (placeholder for actual ML model)

        # Calculate degradation rate
        if not telemetry_history:
            raise BusinessException("Insufficient telemetry data for prediction")

        # Simulate prediction
        current_health = self._calculate_component_health(telemetry_history)

        if current_health < 0.2:
            urgency = MaintenancePriority.CRITICAL
            days_until_failure = 7
        elif current_health < 0.4:
            urgency = MaintenancePriority.HIGH
            days_until_failure = 14
        elif current_health < 0.6:
            urgency = MaintenancePriority.MEDIUM
            days_until_failure = 30
        else:
            urgency = MaintenancePriority.LOW
            days_until_failure = 60

        prediction = MaintenancePrediction(
            asset_id=asset_id,
            component=component,
            predicted_failure_date=datetime.now() + timedelta(days=days_until_failure),
            confidence=0.75,
            recommended_action=f"Schedule {component} maintenance within {days_until_failure} days",
            urgency=urgency,
        )

        # Save prediction
        self._save_prediction(prediction)

        return prediction

    def _calculate_component_health(self, telemetry_history: list[dict]) -> float:
        """Calculate component health from telemetry history"""
        # Simplified health calculation
        if not telemetry_history:
            return 1.0

        # Use latest values
        latest = telemetry_history[-1]

        health = 1.0

        if "temperature" in latest:
            temp_factor = max(0, 1 - (latest["temperature"] - 25) / 50)
            health *= temp_factor

        if "vibration" in latest:
            vibration_factor = max(0, 1 - latest["vibration"] / 15)
            health *= vibration_factor

        return max(0, min(1, health))

    def _save_prediction(self, prediction: MaintenancePrediction):
        """Save prediction to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO maintenance_predictions
            (asset_id, component, predicted_failure_date, confidence, recommended_action, urgency)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                prediction.asset_id,
                prediction.component,
                prediction.predicted_failure_date.isoformat(),
                prediction.confidence,
                prediction.recommended_action,
                prediction.urgency.value,
            ),
        )

        conn.commit()
        conn.close()

    def analyze_battery_health(self, asset_id: int, battery_data: dict) -> BatteryHealth:
        """Analyze battery health and predict remaining life"""
        current_capacity = battery_data.get("capacity_percent", 100)
        cycle_count = battery_data.get("cycle_count", 0)

        # Calculate degradation rate
        degradation_rate = (100 - current_capacity) / max(cycle_count, 1)

        # Estimate cycles remaining
        cycles_remaining = (
            int(current_capacity / degradation_rate) if degradation_rate > 0 else 500
        )  # Default estimate

        # Predict health status
        if current_capacity > 90:
            predicted_health = "excellent"
        elif current_capacity > 75:
            predicted_health = "good"
        elif current_capacity > 60:
            predicted_health = "fair"
        elif current_capacity > 40:
            predicted_health = "poor"
        else:
            predicted_health = "critical"

        battery_health = BatteryHealth(
            asset_id=asset_id,
            current_capacity=current_capacity,
            degradation_rate=degradation_rate,
            estimated_cycles_remaining=cycles_remaining,
            predicted_health=predicted_health,
        )

        # Save to database
        self._save_battery_health(battery_health)

        return battery_health

    def _save_battery_health(self, battery_health: BatteryHealth):
        """Save battery health to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO battery_health
            (asset_id, current_capacity, degradation_rate, estimated_cycles_remaining, predicted_health, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                battery_health.asset_id,
                battery_health.current_capacity,
                battery_health.degradation_rate,
                battery_health.estimated_cycles_remaining,
                battery_health.predicted_health,
            ),
        )

        conn.commit()
        conn.close()

    def schedule_maintenance(
        self,
        asset_id: int,
        maintenance_type: MaintenanceType,
        priority: MaintenancePriority,
        scheduled_date: datetime,
        description: str,
        estimated_duration: int = 60,
    ) -> str:
        """Schedule maintenance for an asset"""
        schedule_id = f"maint_{int(datetime.now().timestamp())}"

        schedule = MaintenanceSchedule(
            schedule_id=schedule_id,
            asset_id=asset_id,
            maintenance_type=maintenance_type,
            priority=priority,
            scheduled_date=scheduled_date,
            estimated_duration=estimated_duration,
            description=description,
            status=MaintenanceStatus.SCHEDULED,
            created_at=datetime.now(),
            completed_at=None,
        )

        # Save to database
        self._save_maintenance_schedule(schedule)

        return schedule_id

    def _save_maintenance_schedule(self, schedule: MaintenanceSchedule):
        """Save maintenance schedule to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO maintenance_schedules
            (schedule_id, asset_id, maintenance_type, priority, scheduled_date, estimated_duration, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                schedule.schedule_id,
                schedule.asset_id,
                schedule.maintenance_type.value,
                schedule.priority.value,
                schedule.scheduled_date.isoformat(),
                schedule.estimated_duration,
                schedule.description,
                schedule.status.value,
            ),
        )

        conn.commit()
        conn.close()

    def get_upcoming_maintenance(self, days: int = 7) -> list[MaintenanceSchedule]:
        """Get upcoming maintenance schedules"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = datetime.now() + timedelta(days=days)

        cursor.execute(
            """
            SELECT * FROM maintenance_schedules
            WHERE scheduled_date < ? AND status = 'scheduled'
            ORDER BY scheduled_date ASC
        """,
            (cutoff.isoformat(),),
        )

        results = cursor.fetchall()
        conn.close()

        return [
            MaintenanceSchedule(
                schedule_id=row[0],
                asset_id=row[1],
                maintenance_type=MaintenanceType(row[2]),
                priority=MaintenancePriority(row[3]),
                scheduled_date=datetime.fromisoformat(row[4]),
                estimated_duration=row[5],
                description=row[6],
                status=MaintenanceStatus(row[7]),
                created_at=datetime.fromisoformat(row[8]),
                completed_at=datetime.fromisoformat(row[9]) if row[9] else None,
            )
            for row in results
        ]

    def complete_maintenance(self, schedule_id: str) -> bool:
        """Mark maintenance as completed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE maintenance_schedules
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE schedule_id = ?
        """,
            (schedule_id,),
        )

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        return rows_affected > 0

    def record_telemetry(self, asset_id: int, metric_name: str, metric_value: float):
        """Record telemetry data point"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO telemetry_history
            (asset_id, metric_name, metric_value)
            VALUES (?, ?, ?)
        """,
            (asset_id, metric_name, metric_value),
        )

        conn.commit()
        conn.close()

    def get_telemetry_history(self, asset_id: int, hours: int = 24) -> list[dict]:
        """Get telemetry history for an asset"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = datetime.now() - timedelta(hours=hours)

        cursor.execute(
            """
            SELECT * FROM telemetry_history
            WHERE asset_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
        """,
            (asset_id, cutoff.isoformat()),
        )

        results = cursor.fetchall()
        conn.close()

        return [
            {"metric_name": row[2], "metric_value": row[3], "timestamp": row[4]} for row in results
        ]


# Convenience functions
def detect_asset_anomalies(asset_id: int, telemetry: dict) -> list[dict]:
    """Detect anomalies for an asset"""
    service = PredictiveAnalyticsService()
    anomalies = service.detect_anomalies(asset_id, telemetry)
    return [
        {
            "type": a.anomaly_type,
            "severity": a.severity.value,
            "description": a.description,
            "confidence": a.confidence,
        }
        for a in anomalies
    ]


def schedule_preventive_maintenance(asset_id: int, component: str, days: int = 30) -> str:
    """Schedule preventive maintenance"""
    service = PredictiveAnalyticsService()
    return service.schedule_maintenance(
        asset_id,
        MaintenanceType.PREVENTIVE,
        MaintenancePriority.MEDIUM,
        datetime.now() + timedelta(days=days),
        f"Preventive maintenance for {component}",
    )


if __name__ == "__main__":
    print("Testing Consolidated Predictive Analytics...")

    # Test anomaly detection
    telemetry = {"temperature": 55, "vibration": 12, "battery_voltage": 10.5}
    anomalies = detect_asset_anomalies(1, telemetry)
    print(f"Detected {len(anomalies)} anomalies")

    # Test maintenance scheduling
    schedule_id = schedule_preventive_maintenance(1, "motor", 30)
    print(f"Scheduled maintenance: {schedule_id}")

    # Test battery health
    service = PredictiveAnalyticsService()
    battery_health = service.analyze_battery_health(1, {"capacity_percent": 85, "cycle_count": 50})
    print(f"Battery health: {battery_health.predicted_health}")

    print("Consolidated Predictive Analytics test complete!")
