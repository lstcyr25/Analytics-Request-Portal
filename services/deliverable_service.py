
from pathlib import Path
from uuid import uuid4

from database.supabase_client import get_supabase_client
from services.notification_service import create_in_app_notification

BUCKET_NAME = "request-deliverables"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def upload_request_deliverable(
    request_id: int,
    file,
    description: str | None = None,
) -> dict:
    """Upload a deliverable and save its metadata."""

    try:
        supabase = get_supabase_client()

        original_name = Path(file.name).name
        file_bytes = file.getvalue()

        if not file_bytes:
            return {"success": False, "error": "The file is empty."}

        if len(file_bytes) > MAX_FILE_SIZE:
            return {"success": False, "error": "File exceeds the 20 MB limit."}

        extension = Path(original_name).suffix.lower()
        storage_name = f"{uuid4().hex}{extension}"
        storage_path = f"{request_id}/{storage_name}"

        upload_result = supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": file.type or "application/octet-stream",
                "upsert": "false",
            },
        )

        user_result = supabase.rpc(
            "current_app_user_id"
        ).execute()

        if not user_result.data:
            raise ValueError("Could not identify the current application user.")

        uploaded_by = user_result.data

        metadata_result = (
            supabase.table("request_deliverables")
            .insert({
                "request_id": request_id,
                "uploaded_by": uploaded_by,
                "file_name": original_name,
                "storage_path": storage_path,
                "description": description.strip() if description else None,
            })
            .execute()
        )

        if not metadata_result.data:
            raise ValueError("File uploaded, but metadata was not saved.")

        create_in_app_notification(
            recipient_id=uploaded_by,
            request_id=request_id,
            event_type="analyst_deliverable_uploaded",
            title="Deliverable uploaded",
            message=(
                f'"{original_name}" was successfully uploaded '
                f'for request #{request_id}.'
            ),
        )

        return {
            "success": True,
            "message": f"{original_name} uploaded successfully.",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


def get_request_deliverables(request_id: int) -> dict:
    """Retrieve deliverables visible to the authenticated user."""

    try:
        supabase = get_supabase_client()

        result = (
            supabase.table("request_deliverables")
            .select("*")
            .eq("request_id", request_id)
            .order("uploaded_at", desc=True)
            .execute()
        )

        return {
            "success": True,
            "deliverables": result.data or [],
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


def download_request_deliverable(storage_path: str) -> dict:
    """Download a deliverable through the authenticated client."""

    try:
        supabase = get_supabase_client()

        result = (
            supabase.storage
            .from_(BUCKET_NAME)
            .download(storage_path)
        )

        return {"success": True, "file_bytes": result}

    except Exception as exc:
        return {"success": False, "error": str(exc)}

def confirm_request_completion(request_id: int) -> dict:
    """Allow the requester to confirm delivered work."""

    try:
        supabase = get_supabase_client()

        supabase.rpc(
            "requester_confirm_completion",
            {"p_request_id": request_id},
        ).execute()

        return {
            "success": True,
            "message": "Request marked as completed.",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }

def request_changes(request_id: int, reason: str) -> dict:
    try:
        supabase = get_supabase_client()

        supabase.rpc(
            "requester_request_changes",
            {
                "p_request_id": request_id,
                "p_reason": reason,
            },
        ).execute()

        return {
            "success": True,
            "message": "Changes requested. The analyst has been notified.",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }