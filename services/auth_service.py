
from database.supabase_client import (
    get_service_role_client,
    get_supabase_client,
)


VALID_ROLES = {
    "business_user",
    "analyst",
    "analytics_manager",
}



def sign_in(identifier: str, password: str) -> dict:
    """
    Authenticate using either username or email.

    Username lookup uses the trusted backend client.
    Authentication remains isolated to the browser session.
    """

    if not isinstance(identifier, str) or not identifier.strip():
        return {
            "success": False,
            "error": "Enter your username or email address.",
        }

    if not isinstance(password, str) or not password:
        return {
            "success": False,
            "error": "Password is required.",
        }

    try:
        login_identifier = identifier.strip()

        if "@" in login_identifier:
            login_email = login_identifier.lower()
        else:
            service_supabase = get_service_role_client()

            profile_response = (
                service_supabase.table("users")
                .select("email")
                .ilike("username", login_identifier)
                .eq("is_active", True)
                .maybe_single()
                .execute()
            )

            profile = profile_response.data

            if not profile:
                return {
                    "success": False,
                    "error": "Invalid username or password.",
                }

            login_email = profile["email"]

        supabase = get_supabase_client()

        response = supabase.auth.sign_in_with_password(
            {
                "email": login_email,
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

    except Exception:
        return {
            "success": False,
            "error": "Invalid username/email or password.",
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
