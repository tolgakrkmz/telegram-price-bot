import hashlib

def get_product_id(product: dict) -> str:
    """
    Генерира уникален ID за продукт от неговите ключови данни.
    """
    unique_string = f"{product['name']}_{product['store']}_{product['price']}"
    return hashlib.md5(unique_string.encode()).hexdigest()
