# ⚡ DAMXD AUTO HITTER Bot

An advanced, high-performance Telegram Bot built with Python, `aiogram`, and `MongoDB` designed for card verification, custom gateway hits, automated broadcasts, and robust access control.

---

## ✨ Features

- **🛡️ Secure Access Control & Admin Panel**: Integrated authorization checking for both users (Free vs. Premium/Owner plans) and Telegram groups.
- **🔄 Robust Group Authorization Middleware**: Bypasses restrictions for specific administrative setup commands, with intelligent automatic Telegram group ID parsing (e.g., handles formats with or without `100` prefix).
- **💸 Multiple Payment Gateways**: Integration modules for Stripe, Razorpay, Cashfree, PayU, Epoch, and more.
- **⚙️ Dynamic Proxy Rotation**: Rotates through a system proxy pool for free/standard users while supporting dedicated personal proxies for premium users.
- **📈 Advanced Global Stats & Logs**: Detailed execution tracking (total checks, live hits, charged amounts, active codes, banned users) persisted in MongoDB.
- **📣 Automated Hit Broadcaster**: Built-in automated card hits generator and Telegram channel broadcast publisher with visual progress bars.

---

## 🛠️ Installation & Setup

### 1. Requirements

Ensure you have Python 3.8+ and MongoDB installed and running.

Install all dependencies from the `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
MONGO_URL=mongodb://localhost:27017
OWNER_IDS=8303990517
PORT=5000
LOG_CHANNEL_ID=@your_channel_username
UPDATE_PASSWORD=your_secure_update_password
```

---

## 🚀 Running the Bot

Start the main server and Telegram polling loop:

```bash
python main.py
```

This starts:
1. The **Telegram Bot Listener** (aiogram polling).
2. The **HTTP Web Server** (aiohttp server on port `5000`).

---

## 💬 Command Reference

### Group Management
- `/addgp <chat_id>` / `.addgp <chat_id>`: Authorize a group chat to use the bot. (Can be run in private chat or directly inside the group chat).
- `/delgp <chat_id>` / `.delgp <chat_id>`: Deauthorize a group chat.

### Owner Administration
- `/owners`: List all hardcoded Super Owners and database-promoted Owners.
- `/addowner <user_id>`: Promote a user to Database Owner.
- `/removeowner <user_id>`: Demote a database owner.
- `/stats`: Display global bot usage statistics.

### Card Operations
- `/check <card_info>` / `/mash <card_info>`: Perform single or bulk card gateway checks.
