from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Търси продукт", callback_data="search")],
        [InlineKeyboardButton("⭐ Моите любими", callback_data="list_favorites")],
        [InlineKeyboardButton("🧹 Изчисти чат", callback_data="clear_chat")],
        [InlineKeyboardButton("📂 Категории", callback_data="categories")],
        [InlineKeyboardButton("🛒 Количка за пазаруване", callback_data="shopping_list")]
    ]
    return InlineKeyboardMarkup(keyboard)


def favorites_keyboard(favorites):
    keyboard = []
    for pid, product in favorites.items():
        keyboard.append([InlineKeyboardButton(f"❌ {product['name']}", callback_data=f"delete_{pid}")])

    keyboard.append([InlineKeyboardButton("⬅️ Върни се в менюто", callback_data="main_menu")])

    return InlineKeyboardMarkup(keyboard)
