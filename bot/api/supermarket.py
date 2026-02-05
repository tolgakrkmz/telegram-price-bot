import requests
from config.settings import SUPER_API_KEY, SUPER_API_BASE

def get_product_price(product_name: str, multiple=False):
    url = f"{SUPER_API_BASE}/products"
    headers = {"Authorization": f"Bearer {SUPER_API_KEY}"}
    params = {"search": product_name, "limit": 5}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            return None

        results = [
            {
                "name": p.get("name"),
                "price": p.get("price_lev"),
                "unit": p.get("quantity"),
                "store": p.get("supermarket", {}).get("name"),
                "image": p.get("image_url"),
                "discount": p.get("discount")
            }
            for p in data
        ]

        return results if multiple else results[0]

    except Exception as e:
        print("API error:", e)
        return None
