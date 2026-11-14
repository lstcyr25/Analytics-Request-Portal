
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


def _log_failed_notification(
    recipient_id: int | None,
    request_id: int,
    event_type: str,
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


def _send_templated_notification(
    recipient_id: int,
    recipient_email: str,
    request_id: int,
    event_type: str,
    values: dict,
) -> dict:
    """
    Render, send, and log one email notification.

    Notification failures do not affect request submission.
    """

    subject = None
    log_attempted = False

    try:
        rendered = render_email_template(event_type, values)

        if not rendered["success"]:
            error_message = rendered.get(
                "error",
                "Email template rendering failed.",
            )

            log_attempted = True
            log_result = _log_failed_notification(
                recipient_id=recipient_id,
                request_id=request_id,
                event_type=event_type,
                error_message=error_message,
            )

            return {
                "success": False,
                "message": "Email template rendering failed.",
                "error": error_message,
                "log_success": log_result["success"],
            }

        subject = rendered["subject"]

        email_result = send_email(
            recipient_email=recipient_email,
            subject=subject,
            body=rendered["body"],
        )

        email_error = (
            None
            if email_result["success"]
            else email_result.get("error", "Email sending failed.")
        )

        log_attempted = True

        log_result = log_notification(
            recipient_id=recipient_id,
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
            "message": (
                "Email accepted by Resend."
                if email_result["success"]
                else "Email sending failed."
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
                    recipient_id=recipient_id,
                    request_id=request_id,
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
            "error": str(error),
            "log_success": log_result["success"],
        }


def submit_request(
    type_id: int,
    priority_id: int,
    title: str,
    description: str,
    needed_date: str | None = None,
    notification_recipient_override: str | None = None,
) -> dict:
    """
    Submit an analytics request through the secure RPC function.

    Sends separate notifications for request submission and
    automatic assignment when an analyst is assigned.
    """

    supabase = get_supabase_client()

    # Validate request fields before accessing string methods.
    if not isinstance(title, str) or not title.strip():
        return {
            "success": False,
            "error": "Request title cannot be empty.",
        }

    if not isinstance(description, str) or not description.strip():
        return {
            "success": False,
            "error": "Request description cannot be empty.",
        }

    if (
        needed_date is not None
        and (
            not isinstance(needed_date, str)
            or not needed_date.strip()
        )
    ):
        return {
            "success": False,
            "error": "Needed date must be a valid date or None.",
        }

    title = title.strip()
    description = description.strip()

    if needed_date is not None:
        needed_date = needed_date.strip()

    # Restrict test overrides to Resend's designated sandbox recipient.
    if (
        notification_recipient_override is not None
        and notification_recipient_override != "delivered@resend.dev"
    ):
        return {
            "success": False,
            "error": "Invalid notification test recipient.",
        }

    # Submit the request through the secure database function.
    try:
        response = supabase.rpc(
            "business_submit_request",
            {
                "p_type_id": type_id,
                "p_priority_id": priority_id,
                "p_title": title,
                "p_description": description,
                "p_needed_date": needed_date,
            },
        ).execute()

        request_id = response.data

        if not request_id:
            raise ValueError(
                "The database did not return a request ID."
            )

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    # The request is now submitted.
    # Notification failures must not undo the submission.

    submission_notification = {
        "success": False,
        "message": "Submission notification could not be processed.",
    }

    assignment_notification = {
        "success": False,
        "message": "Assignment notification has not been processed.",
    }

    user_id = None
    profile = None
    recipient_email = None

    # 1. Process the request-submitted notification.
    try:
        user_response = supabase.rpc(
            "current_app_user_id"
        ).execute()

        user_id = user_response.data

        if not user_id:
            raise ValueError("Could not identify the current user.")

        profile_response = (
            supabase.table("users")
            .select("user_id, full_name, email")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        profile = profile_response.data

        if not profile:
            raise ValueError("Could not retrieve the requester profile.")

        recipient_email = (
            notification_recipient_override or profile.get("email")
        )

        if not recipient_email:
            raise ValueError("The requester has no email address.")

        priority_response = (
            supabase.table("priorities")
            .select("priority_name")
            .eq("priority_id", priority_id)
            .maybe_single()
            .execute()
        )

        priority = priority_response.data

        if not priority:
            raise ValueError("Could not retrieve the request priority.")

        submission_notification = _send_templated_notification(
            recipient_id=user_id,
            recipient_email=recipient_email,
            request_id=request_id,
            event_type="request_submitted",
            values={
                "requester_name": profile.get("full_name") or "User",
                "request_title": title,
                "request_id": request_id,
                "priority": priority["priority_name"],
                "needed_date": needed_date or "Not specified",
            },
        )

        create_in_app_notification(
            recipient_id=user_id,
            request_id=request_id,
            event_type="request_submitted",
            title="Request submitted",
            message=f'Your request "{title}" was submitted successfully.',
        )

    except Exception as error:
        log_result = _log_failed_notification(
            recipient_id=user_id,
            request_id=request_id,
            event_type="request_submitted",
            error_message=str(error),
        )

        submission_notification = {
            "success": False,
            "message": "Submission notification processing failed.",
            "error": str(error),
            "log_success": log_result["success"],
        }

    # 2. Independently check whether automatic assignment occurred.
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
            raise ValueError("Could not retrieve the submitted request.")

        assigned_analyst_id = request.get("assigned_to")

        if not assigned_analyst_id:
            assignment_notification = {
                "success": False,
                "message": (
                    "No analyst was automatically assigned. "
                    "Assignment notification skipped."
                ),
            }

        elif not user_id or not profile or not recipient_email:
            raise ValueError(
                "Requester details are unavailable for assignment notification."
            )

        else:
            # The business user cannot read another user's profile
            # under RLS. Use the trusted backend client to retrieve
            # only the assigned analyst's display name.
            service_supabase = get_service_role_client()

            analyst_response = (
                service_supabase.table("users")
                .select("full_name")
                .eq("user_id", assigned_analyst_id)
                .maybe_single()
                .execute()
            )

            analyst = analyst_response.data

            if not analyst:
                raise ValueError(
                    "Could not retrieve the assigned analyst's name."
                )

            create_in_app_notification(
                recipient_id=assigned_analyst_id,
                request_id=request_id,
                event_type="request_assigned",
                title="New request assigned",
                message=f'You have been assigned request #{request_id}: "{title}".',
            )

            create_in_app_notification(
                recipient_id=user_id,
                request_id=request_id,
                event_type="request_assigned",
                title="Analyst assigned",
                message=f'Your request "{title}" has been assigned to an analyst.',
            )

            assignment_notification = _send_templated_notification(
                recipient_id=user_id,
                recipient_email=recipient_email,
                request_id=request_id,
                event_type="request_assigned",
                values={
                    "requester_name": profile.get("full_name") or "User",
                    "request_title": request["title"],
                    "analyst_name": (
                        analyst.get("full_name") or "Assigned Analyst"
                    ),
                    "request_id": request_id,
                    "expected_date": (
                        request["expected_date"] or "Not yet determined"
                    ),
                },
            )

    except Exception as error:
        log_result = _log_failed_notification(
            recipient_id=user_id,
            request_id=request_id,
            event_type="request_assigned",
            error_message=str(error),
        )

        assignment_notification = {
            "success": False,
            "message": "Assignment notification processing failed.",
            "error": str(error),
            "log_success": log_result["success"],
        }

    return {
        "success": True,
        "request_id": request_id,
        "message": "Request submitted successfully.",
        # Retain the original notification key for compatibility.
        "notification": submission_notification,
        "notifications": {
            "request_submitted": submission_notification,
            "request_assigned": assignment_notification,
        },
    }


def get_my_requests() -> dict:
    """
    Retrieve requests visible to the currently authenticated user.

    RLS determines which requests the user can access.
    """

    supabase = get_supabase_client()

    try:
        response = (
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

        return {
            "success": True,
            "data": response.data,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def get_request_by_id(request_id: int) -> dict:
    """
    Retrieve one request by its ID.

    RLS determines whether the user can access it.
    """

    supabase = get_supabase_client()

    try:
        response = (
            supabase.table("requests")
            .select("*")
            .eq("request_id", request_id)
            .maybe_single()
            .execute()
        )

        if not response.data:
            return {
                "success": False,
                "error": "Request not found or access denied.",
            }

        return {
            "success": True,
            "data": response.data,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }
