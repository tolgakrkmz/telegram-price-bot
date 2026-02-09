from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Търси продукт", callback_data="search")],
        [InlineKeyboardButton("⭐ Моите любими", callback_data="list_favorites")],
        [InlineKeyboardButton("🧹 Изчисти чат", callback_data="clear_chat")],
        [InlineKeyboardButton("📂 Категории", callback_data="categories")]
    ]
    return InlineKeyboardMarkup(keyboard)


def favorites_keyboard(favorites):
    """
    favorites: dict {product_id: product_dict}
    Връща InlineKeyboardMarkup с бутон за изтриване на всеки продукт
    и бутон за връщане към главното меню
    """
    keyboard = []
    for pid, product in favorites.items():
        keyboard.append([InlineKeyboardButton(f"❌ {product['name']}", callback_data=f"delete_{pid}")])

    # Бутон за връщане към главното меню
    keyboard.append([InlineKeyboardButton("⬅️ Върни се в менюто", callback_data="main_menu")])

    return InlineKeyboardMarkup(keyboard)
