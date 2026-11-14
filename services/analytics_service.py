from database.supabase_client import (
    get_supabase_client,
    get_service_role_client,
)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def _require_analytics_manager(supabase) -> tuple[bool, str | None]:
    """Verify that the current user is an active analytics manager."""

    try:
        auth_result = supabase.auth.get_user()
        auth_user = auth_result.user

        if not auth_user:
            return False, "Authentication required."

        profile_result = (
            supabase.table("users")
            .select("role, is_active")
            .eq("auth_user_id", auth_user.id)
            .single()
            .execute()
        )

        profile = profile_result.data

        if (
            not profile
            or profile["role"] != "analytics_manager"
            or not profile["is_active"]
        ):
            return (
                False,
                "Only active analytics managers can access this information.",
            )

        return True, None

    except Exception:
        return False, "Unable to verify analytics access."


def get_analyst_workload() -> dict:
    """Retrieve analyst workload from the Gold reporting view."""

    try:
        supabase = get_supabase_client()

        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {"success": False, "message": error_message}

        response = (
            supabase.table("v_analyst_workload")
            .select("*")
            .execute()
        )

        return {
            "success": True,
            "data": response.data or [],
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


def get_turnaround_by_type() -> dict:
    """Retrieve request turnaround metrics by request type."""

    try:
        supabase = get_supabase_client()

        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {"success": False, "message": error_message}

        response = (
            supabase.table("v_turnaround_by_type")
            .select("*")
            .execute()
        )

        return {
            "success": True,
            "data": response.data or [],
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


def get_overdue_requests() -> dict:
    """Retrieve overdue requests from the Gold reporting view."""

    try:
        supabase = get_supabase_client()

        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {"success": False, "message": error_message}

        response = (
            supabase.table("v_overdue_requests")
            .select("*")
            .execute()
        )

        return {
            "success": True,
            "data": response.data or [],
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


def get_request_volume_by_department_and_type() -> dict:
    """Calculate request volume by department and request type."""

    try:
        supabase = get_supabase_client()

        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {"success": False, "message": error_message}

        requests_response = (
            supabase.table("requests")
            .select("request_id, requester_id, type_id")
            .execute()
        )

        users_response = (
            supabase.table("users")
            .select("user_id, department_id")
            .execute()
        )

        departments_response = (
            supabase.table("departments")
            .select("department_id, department_name")
            .execute()
        )

        types_response = (
            supabase.table("request_types")
            .select("type_id, type_name")
            .execute()
        )

        users = {
            user["user_id"]: user
            for user in (users_response.data or [])
        }

        departments = {
            department["department_id"]: department["department_name"]
            for department in (departments_response.data or [])
        }

        request_types = {
            item["type_id"]: item["type_name"]
            for item in (types_response.data or [])
        }

        volume = {}

        for request in requests_response.data or []:
            requester = users.get(request["requester_id"], {})

            department_id = requester.get("department_id")
            type_id = request.get("type_id")

            department_name = departments.get(
                department_id,
                "Unassigned Department",
            )

            type_name = request_types.get(
                type_id,
                "Unknown Request Type",
            )

            key = (department_name, type_name)

            volume[key] = volume.get(key, 0) + 1

        results = [
            {
                "department_name": department,
                "type_name": request_type,
                "request_count": count,
            }
            for (department, request_type), count in volume.items()
        ]

        results.sort(
            key=lambda item: (
                item["department_name"],
                item["type_name"],
            )
        )

        return {
            "success": True,
            "data": results,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


def get_analyst_performance_snapshots(
    analyst_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Retrieve historical analyst performance snapshots."""

    try:
        supabase = get_supabase_client()

        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {"success": False, "message": error_message}

        query = (
            supabase.table("analyst_performance_snapshots")
            .select("*")
            .order("snapshot_date", desc=True)
        )

        if analyst_id is not None:
            query = query.eq("analyst_id", analyst_id)

        if start_date:
            query = query.gte("snapshot_date", start_date)

        if end_date:
            query = query.lte("snapshot_date", end_date)

        response = query.execute()

        return {
            "success": True,
            "data": response.data or [],
        }

    except Exception as error:
        return {"success": False, "error": str(error)}



def get_completion_performance() -> dict:
    """Calculate on-time performance using Eastern Time."""

    try:
        supabase = get_supabase_client()

        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {"success": False, "message": error_message}

        eastern = ZoneInfo("America/New_York")

        # Only the Closed status counts as completed.
        closed_status = (
            supabase.table("statuses")
            .select("status_id")
            .eq("status_name", "Closed")
            .execute()
        )

        closed_status_ids = [
            row["status_id"] for row in (closed_status.data or [])
        ]

        if not closed_status_ids:
            return {
                "success": True,
                "data": {
                    "total_completed": 0,
                    "on_time": 0,
                    "overdue": 0,
                    "without_expected_date": 0,
                    "on_time_rate": None,
                },
            }

        result = (
            supabase.table("requests")
            .select("request_id, expected_date, resolved_at")
            .in_("status_id", closed_status_ids)
            .not_.is_("resolved_at", "null")
            .execute()
        )

        completed_requests = result.data or []

        on_time = 0
        overdue = 0
        without_expected_date = 0

        for request in completed_requests:
            expected_date = request.get("expected_date")
            resolved_at = request.get("resolved_at")

            if not expected_date:
                without_expected_date += 1
                continue

            # Convert the completion timestamp to Eastern Time.
            resolved_datetime = datetime.fromisoformat(
                resolved_at.replace("Z", "+00:00")
            ).astimezone(eastern)

            resolved_date = resolved_datetime.date().isoformat()

            if resolved_date <= expected_date:
                on_time += 1
            else:
                overdue += 1

        total_with_deadlines = on_time + overdue

        on_time_rate = (
            round((on_time / total_with_deadlines) * 100, 2)
            if total_with_deadlines > 0
            else None
        )

        return {
            "success": True,
            "data": {
                "total_completed": len(completed_requests),
                "on_time": on_time,
                "overdue": overdue,
                "without_expected_date": without_expected_date,
                "on_time_rate": on_time_rate,
            },
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
        }


def generate_analyst_performance_snapshots() -> dict:
    """Generate or refresh daily performance snapshots for active analysts."""

    try:
        supabase = get_supabase_client()

        authorized, error_message = _require_analytics_manager(supabase)

        if not authorized:
            return {"success": False, "message": error_message}

        # Use Eastern Time for daily reporting.
        eastern = ZoneInfo("America/New_York")
        today = datetime.now(eastern).date()

        today_start = datetime.combine(
            today,
            datetime.min.time(),
            tzinfo=eastern,
        )

        tomorrow_start = datetime.combine(
            today + timedelta(days=1),
            datetime.min.time(),
            tzinfo=eastern,
        )

        # Retrieve active analysts.
        analysts_result = (
            supabase.table("users")
            .select("user_id")
            .eq("role", "analyst")
            .eq("is_active", True)
            .execute()
        )

        analysts = analysts_result.data or []

        if not analysts:
            return {
                "success": True,
                "message": "No active analysts found.",
                "snapshots_created": 0,
            }

        # Retrieve requests needed for the calculations.
        requests_result = (
            supabase.table("requests")
            .select(
                "assigned_to,status_id,expected_date,created_at,resolved_at"
            )
            .not_.is_("assigned_to", "null")
            .execute()
        )

        requests = requests_result.data or []

        # Identify the Closed status.
        closed_status_result = (
            supabase.table("statuses")
            .select("status_id")
            .eq("status_name", "Closed")
            .execute()
        )

        closed_status_ids = {
            row["status_id"]
            for row in (closed_status_result.data or [])
        }

        snapshots = []

        # Calculate metrics separately for each analyst.
        for analyst in analysts:
            analyst_id = analyst["user_id"]

            analyst_requests = [
                request
                for request in requests
                if request["assigned_to"] == analyst_id
            ]

            open_requests = [
                request
                for request in analyst_requests
                if request["status_id"] not in closed_status_ids
                and request["status_id"] != 7
            ]

            overdue_requests = [
                request
                for request in open_requests
                if (
                    request.get("expected_date")
                    and str(request["expected_date"])[:10] < today.isoformat()
                )
            ]

            # Identify requests closed during the Eastern calendar day.
            closed_today = []

            for request in analyst_requests:
                resolved_at = request.get("resolved_at")

                if (
                    request["status_id"] in closed_status_ids
                    and resolved_at
                ):
                    resolved_datetime = datetime.fromisoformat(
                        resolved_at.replace("Z", "+00:00")
                    ).astimezone(eastern)

                    if today_start <= resolved_datetime < tomorrow_start:
                        closed_today.append(request)

            # Calculate average turnaround time.
            turnaround_hours = []

            for request in closed_today:
                created_at = request.get("created_at")
                resolved_at = request.get("resolved_at")

                if created_at and resolved_at:
                    created = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )

                    resolved = datetime.fromisoformat(
                        resolved_at.replace("Z", "+00:00")
                    )

                    hours = (
                        resolved - created
                    ).total_seconds() / 3600

                    if hours >= 0:
                        turnaround_hours.append(hours)

            avg_turnaround = (
                round(
                    sum(turnaround_hours) / len(turnaround_hours),
                    2,
                )
                if turnaround_hours
                else None
            )

            # Add one snapshot for this analyst.
            snapshots.append({
                "analyst_id": analyst_id,
                "snapshot_date": today.isoformat(),
                "open_count": len(open_requests),
                "closed_count": len(closed_today),
                "overdue_count": len(overdue_requests),
                "avg_turnaround_hours": avg_turnaround,
            })

        # Upsert prevents duplicate snapshots for the same analyst/date.
        service_supabase = get_service_role_client()

        result = (
            service_supabase.table("analyst_performance_snapshots")
            .upsert(
                snapshots,
                on_conflict="analyst_id,snapshot_date",
            )
            .execute()
        )

        return {
            "success": True,
            "message": "Daily analyst performance snapshots generated successfully.",
            "snapshots_created": len(result.data or []),
            "data": result.data or [],
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
        }