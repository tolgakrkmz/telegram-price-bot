from datetime import datetime
from typing import Dict, List, Optional

from db.supabase_client import supabase

HISTORY_TABLE = "price_history"


def add_price_entry(
    product_id: str, name: str, store: str, price: float, date_str: Optional[str] = None
):
    """Adds a price point with name support and duplicate prevention."""
    try:
        record_date = date_str if date_str else datetime.now().strftime("%Y-%m-%d")

        payload = {
            "product_id": str(product_id),
            "name": name,
            "store": store,
            "price": float(price),
            "recorded_date": record_date,
        }

        if date_str:
            payload["recorded_at"] = date_str

        supabase.table(HISTORY_TABLE).insert(payload).execute()

    except Exception as e:
        if "already exists" not in str(e).lower():
            print(f"Supabase History Insert Error: {e}")


def get_product_history(product_id: str, limit: int = 15) -> List[Dict]:
    """Fetches the last N price points for a specific product."""
    try:
        response = (
            supabase.table(HISTORY_TABLE)
            .select("price, recorded_date, name, store")
            .eq("product_id", str(product_id))
            .order("recorded_date", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Supabase History Select Error: {e}")
        return []


def get_latest_price(product_id: str, store: str) -> Optional[float]:
    """Gets the most recent price recorded for a product in a specific store."""
    try:
        response = (
            supabase.table(HISTORY_TABLE)
            .select("price")
            .eq("product_id", str(product_id))
            .eq("store", store)
            .order("recorded_date", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return float(response.data[0]["price"])
        return None
    except Exception:
        return None
