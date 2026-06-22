"""
Email sending tool — dispatches follow-up emails via SMTP or SendGrid.

Falls back to a simulated log in development if credentials are absent.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_NAME = os.getenv("FROM_NAME", "AI Voice Assistant")


async def send_email(
    to_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Send a plain-text email.

    Returns:
        dict with keys: success, message
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.info(
            f"📧 [SIMULATED] Email to {to_email} | Subject: {subject}\n{body}"
        )
        return {
            "success": True,
            "message": (
                f"✅ Follow-up email sent to {to_email}. "
                "[Simulated — configure SMTP_USER and SMTP_PASSWORD in .env]"
            ),
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        logger.info(f"📧 Email sent to {to_email}: {subject}")
        return {
            "success": True,
            "message": f"✅ Email sent to {to_email} with subject: '{subject}'.",
        }

    except smtplib.SMTPAuthenticationError:
        msg = "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD."
        logger.error(f"❌ Email tool error: {msg}")
        return {"success": False, "message": msg}
    except smtplib.SMTPException as e:
        msg = f"SMTP error: {e}"
        logger.error(f"❌ Email tool error: {msg}")
        return {"success": False, "message": msg}
    except Exception as e:
        msg = f"Failed to send email: {e}"
        logger.error(f"❌ Email tool error: {msg}")
        return {"success": False, "message": msg}
