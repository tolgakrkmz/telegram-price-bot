import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from utils.helpers import get_product_id

# ==============================
# Paths
# ==============================

BASE_DIR = Path(__file__).parent
FAVORITES_FILE = BASE_DIR / "favorites.json"
HISTORY_FILE = BASE_DIR / "price_history.json"
CACHE_FILE = BASE_DIR / "search_cache.json"

# ==============================
# Internal JSON helpers
# ==============================

def _load_json(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}

    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def _save_json(file_path: Path, data: dict[str, Any]) -> None:
    temp_file = file_path.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(file_path)
    except OSError:
        if temp_file.exists():
            temp_file.unlink()
        raise

# ==============================
# USER SETTINGS & ALERTS
# ==============================

def toggle_notifications(user_id: Any) -> bool:
    """Toggle notification status for a specific user."""
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    
    if uid not in data:
        data[uid] = {}
        
    # Default to True if not set, otherwise flip the value
    current_status = data[uid].get("notifications_enabled", False)
    new_status = not current_status
    data[uid]["notifications_enabled"] = new_status
    
    _save_json(FAVORITES_FILE, data)
    return new_status

def get_notification_status(user_id: Any) -> bool:
    """Check if the user has enabled notifications."""
    data = _load_json(FAVORITES_FILE)
    return data.get(str(user_id), {}).get("notifications_enabled", False)

def get_users_to_notify() -> list[str]:
    """Get list of user IDs who have notifications enabled."""
    data = _load_json(FAVORITES_FILE)
    return [uid for uid, settings in data.items() if settings.get("notifications_enabled")]

def get_expiring_products(user_id: str) -> list[dict[str, Any]]:
    """Find products in favorites or shopping list expiring today."""
    data = _load_json(FAVORITES_FILE)
    user_data = data.get(user_id, {})
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    expiring = []
    
    # Check shopping list
    for item in user_data.get("shopping_list", []):
        if item.get("valid-until") == today_str:
            expiring.append(item)
            
    # Check favorites (all keys except shopping_list and settings)
    for key, value in user_data.items():
        if key not in ["shopping_list", "notifications_enabled"] and isinstance(value, dict):
            if value.get("valid-until") == today_str:
                expiring.append(value)
                
    return expiring

def get_expiring_products_tomorrow(user_id: str) -> list[dict[str, Any]]:
    """Find products expiring exactly tomorrow."""
    data = _load_json(FAVORITES_FILE)
    user_data = data.get(user_id, {})
    
    # Calculate tomorrow's date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    expiring = []
    
    # Check both shopping list and favorites
    all_items = user_data.get("shopping_list", []) + [
        v for k, v in user_data.items() 
        if k not in ["shopping_list", "notifications_enabled"] and isinstance(v, dict)
    ]
    
    for item in all_items:
        if item.get("valid-until") == tomorrow:
            expiring.append(item)
                
    return expiring

# ==============================
# PRICE HISTORY
# ==============================

def update_price_history(product_id: str, price: float, name: str, store: str) -> None:
    history = _load_json(HISTORY_FILE)
    date_str = datetime.now().strftime("%Y-%m-%d")

    if product_id not in history:
        history[product_id] = {"name": name, "store": store, "prices": []}

    prices = history[product_id]["prices"]

    if not prices or prices[-1]["date"] != date_str:
        prices.append({"date": date_str, "price": float(price)})
        _save_json(HISTORY_FILE, history)

def get_product_history(product_id: str) -> list[dict[str, Any]]:
    return _load_json(HISTORY_FILE).get(product_id, {}).get("prices", [])

# ==============================
# SEARCH CACHE (12h TTL)
# ==============================

def get_cached_search(query: str) -> list[dict[str, Any]] | None:
    cache = _load_json(CACHE_FILE)
    key = query.lower().strip()

    if key in cache:
        entry = cache[key]
        cached_time = datetime.fromisoformat(entry["timestamp"])

        if datetime.now() - cached_time < timedelta(hours=12):
            return entry["results"]

    return None

def save_search_to_cache(query: str, results: list[dict[str, Any]]) -> None:
    cache = _load_json(CACHE_FILE)
    cache[query.lower().strip()] = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
    _save_json(CACHE_FILE, cache)

# ==============================
# FAVORITES
# ==============================

def get_favorites(user_id: Any) -> dict[str, dict[str, Any]]:
    data = _load_json(FAVORITES_FILE)
    user_data = data.get(str(user_id), {})

    return {
        k: v
        for k, v in user_data.items()
        if k not in ["shopping_list", "notifications_enabled"] and isinstance(v, dict)
    }

def add_favorite(user_id: Any, product: dict[str, Any]) -> bool:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)

    if uid not in data:
        data[uid] = {}

    pid = product.get("id")
    if not pid:
        pid = get_product_id(product)
        product["id"] = pid

    pid = str(pid)

    if pid in data[uid]:
        return False

    data[uid][pid] = product
    _save_json(FAVORITES_FILE, data)

    update_price_history(pid, product["price"], product["name"], product["store"])
    return True

def remove_favorite(user_id: Any, product_id: str) -> bool:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    product_id = str(product_id)

    if uid in data and product_id in data[uid]:
        del data[uid][product_id]
        _save_json(FAVORITES_FILE, data)
        return True

    return False

# ==============================
# SHOPPING LIST
# ==============================

def _ensure_shopping_schema(data: dict[str, Any], user_id: str) -> dict[str, Any]:
    if user_id not in data:
        data[user_id] = {}

    if "shopping_list" not in data[user_id]:
        data[user_id]["shopping_list"] = []

    return data

def get_shopping_list(user_id: Any) -> list[dict[str, Any]]:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)

    data = _ensure_shopping_schema(data, uid)

    return data[uid]["shopping_list"]

def add_to_shopping(user_id: Any, product: dict[str, Any]) -> bool:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)

    data = _ensure_shopping_schema(data, uid)

    pid = product.get("id")
    if not pid:
        pid = get_product_id(product)
        product["id"] = pid

    pid = str(pid)
    product["id"] = pid

    if any(str(item.get("id")) == pid for item in data[uid]["shopping_list"]):
        return False

    data[uid]["shopping_list"].append(product)
    _save_json(FAVORITES_FILE, data)
    return True

def remove_from_shopping(user_id: Any, product_id: str) -> bool:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    product_id = str(product_id)

    if uid in data and "shopping_list" in data[uid]:
        original = data[uid]["shopping_list"]
        updated = [item for item in original if str(item.get("id")) != product_id]

        if len(updated) < len(original):
            data[uid]["shopping_list"] = updated
            _save_json(FAVORITES_FILE, data)
            return True

    return False

def clear_shopping_list(user_id: Any) -> None:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)

    if uid in data:
        data[uid]["shopping_list"] = []
        _save_json(FAVORITES_FILE, data)

def get_all_favorites() -> dict[str, Any]:
    return _load_json(FAVORITES_FILE)