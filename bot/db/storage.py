import json
from pathlib import Path
from datetime import datetime, timedelta

FAVORITES_FILE = Path(__file__).parent / "favorites.json"
HISTORY_FILE = Path(__file__).parent / "price_history.json"
CACHE_FILE = Path(__file__).parent / "search_cache.json"

def load_json(file_path):
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- ЛОГИКА ЗА ИСТОРИЯ НА ЦЕНИТЕ ---
def update_price_history(product_id, price, name, store):
    history = load_json(HISTORY_FILE)
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if product_id not in history:
        history[product_id] = {
            "name": name,
            "store": store,
            "prices": []
        }
    
    # Проверяваме дали вече имаме запис за днес, за да не дублираме
    last_entry = history[product_id]["prices"][-1] if history[product_id]["prices"] else None
    if not last_entry or last_entry["date"] != date_str:
        history[product_id]["prices"].append({
            "date": date_str,
            "price": float(price)
        })
        save_json(HISTORY_FILE, history)

def get_product_history(product_id):
    history = load_json(HISTORY_FILE)
    return history.get(product_id, {}).get("prices", [])

# --- ЛОГИКА ЗА КЕШИРАНЕ НА ТЪРСЕНЕТО ---
def get_cached_search(query):
    cache = load_json(CACHE_FILE)
    query = query.lower().strip()
    
    if query in cache:
        entry = cache[query]
        # Кешът е валиден 12 часа
        cached_time = datetime.fromisoformat(entry["timestamp"])
        if datetime.now() - cached_time < timedelta(hours=12):
            return entry["results"]
    return None

def save_search_to_cache(query, results):
    cache = load_json(CACHE_FILE)
    cache[query.lower().strip()] = {
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    save_json(CACHE_FILE, cache)

# --- СТАНДАРТНИ ФУНКЦИИ (БЕЗ ПРОМЯНА В СТРУКТУРАТА) ---
def load_data(): return load_json(FAVORITES_FILE)
def save_data(data): save_json(FAVORITES_FILE, data)

def add_favorite(user_id, product):
    data = load_data()
    user_id = str(user_id)
    if user_id not in data: data[user_id] = {}
    
    product_id = product.get("id")
    if not product_id:
        from utils.helpers import get_product_id
        product_id = get_product_id(product)
        product["id"] = product_id

    if product_id in data[user_id]: return False
    
    data[user_id][product_id] = product
    save_data(data)
    # При добавяне в любими, веднага записваме и в историята
    update_price_history(product_id, product['price'], product['name'], product['store'])
    return True

def remove_favorite(user_id, product_id):
    data = load_data()
    user_id = str(user_id)
    if user_id in data and product_id in data[user_id]:
        del data[user_id][product_id]
        save_data(data)
        return True
    return False

def get_favorites(user_id):
    data = load_data()
    user_data = data.get(str(user_id), {})
    return {k: v for k, v in user_data.items() if k != "shopping_list" and isinstance(v, dict)}

# --- SHOPPING LIST (КОПИРАЙ ОТ СТАРИЯ ФАЙЛ) ---
def ensure_shopping_schema(data, user_id):
    if user_id not in data: data[user_id] = {}
    if "shopping_list" not in data[user_id]: data[user_id]["shopping_list"] = []
    if isinstance(data[user_id]["shopping_list"], dict):
        data[user_id]["shopping_list"] = list(data[user_id]["shopping_list"].values())
    return data

def add_to_shopping(user_id, product):
    data = load_data()
    user_id = str(user_id)
    data = ensure_shopping_schema(data, user_id)
    if not product.get("id"):
        from utils.helpers import get_product_id
        product["id"] = get_product_id(product)
    for item in data[user_id]["shopping_list"]:
        if item.get("id") == product["id"]: return False
    data[user_id]["shopping_list"].append(product)
    save_data(data)
    return True

def get_shopping_list(user_id):
    data = load_data()
    data = ensure_shopping_schema(data, str(user_id))
    return data[str(user_id)]["shopping_list"]

def remove_from_shopping(user_id, product_id):
    data = load_data()
    data = ensure_shopping_schema(data, str(user_id))
    shopping = data[str(user_id)]["shopping_list"]
    for i, item in enumerate(shopping):
        if item.get("id") == product_id:
            shopping.pop(i)
            save_data(data)
            return True
    return False

def clear_shopping_list(user_id):
    data = load_data()
    data = ensure_shopping_schema(data, str(user_id))
    data[str(user_id)]["shopping_list"] = []
    save_data(data)
    return True