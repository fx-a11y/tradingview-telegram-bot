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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

def get_market_news():
    url = f"https://api.marketaux.com/v1/news/all?api_token={MARKETAUX_API_KEY}&symbols=USD,XAU,EUR,GBP,JPY&language=en&limit=5"
    response = requests.get(url)
    return response.json()

def get_calendar():
    try:
        url = "https://api.datasectors.com/api/calendar"

        headers = {
            "Authorization": f"Bearer {DATASECTORS_API_KEY}"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        if response.status_code != 200:
            return {
                "events": [],
                "error": response.text,
                "status_code": response.status_code
            }

        data = response.json()

        # DEBUG
        print("CALENDAR TYPE:", type(data))
        print("CALENDAR KEYS:", data.keys())

        inner = data.get("data")

        print("INNER TYPE:", type(inner))

        if isinstance(inner, dict):
            print("INNER KEYS:", inner.keys())
            print("EVENT DATA TYPE:", type(inner.get("data")))

        # Ambil daftar event
        events = (
            data
            .get("data", {})
            .get("data", [])
        )

        # Pastikan events berupa LIST
        if not isinstance(events, list):
            return {
                "events": [],
                "error": "Format calendar tidak sesuai",
                "raw_type": str(type(events))
            }

        return {
            "events": events
        }

    except Exception as e:
        return {
            "events": [],
            "error": str(e)
        }


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
        currency = str(event.get("currencyCode", "")).upper()
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

        difference_seconds = (
            event_time - now
        ).total_seconds()

        time_difference = abs(difference_seconds)

        if time_difference <= 30 * 60:

            minutes = round(time_difference / 60)

            if difference_seconds > 0:
                status = "BEFORE"
                message = f"{minutes} menit sebelum berita"
            else:
                status = "AFTER"
                message = f"{minutes} menit setelah berita"

            return {
                "pause": True,
                "status": status,
                "reason": event.get("name"),
                "currency": event.get("currencyCode"),
                "volatility": event.get("volatility"),
                "event_time": date_utc,
                "minutes": minutes,
                "message": message
            }

    return {
        "pause": False,
        "status": None,
        "reason": None,
        "currency": None,
        "volatility": None,
        "event_time": None,
        "minutes": None,
        "message": None
        }

def analyze_with_claude(pair, signal_data, price):
    try:
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        prompt = f"""
Kamu adalah AI trading analyst.

Analisa market berikut:

PAIR:
{pair}

HARGA:
{price}

DATA SIGNAL:
{signal_data}

Tugas:
Tentukan hanya satu keputusan:

BUY
SELL
NO TRADE

Pertimbangkan:
- arah signal
- kondisi market
- risiko false signal
- jangan memaksakan entry

Jawab dalam format JSON persis:

{{
  "decision": "BUY/SELL/NO TRADE",
  "confidence": 0-100,
  "reason": "alasan singkat"
}}
"""

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            return {
                "decision": "NO TRADE",
                "confidence": 0,
                "reason": f"Claude API error: {response.text}"
            }

        result = response.json()

        ai_text = result["content"][0]["text"]

        import json

        ai_result = json.loads(ai_text)

        return {
            "decision": ai_result.get("decision", "NO TRADE"),
            "confidence": ai_result.get("confidence", 0),
            "reason": ai_result.get("reason", "")
        }

    except Exception as e:
        return {
            "decision": "NO TRADE",
            "confidence": 0,
            "reason": f"AI error: {str(e)}"
        }

def process_signal(pair, signal_data):
    # 1. Cek news pause
    news = is_news_pause(pair)

    if news["pause"]:
        return {
            "decision": "PAUSE",
            "pair": pair,
            "reason": news["reason"],
            "currency": news["currency"],
            "volatility": news["volatility"],
            "event_time": news["event_time"],
            "message": news.get("message", "High impact news detected")
        }

    # 2. Ambil harga
    price_data = get_forex_price(
        f"{pair[:3]}/{pair[3:]}"
        if len(pair) == 6
        else pair
    )

    # 3. Analisa Claude
    ai_result = analyze_with_claude(
        pair,
        signal_data,
        price_data
    )

    # 4. Return hasil AI
    return {
        "decision": ai_result["decision"],
        "pair": pair,
        "confidence": ai_result["confidence"],
        "reason": ai_result["reason"],
        "price": price_data
        }

@app.route("/pause-debug/<pair>")
def pause_debug(pair):
    events = get_relevant_events(pair)

    now = datetime.now(timezone.utc)

    result = []

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

        difference_minutes = (
            event_time - now
        ).total_seconds() / 60

        result.append({
            "name": event.get("name"),
            "currency": event.get("currencyCode"),
            "volatility": event.get("volatility"),
            "event_time": date_utc,
            "minutes_to_news": round(difference_minutes, 2),
            "inside_pause_window": abs(difference_minutes) <= 30
        })

    return jsonify({
        "pair": pair.upper().replace("/", ""),
        "server_time_utc": now.isoformat(),
        "pause_window_minutes": 30,
        "events": result
    })
    
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}

    # Ambil pair dari request/API
    pair = str(data.get("symbol", "")).upper().replace("/", "")

    if not pair:
        return {
            "status": "error",
            "message": "Symbol tidak ditemukan"
        }, 400

    # Format symbol untuk Twelve Data
    symbol = pair

    # Contoh:
    # XAUUSD -> XAU/USD
    # EURUSD -> EUR/USD
    # GBPUSD -> GBP/USD
    if len(symbol) == 6:
        symbol = f"{symbol[:3]}/{symbol[3:]}"

    # Ambil harga terbaru
    price = get_forex_price(symbol)

    # Proses signal + cek news pause
    result = process_signal(
        pair,
        data
    )

    # =========================
    # NEWS PAUSE
    # =========================

    if result["decision"] == "PAUSE":

        text = f"""
🔴 NEWS PAUSE

Pair: {pair}

Status: PAUSE

News:
{result["reason"]}

Currency:
{result["currency"]}

Volatility:
{result["volatility"]}

Event Time:
{result["event_time"]}

Harga:
{price}
"""

    # =========================
    # LANJUT KE CLAUDE AI
    # =========================

    else:

        text = f"""
📊 SIGNAL MASUK

Pair: {pair}

Harga:
{price}

Data:
{data}

Status:
ANALYZE BY CLAUDE AI
"""

    # Kirim Telegram
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text
        }
    )

    return {
        "status": "OK",
        "pair": pair,
        "price": price,
        "decision": result["decision"]
    }
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

