import requests
from typing import List, Dict, Optional, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config.settings import SUPER_API_KEY, SUPER_API_BASE

# Setup a global session with retries for resilience
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def get_product_price(
    product_name: str, 
    multiple: bool = False
) -> Union[Optional[Dict[str, Any]], List[Dict[str, Any]], None]:
    """
    Fetches product data from the supermarket API.
    """
    url = f"{SUPER_API_BASE}/products"
    headers = {"Authorization": f"Bearer {SUPER_API_KEY}"}
    params = {"search": product_name, "limit": 5}

    try:
        response = session.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        json_response = response.json()
        data = json_response.get("data", [])

        if not data:
            return [] if multiple else None

        results = []
        for p in data:
            product_info = {
                "id": p.get("id"),
                "name": p.get("name", "Unknown Product"),
                "price": p.get("price_lev", 0.0),
                "price_eur": p.get("price_eur", 0.0),
                "unit": p.get("quantity", "n/a"),
                "quantity": p.get("quantity"),        
                "store": p.get("supermarket", {}).get("name", "Unknown Store"),
                "supermarket": p.get("supermarket"), 
                "image": p.get("image_url"),
                "image_url": p.get("image_url"),      
                "discount": p.get("discount"),
                "brochure": p.get("brochure")
            }
            results.append(product_info)

        if multiple:
            return results
        return results[0] if results else None

    except (requests.exceptions.RequestException, KeyError, ValueError, TypeError):
        return [] if multiple else None