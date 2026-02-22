import asyncio
from typing import Dict, Any, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from utils.menu import main_menu_keyboard
from api.supermarket import get_product_price
from utils.helpers import calculate_unit_price, format_promo_dates # Added format_promo_dates
from db.storage import (
    add_to_shopping,
    get_shopping_list,
    remove_from_shopping,
    clear_shopping_list,
    get_cached_search,
    save_search_to_cache,
    _load_json as load_json,
    CACHE_FILE
)

CURRENCY = "€"

def get_better_price(
    product_name: str, 
    current_price: float, 
    current_store: str, 
    current_item: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Analyzes cached data to find better deals using EUR prices.
    """
    cache = load_json(CACHE_FILE)
    better_option = None
    
    # Use fallback keys for unit price calculation
    curr_u_price, _ = calculate_unit_price(current_price, current_item.get('quantity') or current_item.get('unit'))
    
    if curr_u_price is None:
        return None

    min_unit_price = curr_u_price

    ignore_words = {'pilos', 'саяна', 'lidl', 'kaufland', 'billa', 'боженци', 'vereia', 'верея'}
    keywords = [w for w in product_name.lower().split() if w not in ignore_words and len(w) > 2]

    for query, data in cache.items():
        # Handle cases where cache structure might vary
        results = data if isinstance(data, list) else data.get("results", [])
        for p in results:
            p_name_lower = p.get('name', '').lower()
            match_count = sum(1 for word in keywords if word in p_name_lower)
            
            if match_count >= 2:
                try:
                    # Get prices and stores using fallback mapping
                    p_price = float(p.get('price_eur') or p.get('price', 0))
                    p_unit = p.get('quantity') or p.get('unit')
                    p_store = p.get('supermarket', {}).get('name') if isinstance(p.get('supermarket'), dict) else p.get('store', 'Unknown')

                    p_u_price, _ = calculate_unit_price(p_price, p_unit)
                    
                    if p_u_price and p_store != current_store and p_u_price < min_unit_price:
                        if "%" in product_name:
                            percentage = [s for s in product_name.split() if "%" in s]
                            if percentage and percentage[0] not in p_name_lower:
                                continue
                        
                        min_unit_price = p_u_price
                        # Create a clean display object for 'better'
                        better_option = {
                            'price': p_price,
                            'unit': p_unit,
                            'store': p_store
                        }
                except (ValueError, TypeError, KeyError):
                    continue
    return better_option

async def safe_edit(query, text: str, reply_markup: InlineKeyboardMarkup = None) -> None:
    """Safely updates messages with either text or caption."""
    params = {
        "text" if query.message.text else "caption": text,
        "reply_markup": reply_markup,
        "parse_mode": constants.ParseMode.MARKDOWN
    }
    try:
        if query.message.text:
            await query.edit_message_text(**params)
        else:
            await query.edit_message_caption(**params)
    except Exception:
        # Fallback if message is unchanged
        pass

async def list_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the shopping list with dates and EUR comparisons."""
    query = update.callback_query
    user_id = update.effective_user.id
    shopping = get_shopping_list(user_id)

    if not shopping:
        text = "🛒 Your cart is empty."
        reply_markup = main_menu_keyboard()
        if query:
            await query.answer()
            await safe_edit(query, text, reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
        return

    if query: await query.answer()

    total_sum = 0.0
    potential_savings = 0.0
    store_totals: Dict[str, float] = {}
    report_lines = ["🛒 *Your Shopping List*\n"]
    keyboard = []

    # Iterate through cart
    # shopping can be dict {pid: p} or list [p1, p2] depending on your storage.py
    # Assuming list based on your previous shopping.py logic
    items = shopping.items() if isinstance(shopping, dict) else enumerate(shopping)

    for idx, product in items:
        # Fallback mapping
        price = float(product.get("price_eur") or product.get("price", 0))
        store = product.get("supermarket", {}).get("name") if isinstance(product.get("supermarket"), dict) else product.get("store", "Unknown")
        name = product.get("name", "Unknown")
        unit = product.get("quantity") or product.get("unit", "N/A")
        product_id = product.get("id") or idx

        total_sum += price
        store_totals[store] = store_totals.get(store, 0.0) + price

        # Extract dates via helper
        promo_timer = format_promo_dates(product)
        promo_text = f" | ⏳ {promo_timer}" if promo_timer else ""

        # Smart Comparison
        better = get_better_price(name, price, store, product)
        better_text = ""
        if better:
            better_text = f"   💡 *Better Deal:* {better['price']:.2f}{CURRENCY} ({better['unit']}) at {better['store']}\n"
            if better.get('unit') == unit:
                potential_savings += (price - float(better['price']))

        report_lines.append(f"• {name}\n   💰 **{price:.2f}{CURRENCY}** ({unit}){promo_text}\n   🏬 {store}\n{better_text}")
        keyboard.append([InlineKeyboardButton(f"🗑 Remove {name[:15]}...", callback_data=f"remove_shopping_{product_id}")])

    summary = [
        f"\n📦 Items: {len(shopping)}",
        f"💰 *Total Sum: {total_sum:.2f}{CURRENCY}*"
    ]
    
    if potential_savings > 0:
        summary.append(f"✨ *Potential Savings: {potential_savings:.2f}{CURRENCY}*")

    summary.append("\n🧾 *By Store:*")
    for store, s_sum in store_totals.items():
        summary.append(f"• {store}: {s_sum:.2f}{CURRENCY}")

    report_lines.extend(summary)
    keyboard.append([InlineKeyboardButton("🧹 Clear Cart", callback_data="confirm_clear")])
    keyboard.append([InlineKeyboardButton("⬅️ Menu", callback_data="main_menu")])

    final_text = "\n".join(report_lines)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await safe_edit(query, final_text, reply_markup)
    else:
        await update.message.reply_text(final_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def add_to_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    await query.answer()

    product_id = query.data.replace("add_shopping_", "")
    search_results = context.user_data.get("search_results", {})
    product = search_results.get(product_id)
    
    if not product:
        await safe_edit(query, "❌ Product not found.")
        return

    added = add_to_shopping(query.from_user.id, product)
    msg = f"🛒 *{product['name']}* added to cart." if added else "ℹ️ Already in cart."
    await safe_edit(query, msg)

async def remove_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    await query.answer()
    remove_from_shopping(update.effective_user.id, query.data.replace("remove_shopping_", ""))
    await list_shopping(update, context)

async def confirm_clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    await query.answer()
    keyboard = [[
        InlineKeyboardButton("✅ Yes", callback_data="clear_shopping"),
        InlineKeyboardButton("❌ Cancel", callback_data="view_shopping")
    ]]
    await safe_edit(query, "⚠️ Clear the entire cart?", InlineKeyboardMarkup(keyboard))

async def clear_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    await query.answer()
    clear_shopping_list(update.effective_user.id)
    await safe_edit(query, "🧹 Cart has been cleared.", reply_markup=main_menu_keyboard())