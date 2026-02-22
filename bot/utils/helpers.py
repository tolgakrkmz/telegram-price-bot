import hashlib
import re

def get_product_id(product: dict) -> str:
    """
    Генерира уникален ID за продукт от неговите ключови данни.
    """
    unique_string = f"{product['name']}_{product['store']}_{product['price']}"
    return hashlib.md5(unique_string.encode()).hexdigest()

def calculate_unit_price(price, unit_str):
    """
    Parses unit strings like '1.5 L', '500 g', '1kg' and returns price per 1L or 1kg.
    Supports both Latin and Cyrillic units.
    """
    if not unit_str or price is None:
        return None, None

    # Regex to extract numeric value and the unit label
    # Matches '500g', '500 g', '1.5L', etc.
    match = re.search(r"(\d+[\.,]?\d*)\s*([a-zA-Zа-яА-Я]+)", str(unit_str).lower())
    if not match:
        return None, None

    try:
        value = float(match.group(1).replace(',', '.'))
        unit = match.group(2)
    except (ValueError, IndexError):
        return None, None

    # Normalization mapping
    # Weight: g, гр, г -> kg
    # Volume: ml, мл -> l
    weight_units = ['g', 'гр', 'г', 'kg', 'кг']
    volume_units = ['ml', 'мл', 'l', 'л']
    
    base_unit = "kg" if unit in weight_units else "l"
    norm_value = value

    # Convert grams/milliliters to base (kg/l)
    if unit in ['g', 'гр', 'г', 'ml', 'мл']:
        norm_value = value / 1000
    
    if norm_value > 0:
        return round(price / norm_value, 2), base_unit
        
    return None, None