from db.supabase_client import supabase


def create_user_if_not_exists(user):
    """Creates a user record in Supabase if it doesn't exist."""
    try:
        user_data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
        }

        response = supabase.table("users").upsert(user_data).execute()
        return response.data
    except Exception as e:
        print(f"Supabase User Error: {e}")
        return None
