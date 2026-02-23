import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
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

def _load_json(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_json(file_path: Path, data: Dict[str, Any]) -> None:
    temp_file = file_path.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(file_path)
    except IOError:
        if temp_file.exists():
            temp_file.unlink()
        raise


# ==============================
# PRICE HISTORY
# ==============================

def update_price_history(product_id: str, price: float, name: str, store: str) -> None:
    history = _load_json(HISTORY_FILE)
    date_str = datetime.now().strftime("%Y-%m-%d")

    if product_id not in history:
        history[product_id] = {
            "name": name,
            "store": store,
            "prices": []
        }

    prices = history[product_id]["prices"]

    if not prices or prices[-1]["date"] != date_str:
        prices.append({
            "date": date_str,
            "price": float(price)
        })
        _save_json(HISTORY_FILE, history)


def get_product_history(product_id: str) -> List[Dict[str, Any]]:
    return _load_json(HISTORY_FILE).get(product_id, {}).get("prices", [])


# ==============================
# SEARCH CACHE (12h TTL)
# ==============================

def get_cached_search(query: str) -> Optional[List[Dict[str, Any]]]:
    cache = _load_json(CACHE_FILE)
    key = query.lower().strip()

    if key in cache:
        entry = cache[key]
        cached_time = datetime.fromisoformat(entry["timestamp"])

        if datetime.now() - cached_time < timedelta(hours=12):
            return entry["results"]

    return None


def save_search_to_cache(query: str, results: List[Dict[str, Any]]) -> None:
    cache = _load_json(CACHE_FILE)
    cache[query.lower().strip()] = {
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    _save_json(CACHE_FILE, cache)


# ==============================
# FAVORITES
# ==============================

def get_favorites(user_id: Any) -> Dict[str, Dict[str, Any]]:
    data = _load_json(FAVORITES_FILE)
    user_data = data.get(str(user_id), {})

    return {
        k: v for k, v in user_data.items()
        if k != "shopping_list" and isinstance(v, dict)
    }


def add_favorite(user_id: Any, product: Dict[str, Any]) -> bool:
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

def _ensure_shopping_schema(data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    if user_id not in data:
        data[user_id] = {}

    if "shopping_list" not in data[user_id]:
        data[user_id]["shopping_list"] = []

    return data


def get_shopping_list(user_id: Any) -> List[Dict[str, Any]]:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)

    data = _ensure_shopping_schema(data, uid)

    return data[uid]["shopping_list"]


def add_to_shopping(user_id: Any, product: Dict[str, Any]) -> bool:
    data = _load_json(FAVORITES_FILE)
    uid = str(user_id)

    data = _ensure_shopping_schema(data, uid)

    # 🔥 Always ensure stable ID
    pid = product.get("id")
    if not pid:
        pid = get_product_id(product)
        product["id"] = pid

    pid = str(pid)
    product["id"] = pid  # ensure stored as string

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

        updated = [
            item for item in original
            if str(item.get("id")) != product_id
        ]

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


def get_all_favorites() -> Dict[str, Any]:
    return _load_json(FAVORITES_FILE)