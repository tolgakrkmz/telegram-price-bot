import json
from pathlib import Path

FAVORITES_FILE = Path(__file__).parent / "favorites.json"

def load_data():
    if not FAVORITES_FILE.exists():
        return {}
    with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(data):
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_favorite(user_id, product):
    data = load_data()
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {}

    product_id = product.get("id")
    if not product_id:
        from utils.helpers import get_product_id
        product_id = get_product_id(product)
        product["id"] = product_id

    if product_id in data[user_id]:
        return False

    data[user_id][product_id] = product
    save_data(data)
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
    return data.get(str(user_id), {})


# =========================
# SHOPPING LIST FUNCTIONS
# =========================

def ensure_shopping_schema(data, user_id):
    if user_id not in data:
        data[user_id] = {}

    if "shopping_list" not in data[user_id]:
        data[user_id]["shopping_list"] = []

    # Auto migration от стар dict формат
    if isinstance(data[user_id]["shopping_list"], dict):
        data[user_id]["shopping_list"] = list(
            data[user_id]["shopping_list"].values()
        )

    return data


def add_to_shopping(user_id, product):
    data = load_data()
    user_id = str(user_id)

    data = ensure_shopping_schema(data, user_id)

    if not product.get("id"):
        from utils.helpers import get_product_id
        product["id"] = get_product_id(product)

    for item in data[user_id]["shopping_list"]:
        if item.get("id") == product["id"]:
            return False

    data[user_id]["shopping_list"].append(product)
    save_data(data)
    return True


def get_shopping_list(user_id):
    data = load_data()
    user_id = str(user_id)

    data = ensure_shopping_schema(data, user_id)
    save_data(data)

    return data[user_id]["shopping_list"]


def remove_from_shopping(user_id, product_id):
    data = load_data()
    user_id = str(user_id)

    data = ensure_shopping_schema(data, user_id)

    shopping = data[user_id]["shopping_list"]

    for i, item in enumerate(shopping):
        if item.get("id") == product_id:
            shopping.pop(i)
            save_data(data)
            return True

    return False


def clear_shopping_list(user_id):
    data = load_data()
    user_id = str(user_id)

    data = ensure_shopping_schema(data, user_id)

    data[user_id]["shopping_list"] = []
    save_data(data)
    return True
