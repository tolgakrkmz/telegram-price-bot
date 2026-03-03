from typing import Any, List, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import SUPER_API_BASE, SUPER_API_KEY

session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
)
session.mount("https://", HTTPAdapter(max_retries=retries))


def get_product_price(
    product_name: str, multiple: bool = False, stores: Optional[List[str]] = None
) -> Union[dict[str, Any], None, List[dict[str, Any]]]:
    """
    Fetches product data and strictly filters results by selected stores manually.
    """
    url = f"{SUPER_API_BASE}/products"
    params = {"search": product_name, "limit": 50, "api_key": SUPER_API_KEY}

    active_stores_lower = []
    if stores:
        if isinstance(stores, str):
            active_stores_lower = [
                s.strip().lower() for s in stores.split(",") if s.strip()
            ]
        else:
            active_stores_lower = [str(s).strip().lower() for s in stores if s]

    try:
        headers = {"Authorization": f"Bearer {SUPER_API_KEY}"}
        response = session.get(url, headers=headers, params=params, timeout=12)
        response.raise_for_status()

        data = response.json().get("data", [])
        if not data:
            return [] if multiple else None

        results = []
        for p in data:
            store_data = p.get("supermarket", {})
            api_store_name = str(store_data.get("name", "")).strip()
            api_store_name_lower = api_store_name.lower()

            if active_stores_lower and "all" not in active_stores_lower:
                if api_store_name_lower not in active_stores_lower:
                    continue

            results.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name", "Unknown Product"),
                    "price": p.get("price_lev", 0.0),
                    "price_eur": p.get("price_eur", 0.0),
                    "unit": p.get("quantity", "n/a"),
                    "quantity": p.get("quantity"),
                    "store": api_store_name or "Unknown Store",
                    "supermarket": store_data,
                    "image": p.get("image_url"),
                    "image_url": p.get("image_url"),
                    "discount": p.get("discount"),
                    "brochure": p.get("brochure"),
                }
            )

        if multiple:
            return results
        return results[0] if results else None

    except Exception:
        return [] if multiple else None
