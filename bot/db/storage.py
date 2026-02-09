import json
import os

FAV_FILE = "db/favorites.json"

def load_data():
    if not os.path.exists(FAV_FILE):
        return {}
    try:
        with open(FAV_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:  # празен файл
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        return {}

def save_data(data):
    with open(FAV_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_favorite(user_id, product_name):
    data = load_data()
    user_favs = data.get(str(user_id), [])
    if product_name in user_favs:
        return False
    user_favs.append(product_name)
    data[str(user_id)] = user_favs
    save_data(data)
    return True

def get_favorites(user_id):
    """Връща списък с продукти на user_id"""
    data = load_data()
    return data.get(str(user_id), [])
