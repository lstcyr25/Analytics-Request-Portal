
from database.supabase_client import (
    get_supabase_client,
    get_service_role_client,
)
from services.notification_service import (
    render_email_template,
    send_email,
    log_notification,
    create_in_app_notification,
)

from services.analytics_service import _require_analytics_manager


def _log_notification_failure(
    recipient_id: int | None,
    event_type: str,
    request_id: int,
    error_message: str,
    subject: str | None = None,
) -> dict:
    """Record a failed notification when the recipient is known."""

    if not recipient_id:
        return {
            "success": False,
            "error": "Recipient ID is unavailable; failure could not be logged.",
        }

    return log_notification(
        recipient_id=recipient_id,
        event_type=event_type,
        subject=subject or "Notification processing failed",
        delivery_status="failed",
        request_id=request_id,
        error_message=error_message,
    )


def assign_request(
    request_id: int,
    analyst_id: int,
    notification_recipient_override: str | None = None,
) -> dict:
    """Assign or reassign a request and notify its requester."""

    supabase = get_supabase_client()

    if not analyst_id:
        return {
            "success": False,
            "error": "An analyst must be selected.",
        }

    try:
        supabase.rpc(
            "manager_assign_request",
            {
                "p_request_id": request_id,
                "p_analyst_id": analyst_id,
            },
        ).execute()

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    notification = {
        "success": False,
        "message": "Assignment succeeded, but notification was not sent.",
    }

    requester_id = None
    notification_subject = None

    try:
        request_response = (
            supabase.table("requests")
            .select(
                "request_id, title, requester_id, assigned_to, expected_date"
            )
            .eq("request_id", request_id)
            .maybe_single()
            .execute()
        )

        request = request_response.data

        if not request:
            raise ValueError("Could not retrieve the assigned request.")

        requester_id = request["requester_id"]

        service_supabase = get_service_role_client()

        requester_response = (
            service_supabase.table("users")
            .select("user_id, full_name, email")
            .eq("user_id", requester_id)
            .maybe_single()
            .execute()
        )

        requester = requester_response.data

        if not requester or not requester.get("email"):
            raise ValueError("Could not retrieve the requester's email.")

        analyst_response = (
            service_supabase.table("users")
            .select("user_id, full_name")
            .eq("user_id", request["assigned_to"])
            .maybe_single()
            .execute()
        )

        analyst = analyst_response.data

        if not analyst:
            raise ValueError("Could not retrieve the assigned analyst.")

        create_in_app_notification(
            recipient_id=requester_id,
            request_id=request_id,
            event_type="request_assigned",
            title="Analyst assigned",
            message=(
                f'Your request "{request["title"]}" '
                "has been assigned to an analyst."
            ),
        )

        create_in_app_notification(
            recipient_id=request["assigned_to"],
            request_id=request_id,
            event_type="request_assigned",
            title="New request assigned",
            message=(
                f'You have been assigned request #{request_id}: '
                f'"{request["title"]}".'
            ),
        )

        rendered = render_email_template(
            "request_assigned",
            {
                "requester_name": requester.get("full_name") or "User",
                "request_title": request["title"],
                "analyst_name": analyst.get("full_name") or "Assigned Analyst",
                "request_id": request["request_id"],
                "expected_date": (
                    request["expected_date"] or "Not yet determined"
                ),
            },
        )

        if not rendered["success"]:
            raise ValueError(rendered["error"])

        notification_subject = rendered["subject"]

        if (
            notification_recipient_override is not None
            and notification_recipient_override != "delivered@resend.dev"
        ):
            raise ValueError("Invalid notification test recipient.")

        recipient_email = (
            notification_recipient_override or requester["email"]
        )

        email_result = send_email(
            recipient_email=recipient_email,
            subject=rendered["subject"],
            body=rendered["body"],
        )

        log_result = log_notification(
            recipient_id=requester["user_id"],
            event_type="request_assigned",
            subject=rendered["subject"],
            delivery_status=(
                "sent" if email_result["success"] else "failed"
            ),
            request_id=request_id,
            error_message=email_result.get("error"),
        )

        notification = {
            "success": email_result["success"],
            "message": (
                "Assignment email accepted by Resend."
                if email_result["success"]
                else "Assignment succeeded, but email sending failed."
            ),
            "email_error": email_result.get("error"),
            "log_success": log_result["success"],
        }

    except Exception as error:
        log_result = _log_notification_failure(
            recipient_id=requester_id,
            event_type="request_assigned",
            request_id=request_id,
            error_message=str(error),
            subject=notification_subject,
        )

        notification = {
            "success": False,
            "message": (
                "Assignment succeeded, but notification processing failed."
            ),
            "error": str(error),
            "log_success": log_result["success"],
        }

    return {
        "success": True,
        "message": "Request assigned successfully.",
        "notification": notification,
    }


