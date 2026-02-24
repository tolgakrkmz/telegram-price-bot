from api.supermarket import get_product_price
from db.repositories.history_repo import get_product_history


def get_combined_price_history(product_id: str, product_name: str, store: str):
    """Combines API history with internal database history records."""
    db_records = get_product_history(product_id)
    api_results = get_product_price(product_name, multiple=True) or []

    api_match = next(
        (
            p
            for p in api_results
            if (
                p.get("store") == store
                or (p.get("supermarket") or {}).get("name") == store
            )
            and p.get("name") == product_name
        ),
        None,
    )

    combined = {}
    if api_match and "history" in api_match:
        for entry in api_match["history"]:
            combined[entry["date"]] = float(entry["price"])

    for entry in db_records:
        date_val = entry.get("recorded_date") or entry.get("recorded_at")
        if date_val:
            date_str = str(date_val).split("T")[0]
            combined[date_str] = float(entry["price"])

    return combined
