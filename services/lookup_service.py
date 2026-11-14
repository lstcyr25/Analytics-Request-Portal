
from database.supabase_client import get_supabase_client


def get_request_types() -> dict:
    """Retrieve available analytics request types."""

    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("request_types")
            .select("type_id, type_name, description, expected_days")
            .order("type_id")
            .execute()
        )

        return {
            "success": True,
            "data": response.data or [],
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def get_priorities() -> dict:
    """Retrieve available request priorities."""

    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("priorities")
            .select("priority_id, priority_name, load_weight, overdue_days")
            .order("priority_id")
            .execute()
        )

        return {
            "success": True,
            "data": response.data or [],
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def get_statuses() -> dict:
    """Retrieve available request statuses."""

    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("statuses")
            .select("status_id, status_name")
            .order("status_id")
            .execute()
        )

        return {
            "success": True,
            "data": response.data or [],
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }
