
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
from datetime import datetime
from zoneinfo import ZoneInfo


def _log_failed_notification(
    request_id: int,
    recipient_id: int | None,
    event_type: str,
    error_message: str,
    subject: str | None = None,
) -> dict:
    """Log a failed notification when the recipient is known."""

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


def _notify_requester(
    request_id: int,
    requester_id: int,
    requester_email: str,
    event_type: str,
    values: dict,
) -> dict:
    """Send and log a templated email without affecting the main operation."""

    subject = None
    log_attempted = False

    try:
        rendered = render_email_template(event_type, values)

        if not rendered["success"]:
            error_message = rendered.get(
                "error",
                "Template rendering failed.",
            )

            log_attempted = True
            log_result = _log_failed_notification(
                request_id=request_id,
                recipient_id=requester_id,
                event_type=event_type,
                error_message=error_message,
            )

            return {
                "success": False,
                "message": "Email template could not be rendered.",
                "email_error": error_message,
                "log_success": log_result["success"],
            }

        subject = rendered["subject"]

        email_result = send_email(
            requester_email,
            subject,
            rendered["body"],
        )

        email_error = (
            None
            if email_result["success"]
            else email_result.get("error", "Email sending failed.")
        )

        log_attempted = True
        log_result = log_notification(
            recipient_id=requester_id,
            event_type=event_type,
            subject=subject,
            delivery_status=(
                "sent" if email_result["success"] else "failed"
            ),
            request_id=request_id,
            error_message=email_error,
        )

        return {
            "success": email_result["success"],
            "message": email_result.get(
                "message",
                "Email processing finished.",
            ),
            "email_error": email_error,
            "log_success": log_result["success"],
        }

    except Exception as error:
        log_result = {
            "success": False,
            "error": "Notification failure could not be logged.",
        }

        if not log_attempted:
            try:
                log_result = _log_failed_notification(
                    request_id=request_id,
                    recipient_id=requester_id,
                    event_type=event_type,
                    error_message=str(error),
                    subject=subject,
                )
            except Exception:
                log_result = {
                    "success": False,
                    "error": "Could not record notification failure.",
                }

        return {
            "success": False,
            "message": "Notification processing failed.",
            "email_error": str(error),
            "log_success": log_result["success"],
        }


def _get_requester_details(request_id: int) -> dict:
    """Retrieve request and requester details for notifications."""

    supabase = get_supabase_client()
    service_supabase = get_service_role_client()

    request_response = (
        supabase.table("requests")
        .select("request_id, title, requester_id")
        .eq("request_id", request_id)
        .maybe_single()
        .execute()
    )

    if not request_response.data:
        return {
            "success": False,
            "error": "Request details could not be retrieved.",
        }

    request = request_response.data

    requester_response = (
        service_supabase.table("users")
        .select("user_id, full_name, email")
        .eq("user_id", request["requester_id"])
        .maybe_single()
        .execute()
    )

    if not requester_response.data:
        return {
            "success": False,
            "error": "Requester profile could not be retrieved.",
        }

    requester = requester_response.data

    if not requester.get("email"):
        return {
            "success": False,
            "error": "Requester does not have an email address.",
        }

    return {
        "success": True,
        "request": request,
        "requester": requester,
    }


