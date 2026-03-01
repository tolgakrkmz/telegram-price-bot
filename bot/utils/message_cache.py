from db.supabase_client import supabase


def add_message(user_id: int, message_id: int):
    try:
        supabase.table("message_cache").insert(
            {"user_id": user_id, "message_id": message_id}
        ).execute()
    except Exception as e:
        print(f"Error adding message to cache: {e}")


def get_messages(user_id: int):
    try:
        response = (
            supabase.table("message_cache")
            .select("message_id")
            .eq("user_id", user_id)
            .execute()
        )
        return [row["message_id"] for row in response.data]
    except Exception as e:
        print(f"Error fetching messages from cache: {e}")
        return []


def clear_messages(user_id: int):
    try:
        supabase.table("message_cache").delete().eq("user_id", user_id).execute()
    except Exception as e:
        print(f"Error clearing message cache: {e}")
