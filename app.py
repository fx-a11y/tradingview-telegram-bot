from flask import Flask, request, jsonify
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

MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")
DATASECTORS_API_KEY = os.getenv("DATASECTORS_API_KEY")

def get_market_news():
    url = f"https://api.marketaux.com/v1/news/all?api_token={MARKETAUX_API_KEY}&symbols=USD,XAU,EUR,GBP,JPY&language=en&limit=5"
    response = requests.get(url)
    return response.json()

def get_calendar():
    url = "https://api.datasectors.com/api/calendar"

    headers = {
        "Authorization": f"Bearer {DATASECTORS_API_KEY}"
    }

    response = requests.get(url, headers=headers, timeout=15)

    if response.status_code != 200:
        return {
            "events": [],
            "error": response.text,
            "status_code": response.status_code
        }

    data = response.json()

    # Ambil daftar event dari struktur DataSectors
    events = (
        data.get("data", {})
            .get("data", {})
            .get("data", [])
    )


def get_relevant_events(pair):
    pair = pair.upper().replace("/", "")

    currencies = PAIR_CURRENCIES.get(pair, [])

    calendar = get_calendar()
    events = calendar.get("events", [])

    filtered_events = []

    for event in events:
        currency = event.get("currencyCode")
        volatility = str(event.get("volatility", "")).upper()

        if currency in currencies and volatility == "HIGH":
            filtered_events.append(event)

    return filtered_events

from datetime import datetime, timezone, timedelta

PAIR_CURRENCIES = {
    "XAUUSD": ["USD"],
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"]
}

def get_relevant_events(pair):
    pair = pair.upper().replace("/", "")

    currencies = PAIR_CURRENCIES.get(pair, [])

    calendar = get_calendar()
    events = calendar.get("events", [])

    relevant_events = []

    for event in events:
        currency = event.get("currencyCode")
        volatility = str(event.get("volatility", "")).upper()

        if currency in currencies and volatility == "HIGH":
            relevant_events.append(event)

    return relevant_events

def is_news_pause(pair):
    events = get_relevant_events(pair)

    now = datetime.now(timezone.utc)

    for event in events:
        date_utc = event.get("dateUtc")

        if not date_utc:
            continue

        try:
            event_time = datetime.fromisoformat(
                date_utc.replace("Z", "+00:00")
            )
        except ValueError:
            continue

        time_difference = abs((event_time - now).total_seconds())

        # 30 menit sebelum sampai 30 menit sesudah news
        if time_difference <= 30 * 60:
            return {
                "pause": True,
                "reason": event.get("name"),
                "currency": event.get("currencyCode"),
                "volatility": event.get("volatility"),
                "event_time": date_utc
            }

    return {
        "pause": False,
        "reason": None
}
    
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

@app.route("/news")
def news():
    return get_market_news()
    
@app.route("/calendar")
def calendar():
    return jsonify(get_calendar())

@app.route("/pause/<pair>")
def pause_check(pair):
    return jsonify(is_news_pause(pair))
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

