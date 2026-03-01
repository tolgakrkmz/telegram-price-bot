from datetime import datetime
from typing import Dict, List, Optional
from db.supabase_client import supabase

HISTORY_TABLE = "price_history"


def add_price_entry(
    product_id: str,
    name: str,
    store: str,
    price: float,
    unit_price: Optional[float] = None,
    base_unit: Optional[str] = None,
    date_str: Optional[str] = None,
):
    """
    Adds a price point with unit price support for accurate comparisons.
    Uses upsert to prevent daily duplicates for the same product/store.
    """
    try:
        record_date = date_str if date_str else datetime.now().strftime("%Y-%m-%d")

        payload = {
            "product_id": str(product_id).strip(),
            "name": name,
            "store": store,
            "price": float(price),
            "unit_price": float(unit_price) if unit_price else None,
            "base_unit": base_unit,  # e.g., 'kg', 'l', 'pc'
            "recorded_date": record_date,
        }

        # Upsert ensures we only have ONE price per product per store per day
        supabase.table(HISTORY_TABLE).upsert(payload).execute()

    except Exception as e:
        print(f"Supabase History Upsert Error: {e}")


def get_best_deals_by_category(product_name_part: str, limit: int = 5) -> List[Dict]:
    """
    Experimental: Finds the best unit prices for a similar product across different stores.
    This is how you build a 'Price Comparison' feature.
    """
    try:
        # We search for similar names and sort by unit_price
        response = (
            supabase.table(HISTORY_TABLE)
            .select("name, store, price, unit_price, base_unit")
            .ilike("name", f"%{product_name_part}%")
            .order("unit_price", asc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Comparison Error: {e}")
        return []


def get_product_history(product_id: str, limit: int = 15) -> List[Dict]:
    """Fetches history with newest records first."""
    try:
        clean_id = str(product_id).strip()
        response = (
            supabase.table(HISTORY_TABLE)
            .select("price, unit_price, recorded_date, name, store")
            .eq("product_id", clean_id)
            .order("recorded_date", asc=False)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Supabase History Error: {e}")
        return []


def get_latest_price(product_id: str, store: str) -> Optional[float]:
    """Gets the most recent price for a product in a specific store."""
    try:
        response = (
            supabase.table(HISTORY_TABLE)
            .select("price")
            .eq("product_id", str(product_id).strip())
            .eq("store", store)
            .order("recorded_date", ascending=False)
            .limit(1)
            .execute()
        )
        if response.data:
            return float(response.data[0]["price"])
        return None
    except Exception as e:
        print(f"Supabase Latest Price Error: {e}")
        return None
