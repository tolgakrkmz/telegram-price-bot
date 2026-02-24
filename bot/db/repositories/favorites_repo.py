from typing import Dict, List, Optional

from db.supabase_client import supabase

FAVORITES_TABLE = "favorites"


def get_user_favorites(user_id: int) -> List[Dict]:
    """Fetch all favorites for a specific user."""
    try:
        response = (
            supabase.table(FAVORITES_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []
    except Exception as e:
        print(f"Supabase Select Error: {e}")
        return []


def add_favorite(user_id: int, product: Dict) -> Optional[Dict]:
    """Adds a product to favorites with unique check and fallback IDs."""
    pid = str(product.get("product_id") or product.get("id"))

    if not pid:
        return {"error": "Missing product ID"}

    try:
        existing = (
            supabase.table(FAVORITES_TABLE)
            .select("id")
            .eq("user_id", user_id)
            .eq("product_id", pid)
            .execute()
        )
        if existing.data:
            return {"error": "Already exists"}

        payload = {
            "user_id": user_id,
            "product_id": pid,
            "name": product.get("name"),
            "price": product.get("price"),
            "price_eur": product.get("price_eur"),
            "unit": product.get("unit"),
            "quantity": product.get("quantity"),
            "store": product.get("store"),
            "valid_until": product.get("valid_until"),
            "supermarket": product.get("supermarket"),
            "image": product.get("image") or product.get("image_url"),
            "discount": str(product.get("discount", "")),
            "brochure": product.get("brochure"),
        }

        response = supabase.table(FAVORITES_TABLE).insert(payload).execute()
        return response.data[0] if response.data else None

    except Exception as e:
        print(f"Supabase Insert Error: {e}")
        return {"error": str(e)}


def delete_favorite(user_id: int, product_id: str) -> bool:
    """Removes a favorite product for a specific user."""
    try:
        response = (
            supabase.table(FAVORITES_TABLE)
            .delete()
            .eq("user_id", user_id)
            .eq("product_id", str(product_id))
            .execute()
        )
        return len(response.data) > 0
    except Exception as e:
        print(f"Supabase Delete Error: {e}")
        return False


def get_all_favorites_from_db():
    """Fetches all favorites. Using your exact schema columns."""
    try:
        response = supabase.table("favorites").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Error fetching all favorites: {e}")
        return []
