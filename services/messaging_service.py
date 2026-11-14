
from database.supabase_client import get_supabase_client


def get_request_messages(request_id: int) -> dict:
    """
    Retrieve messages for a request.

    RLS controls which messages the authenticated user can see.
    Internal notes remain hidden from unauthorized users.
    """

    if (
        not isinstance(request_id, int)
        or isinstance(request_id, bool)
        or request_id <= 0
    ):
        return {
            "success": False,
            "error": "A valid request ID is required.",
        }

    supabase = get_supabase_client()

    try:
        response = (
            supabase.table("request_messages")
            .select(
                "message_id, request_id, sender_id, message_type, "
                "message_body, is_internal, new_expected_date, created_at"
            )
            .eq("request_id", request_id)
            .order("created_at")
            .execute()
        )

        return {
            "success": True,
            "messages": response.data or [],
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def send_message(request_id: int, message_body: str) -> dict:
    """
    Send a public comment on a request.

    The authenticated user's identity is determined by Supabase.
    RLS verifies request participation and insert authorization.
    """

    if (
        not isinstance(request_id, int)
        or isinstance(request_id, bool)
        or request_id <= 0
    ):
        return {
            "success": False,
            "error": "A valid request ID is required.",
        }

    if not isinstance(message_body, str) or not message_body.strip():
        return {
            "success": False,
            "error": "Message cannot be empty.",
        }

    supabase = get_supabase_client()

    try:
        # Retrieve the authenticated user's internal application ID.
        user_response = supabase.rpc(
            "current_app_user_id"
        ).execute()

        sender_id = user_response.data

        if not sender_id:
            return {
                "success": False,
                "error": "Unable to identify the authenticated user.",
            }

        # RLS verifies that the sender can participate in this request.
        response = (
            supabase.table("request_messages")
            .insert({
                "request_id": request_id,
                "sender_id": sender_id,
                "message_type": "comment",
                "message_body": message_body.strip(),
                "is_internal": False,
            })
            .execute()
        )

        if not response.data:
            return {
                "success": False,
                "error": "The message could not be confirmed as saved.",
            }

        return {
            "success": True,
            "message": "Comment sent successfully.",
            "data": response.data,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }
