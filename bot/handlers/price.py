from telegram import Update
from telegram.ext import ContextTypes

from api.supermarket import get_product_price


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Пример: /price bananas")
        return

    product_name = " ".join(context.args).lower()
    result = get_product_price(product_name)

    if not result:
        await update.message.reply_text("❌ Няма намерен продукт")
        return

    await update.message.reply_text(
        f"🛒 *{result['name'].title()}*\n"
        f"Цена: {result['price']} лв / {result['unit']}\n"
        f"Магазин: {result['store']}",
        parse_mode="Markdown",        
    )
