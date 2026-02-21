from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    """Main navigation menu."""
    keyboard = [
        [InlineKeyboardButton("🔍 Search Products", callback_data="search")],
        [
            InlineKeyboardButton("⭐ Favorites", callback_data="list_favorites"),
            InlineKeyboardButton("🛒 Cart", callback_data="shopping_list")
        ],
        [
            InlineKeyboardButton("ℹ️ Info & Help", callback_data="bot_info"),
            InlineKeyboardButton("🧹 Clear Chat", callback_data="clear_chat")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def favorites_keyboard(favorites=None):
    """
    Dynamic menu for favorites. 
    Shows 'Update' button only if there are items to update.
    """
    keyboard = []
    
    if favorites:
        keyboard.append([InlineKeyboardButton("🔄 Update Prices Now", callback_data="update_prices_manual")])
    
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)