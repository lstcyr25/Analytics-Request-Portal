
from database.supabase_client import get_supabase_client


VALID_ROLES = {
    "business_user",
    "analyst",
    "analytics_manager",
}


def sign_in(email: str, password: str) -> dict:
    """
    Authenticate a user with Supabase Auth.

    The authenticated client is isolated to the current
    Streamlit browser session.
    """

    if not isinstance(email, str) or not email.strip():
        return {
            "success": False,
            "error": "A valid email address is required.",
        }

    if not isinstance(password, str) or not password:
        return {
            "success": False,
            "error": "Password is required.",
        }

    try:
        supabase = get_supabase_client()

        response = supabase.auth.sign_in_with_password(
            {
                "email": email.strip(),
                "password": password,
            }
        )

        if not response.user or not response.session:
            raise ValueError(
                "Authentication failed. No user session returned."
            )

        return {
            "success": True,
            "user_id": response.user.id,
            "email": response.user.email,
            "session": response.session,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def get_current_profile() -> dict:
    """Retrieve the active application profile."""

    try:
        supabase = get_supabase_client()

        auth_response = supabase.auth.get_user()

        if not auth_response.user:
            return {
                "success": False,
                "error": "No authenticated user found.",
            }

        profile_response = (
            supabase.table("users")
            .select(
                "user_id, full_name, email, role, is_active"
            )
            .eq("auth_user_id", auth_response.user.id)
            .maybe_single()
            .execute()
        )

        profile = profile_response.data

        if not profile:
            return {
                "success": False,
                "error": "Application profile not found.",
            }

        if not profile.get("is_active"):
            supabase.auth.sign_out()

            return {
                "success": False,
                "error": "This account is inactive.",
            }

        if profile.get("role") not in VALID_ROLES:
            supabase.auth.sign_out()

            return {
                "success": False,
                "error": "Invalid application role.",
            }

        required_fields = (
            "user_id",
            "full_name",
            "email",
            "role",
        )

        if any(not profile.get(field) for field in required_fields):
            return {
                "success": False,
                "error": "The application profile is incomplete.",
            }

        return {
            "success": True,
            "profile": profile,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def sign_out() -> dict:
    """Sign out the currently authenticated user."""

    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out()

        return {
            "success": True,
            "message": "Signed out successfully.",
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }
