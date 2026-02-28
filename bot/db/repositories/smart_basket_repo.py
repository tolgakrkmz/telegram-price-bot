from db.supabase_client import supabase


def update_smart_basket(
    user_id: int, items: list, alert_time: str, last_prices: dict = None
):
    """
    Saves or updates the user's smart basket, including initial prices for comparison.
    """
    data = {
        "user_id": user_id,
        "items": items,
        "alert_time": alert_time,
        "is_active": True,
    }
    if last_prices:
        data["last_prices"] = last_prices

    return supabase.table("smart_baskets").upsert(data, on_conflict="user_id").execute()


def get_baskets_by_time(time_str: str):
    """Fetches all active baskets scheduled for a specific time."""
    return (
        supabase.table("smart_baskets")
        .select("*")
        .eq("alert_time", time_str)
        .eq("is_active", True)
        .execute()
    )


def update_last_prices(user_id: int, last_prices: dict):
    """Updates the last known prices to be used as a baseline for the next check."""
    return (
        supabase.table("smart_baskets")
        .update({"last_prices": last_prices})
        .eq("user_id", user_id)
        .execute()
    )


def get_user_basket(user_id: int):
    """Fetches the current basket. Safe against missing rows."""
    try:
        return (
            supabase.table("smart_baskets")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        print(f"Error fetching basket: {e}")
        return None


def delete_user_basket(user_id: int):
    """Deletes the entire basket for a specific user."""
    try:
        return supabase.table("smart_baskets").delete().eq("user_id", user_id).execute()
    except Exception as e:
        print(f"Error deleting basket: {e}")
        return None
