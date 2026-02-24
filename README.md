# 🛒 Telegram Price Bot

A smart Telegram bot that helps users track supermarket prices, discover the best deals, and receive alerts for price drops.

---

## 🚀 Features

- **🔍 Smart Search** – Find products across multiple supermarkets.
- **📈 Price History** – Track how prices change over time with interactive logs.
- **⭐ Favorites** – Save products to your personal watchlist.
- **📉 Price Drop Alerts** – Automatic notifications when your favorite items go on sale.
- **⚠️ Expiry Reminders** – Get notified before a promotion ends (**Today** or **Tomorrow**).
- **☁️ Cloud Powered** – Uses Supabase for real-time data sync and persistent storage.

---

## 🧱 Tech Stack

- **Python 3.11+**
- **python-telegram-bot** – Telegram integration.
- **Supabase** – Cloud database (PostgreSQL) for users, favorites, and history.
- **Alexander Gekov's Price API** – Real-time supermarket data.

---

## 🔐 Environment Variables

To run this bot, create a `.env` file in the root directory:

```env
# Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key

# External API
API_BASE_URL=[https://prices.alexandergekov.com/api](https://prices.alexandergekov.com/api)

```

--

## 🙏 Acknowledgements
This bot uses the Supermarket Prices API provided by Alexander Gekov.

API Source: [prices.alexandergekov.com](https://prices.alexandergekov.com)

Special thanks to Alexander for providing the data that makes this project possible!

## ⚖️ Disclaimer
This project is currently in development and is hosted privately for testing purposes. It is not a commercial product. All product names, logos, and brands are property of their respective owners. Data accuracy is dependent on the source API.

## **Created with ❤️ for better shopping.**