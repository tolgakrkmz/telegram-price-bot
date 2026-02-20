import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Paths
BASE_DIR = Path(__file__).parent
FAVORITES_FILE = BASE_DIR / "favorites.json"
HISTORY_FILE = BASE_DIR / "price_history.json"
CACHE_FILE = BASE_DIR / "search_cache.json"

def _load_json(file_path: Path) -> Dict[str, Any]:
    """Internal helper to load JSON data safely."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def _save_json(file_path: Path, data: Dict[str, Any]) -> None:
    """Internal helper to save JSON data atomically."""
    temp_file = file_path.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(file_path)
    except IOError as e:
        if temp_file.exists():
            temp_file.unlink()
        raise e

# --- PRICE HISTORY ---
def update_price_history(product_id: str, price: float, name: str, store: str) -> None:
    """Records product price changes over time."""
    history = _load_json(HISTORY_FILE)
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if product_id not in history:
        history[product_id] = {"name": name, "store": store, "prices": []}
    
    prices = history[product_id]["prices"]
    if not prices or prices[-1]["date"] != date_str:
        prices.append({"date": date_str, "price": float(price)})
        _save_json(HISTORY_FILE, history)

def get_product_history(product_id: str) -> List[Dict[str, Any]]:
    """Returns price history for a specific product."""
    return _load_json(HISTORY_FILE).get(product_id, {}).get("prices", [])

# --- SEARCH CACHE ---
def get_cached_search(query: str) -> Optional[List[Dict[str, Any]]]:
    """Retrieves search results from cache if valid (12h)."""
    cache = _load_json(CACHE_FILE)
    query_key = query.lower().strip()
    
    if query_key in cache:
        entry = cache[query_key]
        cached_time = datetime.fromisoformat(entry["timestamp"])
        if datetime.now() - cached_time < timedelta(hours=12):
            return entry["results"]
    return None

def save_search_to_cache(query: str, results: List[Dict[str, Any]]) -> None:
    """Saves API search results to local cache."""
    cache = _load_json(CACHE_FILE)
    cache[query.lower().strip()] = {
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    _save_json(CACHE_FILE, cache)

# --- FAVORITES ---
def get_favorites(user_id: Any) -> Dict[str, Dict[str, Any]]:
    """Returns filtered user favorites (excludes metadata)."""
    data = _load_json(FAVORITES_FILE)
    user_data = data.get(str(user_id), {})
    return {
        k: v for k, v in user_data.items() 
        if k != "shopping_list" and isinstance(v, dict)
    }

def add_favorite(user_id: Any, product: Dict[str, Any]) -> bool:
    """Adds a product to user favorites and records initial price."""
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    
    if uid not in data:
        data[uid] = {}
        
    pid = product.get("id")
    if not pid:
        from utils.helpers import get_product_id
        pid = get_product_id(product)
        product["id"] = pid

    if pid in data[uid]:
        return False
        
    data[uid][pid] = product
    _save_json(FAVORITES_FILE, data)
    update_price_history(pid, product['price'], product['name'], product['store'])
    return True

def remove_favorite(user_id: Any, product_id: str) -> bool:
    """Removes product from favorites."""
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    if uid in data and product_id in data[uid]:
        del data[uid][product_id]
        _save_json(FAVORITES_FILE, data)
        return True
    return False

# --- SHOPPING LIST ---
def _ensure_shopping_schema(data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Ensures shopping list structure exists for the user."""
    if user_id not in data:
        data[user_id] = {}
    if "shopping_list" not in data[user_id]:
        data[user_id]["shopping_list"] = []
    return data

def get_shopping_list(user_id: Any) -> List[Dict[str, Any]]:
    """Returns user's shopping list."""
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    return _ensure_shopping_schema(data, uid)[uid]["shopping_list"]

def add_to_shopping(user_id: Any, product: Dict[str, Any]) -> bool:
    """Adds item to shopping list if not already present."""
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    data = _ensure_shopping_schema(data, uid)
    
    pid = product.get("id") or __import__("utils.helpers").helpers.get_product_id(product)
    
    if any(item.get("id") == pid for item in data[uid]["shopping_list"]):
        return False
        
    data[uid]["shopping_list"].append(product)
    _save_json(FAVORITES_FILE, data)
    return True

def remove_from_shopping(user_id: Any, product_id: str) -> bool:
    """Removes specific item from shopping list."""
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    if uid in data and "shopping_list" in data[uid]:
        initial_len = len(data[uid]["shopping_list"])
        data[uid]["shopping_list"] = [
            i for i in data[uid]["shopping_list"] if i.get("id") != product_id
        ]
        if len(data[uid]["shopping_list"]) < initial_len:
            _save_json(FAVORITES_FILE, data)
            return True
    return False

def clear_shopping_list(user_id: Any) -> None:
    """Wipes all items from shopping list."""
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)
    if uid in data:
        data[uid]["shopping_list"] = []
        _save_json(FAVORITES_FILE, data)

def get_all_favorites():
    """Returns the complete favorites mapping for all users."""
    data = _load_json(FAVORITES_FILE)
    return data.get("favorites", {})