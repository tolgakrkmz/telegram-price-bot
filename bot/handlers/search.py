from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes, ConversationHandler

from api.supermarket import get_product_price
from utils.menu import main_menu_keyboard
from utils.helpers import get_product_id, calculate_unit_price
from utils.message_cache import add_message
from db.storage import (
    get_cached_search, 
    save_search_to_cache, 
    update_price_history, 
    get_product_history
)

# Constants
SEARCH_INPUT = 1
CURRENCY = "€"

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initializes the search process and prompts for user input."""
    prompt_text = "🔍 Enter the product name:"
    user_id = update.effective_user.id

    if update.message:
        msg = await update.message.reply_text(prompt_text)
        add_message(user_id, msg.message_id)
    elif update.callback_query:
        await update.callback_query.answer()
        msg = await update.callback_query.message.reply_text(prompt_text)
        add_message(user_id, msg.message_id)
    
    return SEARCH_INPUT

async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes search input, handles caching, compares unit prices, and displays results."""
    user_input = update.message.text.strip()
    user_id = update.effective_user.id

    # 1. Attempt to retrieve from cache
    products = get_cached_search(user_input)
    is_cached = True

    if not products:
        # 2. Fetch from API if cache is empty
        products = get_product_price(user_input, multiple=True)
        if products:
            save_search_to_cache(user_input, products)
        is_cached = False

    if not products:
        msg = await update.message.reply_text("❌ No products found.")
        add_message(user_id, msg.message_id)
        return ConversationHandler.END

    # 3. Enrich products with unit price data for comparison
    for p in products:
        u_price, u_unit = calculate_unit_price(p.get('price'), p.get('unit'))
        p['calc_unit_price'] = u_price
        p['base_unit'] = u_unit

    # 4. Sort products by unit price (Value for Money)
    # Products with no valid unit price are sorted to the bottom
    products.sort(key=lambda x: x['calc_unit_price'] if x['calc_unit_price'] is not None else float('inf'))

    # Determine the best value across all results
    cheapest_unit_val = products[0]['calc_unit_price'] if products else None

    search_results = {}
    messages_to_cache = []

    for p in products:
        product_id = get_product_id(p)
        search_results[product_id] = p
        
        # 5. Persistence: Record fresh data to history
        if not is_cached:
            update_price_history(product_id, p['price'], p['name'], p['store'])

        # 6. Trend Analysis
        history = get_product_history(product_id)
        trend_text = ""
        if len(history) > 1:
            try:
                prev_price = float(history[-2]['price'])
                curr_price = float(p['price'])
                
                if curr_price < prev_price:
                    trend_text = f"📉 Price drop! (was {prev_price:.2f}{CURRENCY})\n"
                elif curr_price > prev_price:
                    trend_text = f"📈 Price increase! (was {prev_price:.2f}{CURRENCY})\n"
            except (ValueError, KeyError, IndexError):
                pass

        # 7. UI Construction with Value Comparison
        unit_price_info = ""
        best_value_tag = ""
        
        if p.get('calc_unit_price'):
            unit_price_info = f"⚖️ Unit Price: **{p['calc_unit_price']:.2f}{CURRENCY}/{p['base_unit']}**\n"
            # Tag the most cost-effective option
            if p['calc_unit_price'] == cheapest_unit_val:
                best_value_tag = "🏆 *BEST VALUE*\n"

        caption = (
            f"{best_value_tag}"
            f"🛒 *{p['name']}*\n"
            f"💰 Price: **{p['price']:.2f}{CURRENCY}** ({p['unit']})\n"
            f"{unit_price_info}"
            f"🏬 Store: {p['store']}\n"
            f"{trend_text}"
        )
        
        if p.get("discount"):
            caption += f"💸 Discount: {p['discount']}%\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Add to Favorites", callback_data=f"add_favorite_{product_id}")],
            [InlineKeyboardButton("🛒 Add to Cart", callback_data=f"add_shopping_{product_id}")]
        ])

        try:
            if p.get("image"):
                msg = await update.message.reply_photo(
                    p["image"], 
                    caption=caption, 
                    reply_markup=keyboard,
                    parse_mode=constants.ParseMode.MARKDOWN
                )
            else:
                msg = await update.message.reply_text(
                    caption, 
                    reply_markup=keyboard,
                    parse_mode=constants.ParseMode.MARKDOWN
                )
            messages_to_cache.append(msg.message_id)
        except Exception:
            continue

    context.user_data["search_results"] = search_results

    # 8. Final UX confirmation
    footer_text = "✅ Search completed!" + (" (cached data)" if is_cached else "")
    final_msg = await update.message.reply_text(
        footer_text,
        reply_markup=main_menu_keyboard()
    )
    messages_to_cache.append(final_msg.message_id)

    # Cache message IDs for later cleanup
    for m_id in messages_to_cache:
        add_message(user_id, m_id)

    return ConversationHandler.END