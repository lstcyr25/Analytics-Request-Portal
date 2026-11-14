
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import resend
import streamlit as st
from dotenv import load_dotenv

from database.supabase_client import (
    get_service_role_client,
    get_supabase_client,
)


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

def _get_config_value(name: str):
    """Read configuration from environment variables or Streamlit secrets."""

    value = os.getenv(name)

    if value:
        return value

    try:
        return st.secrets.get(name)
    except Exception:
        return None


def get_email_template(event_type: str) -> dict:
    """Retrieve an active email template using the trusted backend client."""

    if not event_type or not event_type.strip():
        return {
            "success": False,
            "error": "Event type is required.",
        }

    try:
        supabase = get_service_role_client()

        response = (
            supabase.table("email_templates")
            .select("event_type, subject_template, body_template")
            .eq("event_type", event_type.strip())
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )

        if not response.data:
            return {
                "success": False,
                "error": f"No active template found for '{event_type.strip()}'.",
            }

        return {
            "success": True,
            "template": response.data,
        }

    except Exception:
        logger.exception("Failed to retrieve email template.")

        return {
            "success": False,
            "error": "Could not retrieve the email template.",
        }


def render_email_template(event_type: str, values: dict) -> dict:
    """Replace double-brace placeholders in an email template."""

    if not isinstance(values, dict):
        return {
            "success": False,
            "error": "Template values must be provided as a dictionary.",
        }

    result = get_email_template(event_type)

    if not result["success"]:
        return result

    template = result["template"]

    subject = template["subject_template"]
    body = template["body_template"]

    for key, value in values.items():
        placeholder = "{{" + str(key) + "}}"
        replacement = str(value)

        subject = subject.replace(placeholder, replacement)
        body = body.replace(placeholder, replacement)

    return {
        "success": True,
        "subject": subject,
        "body": body,
    }


def log_notification(
    recipient_id: int,
    event_type: str,
    subject: str,
    delivery_status: str,
    request_id: int | None = None,
    error_message: str | None = None,
) -> dict:
    """Record notification delivery using the trusted backend client."""

    if not recipient_id:
        return {
            "success": False,
            "error": "Recipient ID is required.",
        }

    if not event_type or not event_type.strip():
        return {
            "success": False,
            "error": "Event type is required.",
        }

    if delivery_status not in ("sent", "failed"):
        return {
            "success": False,
            "error": "Invalid delivery status.",
        }

    try:
        supabase = get_service_role_client()

        response = (
            supabase.table("notification_log")
            .insert({
                "request_id": request_id,
                "recipient_id": recipient_id,
                "channel": "email",
                "event_type": event_type.strip(),
                "subject": subject,
                "delivery_status": delivery_status,
                "error_message": error_message,
            })
            .select("notification_id")
            .single()
            .execute()
        )

        return {
            "success": True,
            "notification_id": response.data["notification_id"],
            "message": "Notification logged successfully.",
        }

    except Exception:
        logger.exception("Failed to record notification.")

        return {
            "success": False,
            "error": "Could not record the notification.",
        }


def send_email(
    recipient_email: str,
    subject: str,
    body: str,
) -> dict:
    """Send a plain-text email through Resend."""

    if not recipient_email or not recipient_email.strip():
        return {
            "success": False,
            "error": "Recipient email is required.",
        }

    if not subject or not subject.strip():
        return {
            "success": False,
            "error": "Email subject is required.",
        }

    if body is None or not str(body).strip():
        return {
            "success": False,
            "error": "Email body is required.",
        }

    api_key = _get_config_value("RESEND_API_KEY")
    email_from = _get_config_value("EMAIL_FROM")

    if not api_key:
        return {
            "success": False,
            "error": "Missing Resend API key.",
        }

    if not email_from:
        return {
            "success": False,
            "error": "Missing sender email address.",
        }

    try:
        resend.api_key = api_key

        response = resend.Emails.send({
            "from": email_from,
            "to": [recipient_email.strip()],
            "subject": subject.strip(),
            "text": body,
        })

        email_id = response.get("id")

        if not email_id:
            logger.error("Resend returned a response without an email ID.")

            return {
                "success": False,
                "error": "Email provider did not return an email ID.",
            }

        return {
            "success": True,
            "email_id": email_id,
            "message": "Email accepted by Resend.",
        }

    except Exception:
        logger.exception("Resend email submission failed.")

        return {
            "success": False,
            "error": "Email provider could not accept the email.",
        }


def send_templated_email(
    recipient_email: str,
    event_type: str,
    values: dict,
) -> dict:
    """Render a Supabase email template and send it through Resend."""

    rendered = render_email_template(event_type, values)

    if not rendered["success"]:
        return rendered

    result = send_email(
        recipient_email=recipient_email,
        subject=rendered["subject"],
        body=rendered["body"],
    )

    if not result["success"]:
        return result

    return {
        "success": True,
        "email_id": result["email_id"],
        "subject": rendered["subject"],
        "message": "Templated email accepted by Resend.",
    }



def create_in_app_notification(
    recipient_id: int,
    event_type: str,
    title: str,
    message: str,
    request_id: int | None = None,
) -> dict:
    """Create an in-app notification using the trusted backend client."""

    try:
        supabase = get_service_role_client()

        response = (
            supabase.table("user_notifications")
            .insert({
                "recipient_id": recipient_id,
                "request_id": request_id,
                "event_type": event_type,
                "title": title,
                "message": message,
            })
            .select("notification_id")
            .single()
            .execute()
        )

        return {
            "success": True,
            "notification_id": response.data["notification_id"],
        }

    except Exception:
        logger.exception("Failed to create in-app notification.")

        return {
            "success": False,
            "error": "Could not create in-app notification.",
        }


def get_user_notifications(limit: int = 15) -> dict:
    """Retrieve the authenticated user's recent notifications."""

    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("user_notifications")
            .select(
                "notification_id, request_id, event_type, "
                "title, message, is_read, created_at"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        notifications = response.data or []

        return {
            "success": True,
            "notifications": notifications,
            "unread_count": sum(
                1 for item in notifications if not item["is_read"]
            ),
        }

    except Exception:
        logger.exception("Failed to retrieve in-app notifications.")

        return {
            "success": False,
            "error": "Could not retrieve notifications.",
            "notifications": [],
            "unread_count": 0,
        }


def mark_notification_read(notification_id: int) -> dict:
    """Mark one of the authenticated user's notifications as read."""

    try:
        supabase = get_supabase_client()

        supabase.table("user_notifications").update({
            "is_read": True,
            "read_at": datetime.now(timezone.utc).isoformat(),
        }).eq(
            "notification_id", notification_id
        ).execute()

        return {"success": True}

    except Exception:
        logger.exception("Failed to mark notification as read.")

        return {
            "success": False,
            "error": "Could not update notification.",
        }


def mark_all_notifications_read() -> dict:
    """Mark all unread notifications belonging to the current user as read."""

    try:
        supabase = get_supabase_client()

        supabase.table("user_notifications").update({
            "is_read": True,
            "read_at": datetime.now(timezone.utc).isoformat(),
        }).eq(
            "is_read", False
        ).execute()

        return {"success": True}

    except Exception:
        logger.exception("Failed to mark all notifications as read.")

        return {
            "success": False,
            "error": "Could not update all notifications.",
        }