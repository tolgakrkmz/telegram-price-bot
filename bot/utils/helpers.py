import hashlib
import re
from datetime import datetime


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
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2)
    except (ValueError, IndexError):
        return None, None

    # Normalization mapping
    # Weight: g, гр, г -> kg
    # Volume: ml, мл -> l
    weight_units = ["g", "гр", "г", "kg", "кг"]

    base_unit = "kg" if unit in weight_units else "l"
    norm_value = value

    # Convert grams/milliliters to base (kg/l)
    if unit in ["g", "гр", "г", "ml", "мл"]:
        norm_value = value / 1000

    if norm_value > 0:
        return round(price / norm_value, 2), base_unit

    return None, None


def format_promo_dates(product: dict) -> str:
    """Extracts valid_until from product['brochure'] and formats it."""
    brochure = product.get("brochure")
    if not brochure or not isinstance(brochure, dict):
        return ""

    until_date = brochure.get("valid_until")
    if not until_date:
        return ""

    try:
        # Expected format from API: YYYY-MM-DD
        date_obj = datetime.strptime(until_date, "%Y-%m-%d")

        # Check if already expired
        if date_obj.date() < datetime.now().date():
            return f"⚠️ Expired ({date_obj.strftime('%d.%m')})"

        return f"⏳ until {date_obj.strftime('%d.%m')}"
    except (ValueError, TypeError):
        # Fallback if date format is different
        return f"⏳ until {until_date}"