def cancel_request(request_id: int, reason: str) -> dict:
    """Cancel a request and notify its business requester."""

    supabase = get_supabase_client()

    if not reason or not reason.strip():
        return {
            "success": False,
            "error": "A cancellation reason is required.",
        }

    # Perform the secure manager cancellation first.
    try:
        supabase.rpc(
            "manager_cancel_request",
            {
                "p_request_id": request_id,
                "p_reason": reason.strip(),
            },
        ).execute()

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    # Cancellation succeeded. Notification processing is independent.
    notification = {
        "success": False,
        "message": "Cancellation succeeded, but notification was not sent.",
    }

    requester_id = None
    notification_subject = None

    try:
        service_supabase = get_service_role_client()

        request_response = (
            service_supabase.table("requests")
            .select("request_id, title, requester_id")
            .eq("request_id", request_id)
            .maybe_single()
            .execute()
        )

        request = request_response.data

        if not request:
            raise ValueError("Could not retrieve the cancelled request.")

        requester_id = request["requester_id"]

        requester_response = (
            service_supabase.table("users")
            .select("user_id, full_name, email")
            .eq("user_id", requester_id)
            .maybe_single()
            .execute()
        )

        requester = requester_response.data

        if not requester or not requester.get("email"):
            raise ValueError("Could not retrieve the requester's email.")

        rendered = render_email_template(
            "request_cancelled",
            {
                "requester_name": requester.get("full_name") or "User",
                "request_title": request["title"],
                "request_id": request_id,
                "reason": reason.strip(),
            },
        )

        if not rendered["success"]:
            raise ValueError(rendered["error"])

        notification_subject = rendered["subject"]

        email_result = send_email(
            recipient_email=requester["email"],
            subject=rendered["subject"],
            body=rendered["body"],
        )

        log_result = log_notification(
            recipient_id=requester["user_id"],
            event_type="request_cancelled",
            subject=rendered["subject"],
            delivery_status=(
                "sent" if email_result["success"] else "failed"
            ),
            request_id=request_id,
            error_message=email_result.get("error"),
        )

        notification = {
            "success": email_result["success"],
            "message": (
                "Cancellation email accepted by Resend."
                if email_result["success"]
                else "Cancellation succeeded, but email sending failed."
            ),
            "email_error": email_result.get("error"),
            "log_success": log_result["success"],
        }

    except Exception as error:
        log_result = _log_notification_failure(
            recipient_id=requester_id,
            event_type="request_cancelled",
            request_id=request_id,
            error_message=str(error),
            subject=notification_subject,
        )

        notification = {
            "success": False,
            "message": (
                "Cancellation succeeded, but notification processing failed."
            ),
            "error": str(error),
            "log_success": log_result["success"],
        }

    return {
        "success": True,
        "message": "Request cancelled successfully.",
        "notification": notification,
    }


def get_analysts() -> dict:
    """Retrieve active analysts for manager assignment workflows."""

    supabase = get_supabase_client()

    try:
        response = (
            supabase.table("users")
            .select("user_id, full_name, email")
            .eq("role", "analyst")
            .eq("is_active", True)
            .order("full_name")
            .execute()
        )

        return {
            "success": True,
            "analysts": response.data or [],
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

def get_all_requests() -> dict:
    """Retrieve all requests for authorized analytics managers."""

    supabase = get_supabase_client()

    try:
        # Verify that the current user is an active analytics manager.
        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {
                "success": False,
                "error": error_message,
            }

        # Retrieve requests visible under the current user's RLS policies.
        requests_response = (
            supabase.table("requests")
            .select(
                """
                request_id,
                title,
                description,
                needed_date,
                expected_date,
                is_overdue,
                created_at,
                assigned_at,
                resolved_at,
                requester_id,
                assigned_to,
                type_id,
                priority_id,
                status_id
                """
            )
            .order("created_at", desc=True)
            .execute()
        )

        # Retrieve user names using the authenticated client.
        users_response = (
            supabase.table("users")
            .select("user_id, full_name, email, role")
            .execute()
        )

        # Create a lookup dictionary for user information.
        users_by_id = {
            user["user_id"]: user
            for user in (users_response.data or [])
        }

        # Add readable requester and analyst information.
        requests = []

        for request in requests_response.data or []:
            requester = users_by_id.get(request["requester_id"])
            analyst = users_by_id.get(request["assigned_to"])

            request["requester_name"] = (
                requester.get("full_name", "Unknown")
                if requester
                else "Unknown"
            )

            request["requester_email"] = (
                requester.get("email", "")
                if requester
                else ""
            )

            request["analyst_name"] = (
                analyst.get("full_name", "Unassigned")
                if analyst
                else "Unassigned"
            )

            requests.append(request)

        return {
            "success": True,
            "data": requests,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def get_user_management_data() -> dict:
    """Retrieve active users and recent role-change history for managers."""

    supabase = get_supabase_client()

    try:
        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {
                "success": False,
                "error": error_message,
            }

        users_response = (
            supabase.table("users")
            .select("user_id, full_name, email, role, is_active")
            .eq("is_active", True)
            .order("full_name")
            .execute()
        )

        history_response = (
            supabase.table("user_role_history")
            .select(
                "history_id, target_user_id, changed_by, "
                "old_role, new_role, reason, changed_at"
            )
            .order("changed_at", desc=True)
            .limit(50)
            .execute()
        )

        users = users_response.data or []
        users_by_id = {
            user["user_id"]: user
            for user in users
        }

        history = []

        for record in history_response.data or []:
            target = users_by_id.get(record["target_user_id"], {})
            manager = users_by_id.get(record["changed_by"], {})

            record["target_user_name"] = target.get(
                "full_name", f"User #{record['target_user_id']}"
            )
            record["manager_name"] = manager.get(
                "full_name", f"User #{record['changed_by']}"
            )

            history.append(record)

        return {
            "success": True,
            "users": users,
            "history": history,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def change_user_role(
    target_user_id: int,
    new_role: str,
    reason: str | None = None,
) -> dict:
    """Change a user's role through the protected manager RPC."""

    supabase = get_supabase_client()

    try:
        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {
                "success": False,
                "error": error_message,
            }

        supabase.rpc(
            "manager_change_user_role",
            {
                "p_target_user_id": target_user_id,
                "p_new_role": new_role,
                "p_reason": reason,
            },
        ).execute()

        return {
            "success": True,
            "message": "User role updated successfully.",
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }
