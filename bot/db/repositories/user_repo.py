from datetime import datetime, timezone

from db.supabase_client import supabase


def create_user_if_not_exists(user):
    """Creates a user record if it doesn't exist, keeping settings intact."""
    try:
        existing = supabase.table("users").select("id").eq("id", user.id).execute()

        if existing.data:
            return existing.data

        user_data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "is_premium": False,
            "daily_request_count": 0,
            "last_request_date": datetime.now().date().isoformat(),
        }

        response = supabase.table("users").insert(user_data).execute()
        return response.data

    except Exception as e:
        print(f"Supabase User Error: {e}")
        return None


def get_user_subscription_status(user_id: int):
    """Returns premium status and manages daily counter reset."""
    try:
        response = (
            supabase.table("users").select("*").eq("id", user_id).single().execute()
        )

        if not response.data:
            return None

        data = response.data
        today = datetime.now().date().isoformat()

        # Check if reset is needed
        if data.get("last_request_date") != today:
            # 1. Update the database
            supabase.table("users").update(
                {"daily_request_count": 0, "last_request_date": today}
            ).eq("id", user_id).execute()

            # 2. Update the local object so the UI gets the fresh values
            data["daily_request_count"] = 0
            data["last_request_date"] = today

        return data
    except Exception as e:
        print(f"Error fetching user status: {e}")
        return None


def increment_request_count(user_id: int):
    """Increments the daily request counter for a user."""
    try:
        status = get_user_subscription_status(user_id)
        if status:
            new_count = status["daily_request_count"] + 1
            supabase.table("users").update({"daily_request_count": new_count}).eq(
                "id", user_id
            ).execute()
            return new_count
    except Exception as e:
        print(f"Error incrementing count: {e}")
    return None


def is_user_premium(user_id: int) -> bool:
    """Checks if the user has an active premium status."""
    try:
        status = get_user_subscription_status(user_id)
        if not status or not status.get("is_premium"):
            return False

        if status.get("premium_until"):
            expiry_str = status["premium_until"].replace("Z", "+00:00")
            expiry = datetime.fromisoformat(expiry_str)

            if expiry < datetime.now(timezone.utc):
                supabase.table("users").update({"is_premium": False}).eq(
                    "id", user_id
                ).execute()
                return False
        return True
    except Exception as e:
        print(f"Premium check error: {e}")
        return False


def get_notification_state(user_id: int) -> bool:
    """Fetches the notification preference."""
    try:
        response = (
            supabase.table("users")
            .select("notifications_enabled")
            .eq("id", user_id)
            .execute()
        )
        if response.data:
            return response.data[0]["notifications_enabled"]
        return True
    except Exception as e:
        print(f"Notification Fetch Error: {e}")
        return True


def toggle_notifications(user_id: int) -> bool:
    """Toggles the state and returns the new value."""
    try:
        current_state = get_notification_state(user_id)
        new_state = not current_state

        supabase.table("users").update({"notifications_enabled": new_state}).eq(
            "id", user_id
        ).execute()

        return new_state
    except Exception as e:
        print(f"Notification Toggle Error: {e}")
        return False


def get_users_to_notify():
    """Returns list of user IDs for notifications."""
    try:
        response = (
            supabase.table("users")
            .select("id")
            .eq("notifications_enabled", True)
            .execute()
        )
        return [user["id"] for user in response.data]
    except Exception as e:
        print(f"Error fetching users to notify: {e}")
        return []


def get_daily_request_count(user_id: int) -> int:
    """Returns the current daily search count for a user."""
    try:
        # Reusing the status function ensures we get the reset count if it's a new day
        status = get_user_subscription_status(user_id)
        if status:
            return status.get("daily_request_count", 0)
    except Exception as e:
        print(f"Error getting daily count: {e}")
    return 0