def _send_status_notification(
    request_id: int,
    new_status_id: int,
) -> dict:
    """Retrieve request details and notify its business requester."""

    supabase = get_supabase_client()

    try:
        details = _get_requester_details(request_id)

        if not details["success"]:
            return {
                "success": False,
                "message": details["error"],
            }

        request = details["request"]
        requester = details["requester"]

        status_response = (
            supabase.table("statuses")
            .select("status_name")
            .eq("status_id", new_status_id)
            .maybe_single()
            .execute()
        )

        if not status_response.data:
            return {
                "success": False,
                "message": "Updated status could not be retrieved.",
            }

        user_id_response = supabase.rpc(
            "current_app_user_id"
        ).execute()

        analyst_id = user_id_response.data

        analyst_response = (
            supabase.table("users")
            .select("full_name")
            .eq("user_id", analyst_id)
            .maybe_single()
            .execute()
        )

        analyst_name = (
            analyst_response.data["full_name"]
            if analyst_response.data
            else "Your analyst"
        )

        status_name = status_response.data["status_name"]

        if new_status_id == 5:
            create_in_app_notification(
                recipient_id=requester["user_id"],
                request_id=request_id,
                event_type="work_awaiting_confirmation",
                title="Work ready for review",
                message=(
                    f'{analyst_name} submitted work for '
                    f'"{request["title"]}". Review the deliverables '
                    "and confirm completion or request changes."
                ),
            )
        else:
            create_in_app_notification(
                recipient_id=requester["user_id"],
                request_id=request_id,
                event_type="request_status_changed",
                title="Request status updated",
                message=(
                    f'Your request "{request["title"]}" '
                    f'has been updated to {status_name}.'
                ),
            )

        create_in_app_notification(
            recipient_id=analyst_id,
            request_id=request_id,
            event_type="analyst_status_updated",
            title="Request status updated",
            message=(
                f'Your request "{request["title"]}" '
                f'is now marked as {status_name}.'
            ),
        )

        if new_status_id == 5:
            event_type = "request_completed"

            values = {
                "requester_name": requester.get("full_name") or "User",
                "request_title": request["title"],
                "request_id": request_id,
            }

        else:
            event_type = "status_changed"

            values = {
                "recipient_name": requester.get("full_name") or "User",
                "request_title": request["title"],
                "request_id": request_id,
                "new_status": status_response.data["status_name"],
                "updated_by": analyst_name,
            }

        return _notify_requester(
            request_id=request_id,
            requester_id=requester["user_id"],
            requester_email=requester["email"],
            event_type=event_type,
            values=values,
        )

    except Exception as error:
        return {
            "success": False,
            "message": "Could not process status notification.",
            "email_error": str(error),
        }


def _send_deadline_extension_notification(
    request_id: int,
    new_expected_date: str,
    reason: str,
) -> dict:
    """Notify the business requester about an approved deadline extension."""

    try:
        details = _get_requester_details(request_id)

        if not details["success"]:
            return {
                "success": False,
                "message": details["error"],
            }

        request = details["request"]
        requester = details["requester"]

        values = {
            "requester_name": requester.get("full_name") or "User",
            "request_title": request["title"],
            "request_id": request_id,
            "new_expected_date": new_expected_date,
            "reason": reason,
        }

        return _notify_requester(
            request_id=request_id,
            requester_id=requester["user_id"],
            requester_email=requester["email"],
            event_type="deadline_extended",
            values=values,
        )

    except Exception as error:
        return {
            "success": False,
            "message": "Could not process deadline notification.",
            "email_error": str(error),
        }


def update_request_status(
    request_id: int,
    new_status_id: int,
    expected_date: str | None = None,
    reason: str | None = None,
) -> dict:
    """Update an assigned request and notify its requester."""

    supabase = get_supabase_client()

    try:
        supabase.rpc(
            "analyst_update_request",
            {
                "p_request_id": request_id,
                "p_new_status_id": new_status_id,
                "p_new_expected_date": expected_date,
                "p_changed_reason": reason,
            },
        ).execute()

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    notification = _send_status_notification(
        request_id=request_id,
        new_status_id=new_status_id,
    )

    return {
        "success": True,
        "message": "Request status updated successfully.",
        "notification": notification,
    }


