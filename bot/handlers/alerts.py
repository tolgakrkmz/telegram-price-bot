import asyncio

from telegram import Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.storage import get_all_favorites, get_favorites, update_price_history

CURRENCY = "€"


async def global_price_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Automated global task: Updates unique favorite products across all users
    and sends push notifications if prices drop or rise.
    """
    all_favs = get_all_favorites()  # Needs to be in storage.py
    if not all_favs:
        return

    # Identify unique products to save API requests
    unique_prods: dict[str, dict] = {}
    for user_id, user_favs in all_favs.items():
        for pid, p in user_favs.items():
            unique_prods[pid] = p

    for pid, p in unique_prods.items():
        new_results = get_product_price(p["name"], multiple=True)
        await asyncio.sleep(1.5)  # Protect API limits

        if not isinstance(new_results, list):
            continue

        match = next(
            (item for item in new_results if item["store"] == p["store"]), None
        )
        if match:
            new_price = float(match["price"])
            old_price = float(p.get("price", 0))

            if new_price != old_price:
                update_price_history(pid, new_price, p["name"], p["store"])
                diff = new_price - old_price
                icon = "📉" if diff < 0 else "📈"

                msg = (
                    f"{icon} *Price Alert!*\n"
                    f"🛒 {p['name']}\n"
                    f"💰 New Price: **{new_price:.2f}{CURRENCY}**\n"
                    f"🏬 Store: {p['store']}"
                )

                # Notify all users tracking this product
                for user_id, user_favs in all_favs.items():
                    if pid in user_favs:
                        try:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=msg,
                                parse_mode=constants.ParseMode.MARKDOWN,
                            )
                        except Exception:
                            continue


async def update_favorites_prices(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Manual update triggered by /update_prices command."""
    user_id = update.effective_user.id
    favorites = get_favorites(user_id)
    if not favorites:
        await update.message.reply_text("⭐ Your favorites list is empty.")
        return

    status_msg = await update.message.reply_text("🔄 Syncing latest prices...")
    report = ["📊 *Price Report:*\n"]

    for pid, p in favorites.items():
        new_results = get_product_price(p["name"], multiple=True)
        await asyncio.sleep(1.2)
        match = next((i for i in new_results if i["store"] == p["store"]), None)
        if match:
            new_p = float(match["price"])
            old_p = float(p.get("price", 0))
            update_price_history(pid, new_p, p["name"], p["store"])
            diff = new_p - old_p
            change = f"({'-' if diff < 0 else '+'}{abs(diff):.2f})" if diff != 0 else ""
            report.append(f"✅ {p['name']}: **{new_p:.2f}{CURRENCY}** {change}")

    await status_msg.edit_text(
        "\n".join(report), parse_mode=constants.ParseMode.MARKDOWN
    )
