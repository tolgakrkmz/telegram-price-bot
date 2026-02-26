from datetime import datetime

from db.supabase_client import supabase

CACHE_TABLE = "search_cache"


def get_cached_results(query: str, expiry_hours: int = None):
    """
    Gets cached results from Supabase.
    If expiry_hours is None, it returns the data regardless of when it was created.
    """
    try:
        query = query.lower().strip()
        response = supabase.table(CACHE_TABLE).select("*").eq("query", query).execute()

        if response.data:
            cache_data = response.data[0]

            # If no expiry is set, return the data immediately (Permanent Cache)
            if expiry_hours is None:
                return cache_data["results"]

            # If expiry is set, check if the data is still within the time limit
            from datetime import timedelta

            created_at = datetime.fromisoformat(
                cache_data["created_at"].replace("Z", "+00:00")
            )

            if datetime.now(created_at.tzinfo) < created_at + timedelta(
                hours=expiry_hours
            ):
                return cache_data["results"]

            # Note: We removed the .delete() call here.
            # Even if 'expired', we don't delete it; we just return None so fresh data can be fetched.

        return None
    except Exception as e:
        print(f"Cache Read Error: {e}")
        return None


def set_cache_results(query: str, results: list):
    """
    Saves or updates search results in the cloud cache.
    Using upsert ensures we only have one row per unique query.
    """
    try:
        query = query.lower().strip()
        payload = {
            "query": query,
            "results": results,
            "created_at": datetime.now().isoformat(),
        }
        # Upsert automatically updates the existing row if the 'query' key matches
        supabase.table(CACHE_TABLE).upsert(payload).execute()
    except Exception as e:
        print(f"Cache Write Error: {e}")


def get_all_cached_products():
    """Returns all cached product lists from the cloud cache for price comparison."""
    try:
        response = supabase.table(CACHE_TABLE).select("results").execute()
        return [item["results"] for item in response.data if item.get("results")]
    except Exception as e:
        print(f"Error fetching all cached products: {e}")
        return []
