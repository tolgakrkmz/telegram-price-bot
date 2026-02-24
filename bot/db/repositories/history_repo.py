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

        # Using upsert instead of insert to avoid "already exists" errors for the same day
        supabase.table(HISTORY_TABLE).upsert(payload).execute()

    except Exception as e:
        print(f"Supabase History Upsert Error: {e}")


def get_product_history(product_id: str, limit: int = 15) -> List[Dict]:
    """Fetches history, explicitly treating product_id as string."""
    try:
        # Ensure it is a string and stripped of any hidden spaces
        clean_id = str(product_id).strip()

        response = (
            supabase.table(HISTORY_TABLE)
            .select("price, recorded_date, name, store")
            .eq("product_id", clean_id)
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
        # Changed desc=True to descending=True
        response = (
            supabase.table(HISTORY_TABLE)
            .select("price")
            .eq("product_id", str(product_id))
            .eq("store", store)
            .order("recorded_date", descending=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return float(response.data[0]["price"])
        return None
    except Exception as e:
        print(f"Supabase Latest Price Error: {e}")
        return None


def add_price_history_record(product_id: str, price: float):
    """Inserts or updates a price record into the price_history table."""
    try:
        data = {
            "product_id": str(product_id),
            "price": float(price),
            "recorded_date": datetime.now().strftime("%Y-%m-%d"),
        }
        response = supabase.table(HISTORY_TABLE).upsert(data).execute()
        return response.data
    except Exception as e:
        print(f"Error adding price history: {e}")
        return None
