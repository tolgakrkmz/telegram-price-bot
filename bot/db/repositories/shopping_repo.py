from typing import Dict, List, Optional

from db.supabase_client import supabase

SHOPPING_TABLE = "shopping_list"


def create_user_if_not_exists_by_id(user_id: int):
    """Ensures the user exists in the users table to avoid foreign key errors."""
    try:
        supabase.table("users").upsert({"id": user_id}).execute()
    except Exception as e:
        print(f"Supabase User Upsert Error: {e}")


def add_to_shopping_list(user_id: int, product: Dict) -> Optional[Dict]:
    """Adds an item to the shopping list with fallback for IDs and images."""
    # Ensure the user exists first to satisfy the Foreign Key constraint
    create_user_if_not_exists_by_id(user_id)

    pid = str(product.get("product_id") or product.get("id") or "")

    payload = {
        "user_id": user_id,
        "product_id": pid,
        "name": product.get("name"),
        "price": product.get("price"),
        "price_eur": product.get("price_eur"),
        "unit": product.get("unit"),
        "quantity": product.get("quantity"),
        "store": product.get("store"),
        "image": product.get("image") or product.get("image_url"),
        "discount": str(product.get("discount", "")),
        "valid_until": product.get("valid_until") or product.get("valid-until"),
    }

    try:
        response = supabase.table(SHOPPING_TABLE).insert(payload).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Supabase Shopping Insert Error: {e}")
        return None


def get_user_shopping_list(user_id: int) -> List[Dict]:
    """Fetches the shopping list for a specific user."""
    try:
        response = (
            supabase.table(SHOPPING_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Supabase Shopping Select Error: {e}")
        return []


def delete_shopping_item(item_id: str) -> bool:
    """Deletes a specific item from the shopping list using its UUID."""
    try:
        response = supabase.table(SHOPPING_TABLE).delete().eq("id", item_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Supabase Shopping Delete Error: {e}")
        return False
