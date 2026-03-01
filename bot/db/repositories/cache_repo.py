from datetime import datetime, timedelta

from db.supabase_client import supabase

CACHE_TABLE = "search_cache"


def get_cached_results(query: str, expiry_hours: int = 24):
    """
    Gets cached results only if they are not older than expiry_hours.
    Does NOT delete expired data to allow fallback during API limits.
    """
    try:
        query = query.lower().strip()
        response = supabase.table(CACHE_TABLE).select("*").eq("query", query).execute()

        if response.data:
            cache_data = response.data[0]
            created_at = datetime.fromisoformat(
                cache_data["created_at"].replace("Z", "+00:00")
            )

            # Check if cache is still fresh
            if datetime.now(created_at.tzinfo) < created_at + timedelta(
                hours=expiry_hours
            ):
                return cache_data["results"]

            # If expired, we return None to force a fresh API search,
            # but we keep the data in DB for emergency fallback.

        return None
    except Exception as e:
        print(f"Cache Read Error: {e}")
        return None


def set_cache_results(query: str, results: list):
    """Saves or updates search results in the cloud cache."""
    try:
        query = query.lower().strip()
        payload = {
            "query": query,
            "results": results,
            "created_at": datetime.now().isoformat(),
        }
        # upsert updates the record if the query already exists
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
