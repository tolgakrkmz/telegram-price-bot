from telegram import Update
from telegram.ext import ContextTypes
from db.storage import get_favorites, update_price_history
from api.supermarket import get_product_price
import asyncio

async def update_favorites_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    favorites = get_favorites(user_id)

    if not favorites:
        await update.message.reply_text("⭐ Списъкът с любими е празен. Няма какво да обновя.")
        return

    status_msg = await update.message.reply_text(f"🔄 Обновявам цените на {len(favorites)} продукта... Моля, изчакайте.")
    
    updated_count = 0
    text = "📊 **Обновяване на цените:**\n\n"

    for pid, p in favorites.items():
        # Правим заявка към API за конкретния продукт по име
        # Ограничаваме до конкретния магазин, за да сме точни
        new_results = get_product_price(p['name'], multiple=True)
        
        if new_results:
            # Търсим съвпадение за същия магазин
            match = next((item for item in new_results if item['store'] == p['store']), None)
            
            if match:
                new_price = float(match['price'])
                old_price = float(p['price'])
                
                # Записваме в историята
                update_price_history(pid, new_price, p['name'], p['store'])
                
                # Обновяваме цената и в самия обект на любимите (в favorites.json)
                # Това ще изисква малка промяна в storage, но засега само докладваме
                
                diff = new_price - old_price
                if diff < 0:
                    text += f"✅ {p['name']}: {new_price} лв (📉 {abs(diff):.2f})\n"
                elif diff > 0:
                    text += f"✅ {p['name']}: {new_price} лв (📈 +{diff:.2f})\n"
                else:
                    text += f"✅ {p['name']}: без промяна ({new_price} лв)\n"
                
                updated_count += 1
        
        # Малка пауза, за да не претоварим API-то и да не ни блокират
        await asyncio.sleep(1)

    await status_msg.edit_text(text if updated_count > 0 else "❌ Не успях да обновя нито един продукт.")