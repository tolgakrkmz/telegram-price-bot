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
        }

        response = supabase.table("users").insert(user_data).execute()
        return response.data

    except Exception as e:
        print(f"Supabase User Error: {e}")
        return None


def get_notification_state(user_id: int) -> bool:
    """Fetches the notification preference. Defaults to True if user not found."""
    try:
        response = (
            supabase.table("users")
            .select("notifications_enabled")
            .eq("id", user_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
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

        # Update the database
        response = (
            supabase.table("users")
            .update({"notifications_enabled": new_state})
            .eq("id", user_id)
            .execute()
        )

        if response.data:
            print(f"Successfully toggled user {user_id} to {new_state}")
            return new_state
        else:
            print(
                f"Failed to update user {user_id} - check if ID exists and RLS policies."
            )
            return current_state

    except Exception as e:
        print(f"Notification Toggle Error: {e}")
        return False


def get_users_to_notify():
    """Returns a list of user IDs who have notifications enabled."""
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
