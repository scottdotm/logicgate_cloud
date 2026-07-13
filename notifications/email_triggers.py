# email_triggers.py
"""
LogicGate Automated Email Trigger System
Manages automated email sequences for user onboarding, engagement, and conversion.
"""

import json
import os
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from billing.tier_manager import TierLimits
from jinja2 import Template

# Database path
SHARED_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logicgate_shared.db")


class EmailTemplate:
    """Email template definitions"""

    TEMPLATES = {
        "welcome": {
            "subject": "Welcome to LogicGate - Let's Get Started",
            "body": """
Hi {{name}},

Welcome to LogicGate! We're excited to have you on board.

Your account has been created and you're ready to start managing your fleet with our unified platform.

**What's Next?**

1. Complete your onboarding wizard: {{onboarding_url}}
2. Register your first asset
3. Connect your edge node
4. Start tracking in real-time

**Your Plan:** {{tier_name}}

{% if trial_days > 0 %}
You have {{trial_days}} days of free trial to explore all features. No credit card required.
{% endif %}

If you have any questions, just reply to this email. Our team is here to help!

Best regards,
The LogicGate Team

---
LogicGate | Unified Fleet Management Platform
https://logicgate.io
            """,
        },
        "onboarding_step_1": {
            "subject": "Step 1: Register Your First Asset",
            "body": """
Hi {{name}},

Ready to get started with LogicGate? Let's register your first asset.

**Why Register Your Asset?**

- Track real-time telemetry
- Set up geofences and alerts
- Monitor battery status and location
- Analyze historical data

**Quick Start Guide:**

1. Go to your dashboard: {{dashboard_url}}
2. Click "Assets" in the navigation
3. Click "Register New Asset"
4. Enter your asset details (name, type, MAVLink ID)
5. Save and start tracking!

**Supported Asset Types:**

- Drones (DJI, Autel, custom MAVLink)
- Rovers and ground vehicles
- Heavy equipment
- Any MAVLink-compatible device

Need help? Check our documentation: {{docs_url}}

Best regards,
The LogicGate Team
            """,
        },
        "onboarding_step_2": {
            "subject": "Step 2: Connect Your Edge Node",
            "body": """
Hi {{name}},

Great progress! Now let's connect your edge node to start receiving telemetry.

**What is an Edge Node?**

An edge node is a small device that connects your assets to the LogicGate cloud. It receives MAVLink telemetry from your assets and sends it to our platform for real-time tracking.

**Setup Steps:**

1. Power on your edge node
2. Connect to your network (WiFi, cellular, or Ethernet)
3. Configure your edge node ID in LogicGate
4. Connect your assets to the edge node
5. Verify telemetry is flowing

**Don't Have an Edge Node?**

No problem! You can still use LogicGate with:
- Direct asset connections
- Simulated telemetry for testing
- Manual data import

Contact us to get an edge node: sales@logicgate.io

Best regards,
The LogicGate Team
            """,
        },
        "trial_ending_soon": {
            "subject": "Your LogicGate Trial Ends Soon",
            "body": """
Hi {{name}},

Your LogicGate trial is ending in {{days_remaining}} days.

**What You've Accomplished:**

- Registered {{asset_count}} asset(s)
- Used {{storage_used}}GB of storage
- Created {{geofence_count}} geofence(s)

**Ready to Upgrade?**

Your trial will convert to the {{tier_name}} plan (${{price}}/month) unless you:

1. Upgrade to a higher tier
2. Downgrade to Freemium
3. Cancel your account

**Upgrade Options:**

- Starter: $99/month (5 assets, 10GB storage)
- Professional: $299/month (25 assets, 50GB storage)
- Enterprise: $799/month (unlimited everything)

Manage your plan: {{billing_url}}

Questions? Reply to this email or schedule a call: {{calendar_url}}

Best regards,
The LogicGate Team
            """,
        },
        "trial_expired": {
            "subject": "Your LogicGate Trial Has Ended",
            "body": """
Hi {{name}},

Your LogicGate trial has ended.

**Your Account Status:**

Your account has been converted to the {{tier_name}} plan.

**What This Means:**

- Your data is safe and accessible
- Your assets continue to be tracked
- You'll be billed ${{price}}/month starting today
- You can upgrade, downgrade, or cancel anytime

**Want to Change Your Plan?**

- Upgrade for more assets and features
- Downgrade to Freemium (limited features)
- Cancel your account

Manage your plan: {{billing_url}}

Need help? Contact us: support@logicgate.io

Best regards,
The LogicGate Team
            """,
        },
        "usage_limit_warning": {
            "subject": "You're Approaching Your {{resource}} Limit",
            "body": """
Hi {{name}},

You're approaching your {{resource}} limit on LogicGate.

**Current Usage:** {{current_usage}} / {{limit}}

**What Happens When You Reach Your Limit:**

- You won't be able to add more {{resource}}
- Existing {{resource}} will continue to work
- Your data remains accessible

**Upgrade to Get More:**

- Starter: {{starter_limit}} {{resource}}
- Professional: {{professional_limit}} {{resource}}
- Enterprise: Unlimited {{resource}}

Upgrade now: {{upgrade_url}}

Questions? Reply to this email.

Best regards,
The LogicGate Team
            """,
        },
        "upgrade_prompt": {
            "subject": "Unlock More with LogicGate Pro",
            "body": """
Hi {{name}},

You've been using LogicGate for {{days_active}} days - great progress!

**Ready to Unlock More Features?**

Upgrade to Professional or Enterprise to access:

- Command & Control (send commands to assets)
- Advanced Analytics (deep insights and trends)
- Custom Reports (export and share data)
- API Access (integrate with your systems)
- Priority Support (faster response times)
- White Labeling (brand as your own)

**Your Current Plan:** {{current_tier}}
**Upgrade to:** Professional ($299/month) or Enterprise ($799/month)

See all features: {{features_url}}

Upgrade now: {{upgrade_url}}

Questions? Schedule a call: {{calendar_url}}

Best regards,
The LogicGate Team
            """,
        },
        "inactive_user": {
            "subject": "We Miss You - Come Back to LogicGate",
            "body": """
Hi {{name}},

We noticed you haven't logged into LogicGate in {{days_inactive}} days.

**Your Account is Still Active:**

- Your {{asset_count}} asset(s) are still registered
- Your data is safe and accessible
- Your plan is {{tier_name}}

**Quick Tips to Get Started Again:**

1. Check your asset status: {{dashboard_url}}
2. Review recent telemetry
3. Set up new geofences
4. Generate a report

**Need Help Getting Back On Track?**

- Reply to this email for assistance
- Schedule a call with our team: {{calendar_url}}
- Check our documentation: {{docs_url}}

We're here to help you succeed!

Best regards,
The LogicGate Team
            """,
        },
        "feature_announcement": {
            "subject": "New Feature: {{feature_name}}",
            "body": """
Hi {{name}},

We're excited to announce a new feature in LogicGate!

**{{feature_name}}**

{{feature_description}}

**How to Use It:**

{{feature_instructions}}

**Available On:** {{available_tiers}}

Try it now: {{dashboard_url}}

Have questions? Reply to this email or check our documentation: {{docs_url}}

Best regards,
The LogicGate Team
            """,
        },
    }

    @classmethod
    def get_template(cls, template_name: str) -> dict:
        """Get email template by name"""
        return cls.TEMPLATES.get(template_name, {})

    @classmethod
    def render_template(cls, template_name: str, context: dict) -> dict:
        """Render email template with context"""
        template = cls.get_template(template_name)

        if not template:
            return {"subject": "", "body": ""}

        # Render subject
        subject_template = Template(template["subject"])
        rendered_subject = subject_template.render(**context)

        # Render body
        body_template = Template(template["body"])
        rendered_body = body_template.render(**context)

        return {"subject": rendered_subject, "body": rendered_body}


class EmailTrigger:
    """Email trigger definitions and conditions"""

    TRIGGERS = {
        "welcome": {
            "event": "user_signup",
            "delay_minutes": 0,
            "template": "welcome",
            "priority": "high",
        },
        "onboarding_step_1": {
            "event": "user_signup",
            "delay_minutes": 1440,  # 24 hours
            "template": "onboarding_step_1",
            "priority": "medium",
        },
        "onboarding_step_2": {
            "event": "user_signup",
            "delay_minutes": 4320,  # 72 hours
            "template": "onboarding_step_2",
            "priority": "medium",
        },
        "trial_ending_soon": {
            "event": "trial_ending",
            "delay_minutes": 0,
            "template": "trial_ending_soon",
            "priority": "high",
        },
        "trial_expired": {
            "event": "trial_expired",
            "delay_minutes": 0,
            "template": "trial_expired",
            "priority": "high",
        },
        "usage_limit_warning": {
            "event": "usage_limit_reached",
            "delay_minutes": 0,
            "template": "usage_limit_warning",
            "priority": "medium",
        },
        "upgrade_prompt": {
            "event": "user_activity",
            "condition": "days_since_signup >= 7 AND tier != enterprise",
            "delay_minutes": 0,
            "template": "upgrade_prompt",
            "priority": "low",
        },
        "inactive_user": {
            "event": "user_inactivity",
            "condition": "days_inactive >= 14",
            "delay_minutes": 0,
            "template": "inactive_user",
            "priority": "low",
        },
    }

    @classmethod
    def get_trigger(cls, trigger_name: str) -> dict:
        """Get trigger configuration by name"""
        return cls.TRIGGERS.get(trigger_name, {})


class EmailQueue:
    """Email queue management"""

    def __init__(self, db_path: str = SHARED_DB_PATH):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Initialize email queue database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Email queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                template_name TEXT,
                context TEXT,
                priority TEXT DEFAULT 'medium',
                scheduled_at TIMESTAMP,
                sent_at TIMESTAMP,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Email history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_email TEXT NOT NULL,
                template_name TEXT,
                trigger_name TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        """)

        conn.commit()
        conn.close()

    def queue_email(
        self,
        recipient_email: str,
        template_name: str,
        context: dict,
        priority: str = "medium",
        delay_minutes: int = 0,
    ) -> int:
        """
        Queue an email for sending
        Returns email queue ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate scheduled time
        scheduled_at = None
        if delay_minutes > 0:
            scheduled_at = (datetime.now() + timedelta(minutes=delay_minutes)).isoformat()

        # Render template
        rendered = EmailTemplate.render_template(template_name, context)

        cursor.execute(
            """
            INSERT INTO email_queue (recipient_email, subject, body, template_name, context, priority, scheduled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                recipient_email,
                rendered["subject"],
                rendered["body"],
                template_name,
                json.dumps(context),
                priority,
                scheduled_at,
            ),
        )

        email_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return email_id

    def get_pending_emails(self) -> list[dict]:
        """Get all pending emails that are ready to send"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, recipient_email, subject, body, template_name, context
            FROM email_queue
            WHERE status = 'pending'
            AND (scheduled_at IS NULL OR scheduled_at <= CURRENT_TIMESTAMP)
            ORDER BY priority DESC, created_at ASC
        """)

        results = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "recipient_email": row[1],
                "subject": row[2],
                "body": row[3],
                "template_name": row[4],
                "context": json.loads(row[5]) if row[5] else {},
            }
            for row in results
        ]

    def mark_sent(self, email_id: int):
        """Mark email as sent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE email_queue
            SET status = 'sent', sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (email_id,),
        )

        conn.commit()
        conn.close()

    def mark_failed(self, email_id: int, error_message: str):
        """Mark email as failed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE email_queue
            SET status = 'failed', error_message = ?
            WHERE id = ?
        """,
            (error_message, email_id),
        )

        conn.commit()
        conn.close()

    def log_email_history(
        self, recipient_email: str, template_name: str, trigger_name: str, status: str
    ):
        """Log email to history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO email_history (recipient_email, template_name, trigger_name, status)
            VALUES (?, ?, ?, ?)
        """,
            (recipient_email, template_name, trigger_name, status),
        )

        conn.commit()
        conn.close()


class EmailSender:
    """Email sending functionality"""

    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = 587,
        smtp_username: str = None,
        smtp_password: str = None,
        from_email: str = "noreply@logicgate.io",
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = smtp_username or os.getenv("SMTP_USERNAME")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.from_email = from_email or os.getenv("FROM_EMAIL", "noreply@logicgate.io")

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send an email
        Returns True if successful
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Subject"] = subject

            # Attach body
            html_part = MIMEText(body, "html")
            msg.attach(html_part)

            # Send email
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()

            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)

            server.send_message(msg)
            server.quit()

            return True

        except Exception as e:
            print(f"[EMAIL SENDING ERROR] {e}")
            return False


class EmailTriggerManager:
    """Main email trigger management system"""

    def __init__(self, db_path: str = SHARED_DB_PATH):
        self.queue = EmailQueue(db_path)
        self.sender = EmailSender()

    def trigger_signup_email(
        self, user_email: str, user_name: str, company: str, tier: str, trial_days: int = 0
    ):
        """Trigger welcome email after signup"""
        try:
            from logicgate_cloud.billing.tier_manager import TierLimits

            limits = TierLimits.get_tier_limits(tier)

            context = {
                "name": user_name,
                "company": company,
                "tier_name": limits["name"],
                "tier": tier,
                "trial_days": trial_days,
                "onboarding_url": "https://logicgate.io/onboarding",
                "dashboard_url": "https://logicgate.io/portal",
            }

            # Queue welcome email
            self.queue.queue_email(user_email, "welcome", context, priority="high")

            # Queue onboarding emails
            if trial_days > 0 or tier != "freemium":
                self.queue.queue_email(
                    user_email, "onboarding_step_1", context, priority="medium", delay_minutes=1440
                )
                self.queue.queue_email(
                    user_email, "onboarding_step_2", context, priority="medium", delay_minutes=4320
                )

            print(f"[EMAIL TRIGGER] Queued signup emails for {user_email}")

        except Exception as e:
            print(f"[EMAIL TRIGGER ERROR] {e}")

    def trigger_trial_ending_email(
        self, user_email: str, user_name: str, org_id: int, days_remaining: int
    ):
        """Trigger trial ending soon email"""
        try:
            from logicgate_cloud.billing.tier_manager import TierManager

            tier_mgr = TierManager()
            status = tier_mgr.get_tier_status(org_id)

            context = {
                "name": user_name,
                "days_remaining": days_remaining,
                "tier_name": status["tier_name"],
                "price": status["price"],
                "asset_count": status["usage"].get("assets", 0),
                "storage_used": status["usage"].get("storage", 0),
                "geofence_count": status["usage"].get("geofences", 0),
                "billing_url": "https://logicgate.io/portal/billing",
                "calendar_url": "https://logicgate.io/schedule",
            }

            self.queue.queue_email(user_email, "trial_ending_soon", context, priority="high")
            print(f"[EMAIL TRIGGER] Queued trial ending email for {user_email}")

        except Exception as e:
            print(f"[EMAIL TRIGGER ERROR] {e}")

    def trigger_usage_limit_email(
        self, user_email: str, user_name: str, resource: str, current_usage: int, limit: int
    ):
        """Trigger usage limit warning email"""
        try:
            context = {
                "name": user_name,
                "resource": resource,
                "current_usage": current_usage,
                "limit": limit,
                "starter_limit": TierLimits.get_tier_limits("starter")[f"max_{resource}"],
                "professional_limit": TierLimits.get_tier_limits("professional")[f"max_{resource}"],
                "upgrade_url": "https://logicgate.io/portal/billing",
            }

            self.queue.queue_email(user_email, "usage_limit_warning", context, priority="medium")
            print(f"[EMAIL TRIGGER] Queued usage limit email for {user_email}")

        except Exception as e:
            print(f"[EMAIL TRIGGER ERROR] {e}")

    def process_queue(self):
        """Process pending emails in the queue"""
        pending_emails = self.queue.get_pending_emails()

        for email in pending_emails:
            success = self.sender.send_email(
                email["recipient_email"], email["subject"], email["body"]
            )

            if success:
                self.queue.mark_sent(email["id"])
                self.queue.log_email_history(
                    email["recipient_email"], email["template_name"], "manual", "sent"
                )
                print(
                    f"[EMAIL SENT] To: {email['recipient_email']}, Template: {email['template_name']}"
                )
            else:
                self.queue.mark_failed(email["id"], "Sending failed")
                self.queue.log_email_history(
                    email["recipient_email"], email["template_name"], "manual", "failed"
                )
                print(f"[EMAIL FAILED] To: {email['recipient_email']}")


# Convenience functions
def send_welcome_email(
    user_email: str, user_name: str, company: str, tier: str, trial_days: int = 0
):
    """Send welcome email after signup"""
    manager = EmailTriggerManager()
    manager.trigger_signup_email(user_email, user_name, company, tier, trial_days)
    manager.process_queue()


def send_trial_ending_email(user_email: str, user_name: str, org_id: int, days_remaining: int):
    """Send trial ending soon email"""
    manager = EmailTriggerManager()
    manager.trigger_trial_ending_email(user_email, user_name, org_id, days_remaining)
    manager.process_queue()


def send_usage_limit_email(
    user_email: str, user_name: str, resource: str, current_usage: int, limit: int
):
    """Send usage limit warning email"""
    manager = EmailTriggerManager()
    manager.trigger_usage_limit_email(user_email, user_name, resource, current_usage, limit)
    manager.process_queue()


if __name__ == "__main__":
    # Test email triggers
    print("Testing Email Triggers...")

    # Test welcome email
    send_welcome_email("test@example.com", "Test User", "Test Company", "professional", 14)

    # Test trial ending email
    # send_trial_ending_email("test@example.com", "Test User", 1, 3)

    # Test usage limit email
    # send_usage_limit_email("test@example.com", "Test User", "assets", 2, 3)

    print("Email triggers test complete!")
