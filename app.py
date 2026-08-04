from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_KEY = os.getenv("TWELVE_DATA_API_KEY")

def get_forex_price(symbol="XAU/USD"):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    return response.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    price = get_forex_price("XAU/USD")

    text = f"""
Alert:
{data}

Harga XAUUSD:
{price}
"""

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text
        }
    )

    return "OK"
@app.route("/")
def home():
    return get_forex_price("XAU/USD")
    @app.route("/test")
def test():

    price = get_forex_price("XAU/USD")

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": f"✅ Tes berhasil!\n\nHarga XAUUSD: {price['price']}"
        }
    )

    return "Pesan terkirim ke Telegram"
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