def add_internal_note(request_id: int, note: str) -> dict:
    """Add a private internal note to an assigned request."""

    supabase = get_supabase_client()

    if not isinstance(note, str) or not note.strip():
        return {
            "success": False,
            "error": "Note cannot be empty.",
        }

    try:
        supabase.rpc(
            "analyst_add_internal_note",
            {
                "p_request_id": request_id,
                "p_note": note.strip(),
            },
        ).execute()

        return {
            "success": True,
            "message": "Internal note added successfully.",
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def request_deadline_extension(
    request_id: int,
    new_expected_date: str,
    reason: str,
) -> dict:
    """Request a new expected delivery date and notify the requester."""

    supabase = get_supabase_client()

    if (
        not isinstance(new_expected_date, str)
        or not new_expected_date.strip()
    ):
        return {
            "success": False,
            "error": "New expected date is required.",
        }

    if not isinstance(reason, str) or not reason.strip():
        return {
            "success": False,
            "error": "An extension reason is required.",
        }

    new_expected_date = new_expected_date.strip()
    reason = reason.strip()

    try:
        supabase.rpc(
            "analyst_request_deadline_extension",
            {
                "p_request_id": request_id,
                "p_new_expected_date": new_expected_date,
                "p_reason": reason,
            },
        ).execute()

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    notification = _send_deadline_extension_notification(
        request_id=request_id,
        new_expected_date=new_expected_date,
        reason=reason,
    )

    return {
        "success": True,
        "message": "Deadline extension recorded successfully.",
        "notification": notification,
    }


def _send_escalation_notifications(request_id: int) -> dict:
    """Notify the designated manager or all active managers about an escalation."""

    service_supabase = get_service_role_client()

    try:
        request_response = (
            service_supabase.table("requests")
            .select("request_id, title")
            .eq("request_id", request_id)
            .maybe_single()
            .execute()
        )

        if not request_response.data:
            return {
                "success": False,
                "message": "Request not found.",
            }

        request = request_response.data

        escalation_response = (
            service_supabase.table("escalations")
            .select("escalated_by, reassigned_to, reason")
            .eq("request_id", request_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not escalation_response.data:
            return {
                "success": False,
                "message": "Escalation record not found.",
            }

        escalation = escalation_response.data[0]

        analyst_response = (
            service_supabase.table("users")
            .select("full_name")
            .eq("user_id", escalation["escalated_by"])
            .maybe_single()
            .execute()
        )

        analyst_name = (
            analyst_response.data["full_name"]
            if analyst_response.data
            else "An analyst"
        )

        recipients = []

        # If a specific manager was selected, verify that the manager is active.
        if escalation["reassigned_to"] is not None:
            target_response = (
                service_supabase.table("users")
                .select("user_id, full_name, email, role, is_active")
                .eq("user_id", escalation["reassigned_to"])
                .maybe_single()
                .execute()
            )

            target = target_response.data

            if (
                target
                and target["role"] == "analytics_manager"
                and target["is_active"]
            ):
                recipients = [target]

        # Otherwise, notify all active analytics managers.
        if not recipients:
            managers_response = (
                service_supabase.table("users")
                .select("user_id, full_name, email")
                .eq("role", "analytics_manager")
                .eq("is_active", True)
                .execute()
            )

            recipients = managers_response.data or []

        if not recipients:
            return {
                "success": False,
                "message": "No active analytics managers were found.",
            }

        results = []

        for manager in recipients:
            if not manager.get("email"):
                error_message = "Manager has no email address."

                log_result = _log_failed_notification(
                    request_id=request_id,
                    recipient_id=manager["user_id"],
                    event_type="request_escalated",
                    error_message=error_message,
                )

                results.append({
                    "recipient_id": manager["user_id"],
                    "success": False,
                    "message": error_message,
                    "log_success": log_result["success"],
                })
                continue

            values = {
                "recipient_name": manager.get("full_name") or "Manager",
                "request_title": request["title"],
                "request_id": request_id,
                "analyst_name": analyst_name,
                "reason": escalation["reason"],
            }

            result = _notify_requester(
                request_id=request_id,
                requester_id=manager["user_id"],
                requester_email=manager["email"],
                event_type="request_escalated",
                values=values,
            )

            results.append({
                "recipient_id": manager["user_id"],
                **result,
            })

        return {
            "success": all(item["success"] for item in results),
            "recipients_count": len(recipients),
            "results": results,
        }

    except Exception as error:
        return {
            "success": False,
            "message": "Could not process escalation notifications.",
            "email_error": str(error),
        }


def escalate_request(
    request_id: int,
    reason: str,
    reassigned_to: int | None = None,
) -> dict:
    """Escalate an assigned request and notify the appropriate managers."""

    supabase = get_supabase_client()

    if not isinstance(reason, str) or not reason.strip():
        return {
            "success": False,
            "error": "An escalation reason is required.",
        }

    try:
        supabase.rpc(
            "analyst_escalate_request",
            {
                "p_request_id": request_id,
                "p_reason": reason.strip(),
                "p_reassigned_to": reassigned_to,
            },
        ).execute()

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    notification = _send_escalation_notifications(request_id)

    return {
        "success": True,
        "message": "Request escalated successfully.",
        "notification": notification,
    }


def get_analyst_performance() -> dict:
    """Calculate performance metrics for the authenticated analyst."""

    supabase = get_supabase_client()

    try:
        # Verify the authenticated user's application role.
        role_result = supabase.rpc("current_app_role").execute()

        if role_result.data != "analyst":
            return {
                "success": False,
                "error": "Only analysts can access this performance report.",
            }

        # Retrieve the authenticated user's internal application ID.
        user_result = supabase.rpc("current_app_user_id").execute()
        analyst_id = user_result.data

        if not analyst_id:
            return {
                "success": False,
                "error": "Unable to identify the authenticated analyst.",
            }

        # Retrieve only requests assigned to this analyst.
        requests_result = (
            supabase.table("requests")
            .select(
                "request_id, status_id, expected_date, is_overdue, "
                "created_at, resolved_at"
            )
            .eq("assigned_to", analyst_id)
            .execute()
        )

        requests = requests_result.data or []

        # Retrieve status names.
        statuses_result = (
            supabase.table("statuses")
            .select("status_id, status_name")
            .execute()
        )

        status_map = {
            item["status_id"]: item["status_name"]
            for item in (statuses_result.data or [])
        }

        # Separate completed, cancelled, and open requests.
        completed = [
            request for request in requests
            if status_map.get(request.get("status_id")) == "Closed"
        ]

        cancelled = [
            request for request in requests
            if status_map.get(request.get("status_id")) == "Cancelled"
        ]

        open_requests = [
            request for request in requests
            if status_map.get(request.get("status_id"))
            not in ("Closed", "Cancelled")
        ]

        # Use the Eastern calendar date to determine overdue requests.
        eastern = ZoneInfo("America/New_York")
        today = datetime.now(eastern).date()

        overdue = [
            request for request in open_requests
            if (
                request.get("expected_date")
                and str(request["expected_date"])[:10] < today.isoformat()
            )
        ]

        # Calculate average turnaround time for completed requests.
        turnaround_hours = []

        for request in completed:
            created_at = request.get("created_at")
            resolved_at = request.get("resolved_at")

            if not created_at or not resolved_at:
                continue

            created = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )

            resolved = datetime.fromisoformat(
                resolved_at.replace("Z", "+00:00")
            )

            hours = (resolved - created).total_seconds() / 3600

            if hours >= 0:
                turnaround_hours.append(hours)

        average_turnaround = (
            round(
                sum(turnaround_hours) / len(turnaround_hours), 2
            )
            if turnaround_hours else None
        )

        # Calculate on-time completion using Eastern Time.
        eastern = ZoneInfo("America/New_York")

        on_time = 0
        late = 0
        without_deadline = 0

        for request in completed:
            expected_date = request.get("expected_date")
            resolved_at = request.get("resolved_at")

            if not expected_date or not resolved_at:
                without_deadline += 1
                continue

            resolved_datetime = datetime.fromisoformat(
                resolved_at.replace("Z", "+00:00")
            ).astimezone(eastern)

            resolved_date = resolved_datetime.date().isoformat()

            if resolved_date <= str(expected_date)[:10]:
                on_time += 1
            else:
                late += 1

        completed_with_deadlines = on_time + late

        on_time_rate = (
            round(
                (on_time / completed_with_deadlines) * 100, 2
            )
            if completed_with_deadlines else None
        )

        return {
            "success": True,
            "data": {
                "total_assigned": len(requests),
                "open_count": len(open_requests),
                "completed_count": len(completed),
                "cancelled_count": len(cancelled),
                "overdue_count": len(overdue),
                "average_turnaround_hours": average_turnaround,
                "on_time_count": on_time,
                "late_count": late,
                "without_deadline_count": without_deadline,
                "on_time_rate": on_time_rate,
            },
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }
