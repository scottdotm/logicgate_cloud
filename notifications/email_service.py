"""
Email Notification Service for LogicGate SaaS

This service handles:
- Transactional emails (password resets, account verification)
- Alert notifications (asset offline, subscription issues)
- Billing notifications (invoices, payment failures)
- System notifications (maintenance, updates)
"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending notifications"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_email: str,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.use_tls = use_tls

    def send_email(
        self, to_email: str, subject: str, html_content: str, text_content: str = None
    ) -> bool:
        """Send an email"""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Subject"] = subject

            # Add text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, "plain")
                msg.attach(text_part)

            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_password_reset(
        self, to_email: str, reset_token: str, tenant_name: str = "LogicGate"
    ) -> bool:
        """Send password reset email"""
        reset_url = f"http://127.0.0.1:8080/reset-password?token={reset_token}"

        subject = f"Password Reset Request - {tenant_name}"

        text_content = f"""
You requested a password reset for your {tenant_name} account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #00ff66; color: #1a1a2e; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
        .button {{ display: inline-block; background-color: #00ff66; color: #1a1a2e;
                  padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{tenant_name}</h1>
        </div>
        <div class="content">
            <h2>Password Reset Request</h2>
            <p>You requested a password reset for your {tenant_name} account.</p>
            <p>Click the button below to reset your password:</p>
            <center>
                <a href="{reset_url}" class="button">Reset Password</a>
            </center>
            <p>Or copy and paste this link:</p>
            <p><code>{reset_url}</code></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you did not request this password reset, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} {tenant_name}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_content, text_content)

    def send_welcome_email(
        self, to_email: str, user_name: str, tenant_name: str = "LogicGate"
    ) -> bool:
        """Send welcome email to new user"""
        subject = f"Welcome to {tenant_name}!"

        text_content = f"""
Welcome to {tenant_name}, {user_name}!

Your account has been successfully created. You can now log in to access your dashboard.

Login URL: http://127.0.0.1:8080/login

If you have any questions, please contact support.
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #00ff66; color: #1a1a2e; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
        .button {{ display: inline-block; background-color: #00ff66; color: #1a1a2e;
                  padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{tenant_name}</h1>
        </div>
        <div class="content">
            <h2>Welcome, {user_name}!</h2>
            <p>Your account has been successfully created. You can now log in to access your dashboard.</p>
            <center>
                <a href="http://127.0.0.1:8080/login" class="button">Login to Dashboard</a>
            </center>
            <p>If you have any questions, please contact support.</p>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} {tenant_name}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_content, text_content)

    def send_invoice_notification(
        self,
        to_email: str,
        invoice_amount: str,
        invoice_url: str,
        due_date: str,
        tenant_name: str = "LogicGate",
    ) -> bool:
        """Send invoice notification"""
        subject = f"Invoice Available - {tenant_name}"

        text_content = f"""
Your invoice for ${invoice_amount} is now available.

Amount: ${invoice_amount}
Due Date: {due_date}

View your invoice: {invoice_url}

Thank you for your business!
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #00ff66; color: #1a1a2e; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
        .button {{ display: inline-block; background-color: #00ff66; color: #1a1a2e;
                  padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{tenant_name}</h1>
        </div>
        <div class="content">
            <h2>Invoice Available</h2>
            <p>Your invoice is now available.</p>
            <p><strong>Amount:</strong> ${invoice_amount}</p>
            <p><strong>Due Date:</strong> {due_date}</p>
            <center>
                <a href="{invoice_url}" class="button">View Invoice</a>
            </center>
            <p>Thank you for your business!</p>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} {tenant_name}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_content, text_content)

    def send_payment_failed(
        self, to_email: str, amount: str, tenant_name: str = "LogicGate"
    ) -> bool:
        """Send payment failed notification"""
        subject = f"Payment Failed - {tenant_name}"

        text_content = f"""
We were unable to process your payment of ${amount}.

Please update your payment information to avoid service interruption.

Update payment: http://127.0.0.1:8080/portal/subscription

If you believe this is an error, please contact support.
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #ff4444; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
        .button {{ display: inline-block; background-color: #ff4444; color: white;
                  padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Payment Failed</h1>
        </div>
        <div class="content">
            <h2>We were unable to process your payment</h2>
            <p><strong>Amount:</strong> ${amount}</p>
            <p>Please update your payment information to avoid service interruption.</p>
            <center>
                <a href="http://127.0.0.1:8080/portal/subscription" class="button">Update Payment</a>
            </center>
            <p>If you believe this is an error, please contact support.</p>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} {tenant_name}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_content, text_content)

    def send_asset_offline_alert(
        self, to_email: str, asset_name: str, last_seen: str, tenant_name: str = "LogicGate"
    ) -> bool:
        """Send asset offline alert"""
        subject = f"Asset Offline Alert - {asset_name}"

        text_content = f"""
Asset {asset_name} has gone offline.

Last seen: {last_seen}

Please check the asset status in your dashboard.

Dashboard: http://127.0.0.1:8080/portal
"""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #ff9800; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
        .button {{ display: inline-block; background-color: #ff9800; color: white;
                  padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Asset Offline Alert</h1>
        </div>
        <div class="content">
            <h2>{asset_name} has gone offline</h2>
            <p><strong>Last seen:</strong> {last_seen}</p>
            <p>Please check the asset status in your dashboard.</p>
            <center>
                <a href="http://127.0.0.1:8080/portal" class="button">View Dashboard</a>
            </center>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} {tenant_name}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_content, text_content)


def get_email_service() -> EmailService | None:
    """Get email service instance from environment variables"""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@logicgate.io")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not all([smtp_host, smtp_username, smtp_password]):
        logger.warning("Email service not configured - missing environment variables")
        return None

    return EmailService(smtp_host, smtp_port, smtp_username, smtp_password, from_email, use_tls)
