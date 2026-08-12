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

def get_market_data(symbol="XAU/USD", interval="15min", outputsize=100):
    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY
    }

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        return {
            "error": response.text
        }

    return response.json()

def get_multi_timeframe_data(symbol):
    """
    Mengambil data market dari 3 timeframe:
    5M  = momentum / entry
    15M = setup utama
    1H  = trend utama
    """

    timeframes = {
        "5min": 100,
        "15min": 100,
        "1h": 100
    }

    result = {}

    for interval, outputsize in timeframes.items():

        try:
            data = get_market_data(
                symbol=symbol,
                interval=interval,
                outputsize=outputsize
            )

            if "error" in data:
                result[interval] = {
                    "error": data["error"]
                }
                continue

            result[interval] = data

        except Exception as e:

            result[interval] = {
                "error": str(e)
            }

    return result

def calculate_indicators(market_data):
    try:
        import pandas as pd

        values = market_data.get("values", [])

        if len(values) < 50:
            return {
                "error": "Data candle tidak cukup untuk menghitung indikator"
            }

        df = pd.DataFrame(values)

        # Pastikan urutan candle dari lama → terbaru
        df = df.iloc[::-1].reset_index(drop=True)

        df["close"] = pd.to_numeric(df["close"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])

        # =========================
        # EMA
        # =========================

        df["ema50"] = df["close"].ewm(
            span=50,
            adjust=False
        ).mean()

        df["ema200"] = df["close"].ewm(
            span=200,
            adjust=False
        ).mean()

        # =========================
        # RSI 14
        # =========================

        delta = df["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss

        df["rsi14"] = 100 - (100 / (1 + rs))

        # =========================
        # MACD
        # =========================

        ema12 = df["close"].ewm(
            span=12,
            adjust=False
        ).mean()

        ema26 = df["close"].ewm(
            span=26,
            adjust=False
        ).mean()

        df["macd"] = ema12 - ema26

        df["macd_signal"] = df["macd"].ewm(
            span=9,
            adjust=False
        ).mean()

        df["macd_histogram"] = (
            df["macd"] - df["macd_signal"]
        )

        # =========================
        # ATR 14
        # =========================

        previous_close = df["close"].shift(1)

        tr1 = df["high"] - df["low"]

        tr2 = (
            df["high"] - previous_close
        ).abs()

        tr3 = (
            df["low"] - previous_close
        ).abs()

        true_range = pd.concat(
            [tr1, tr2, tr3],
            axis=1
        ).max(axis=1)

        df["atr14"] = true_range.rolling(14).mean()

        # =========================
        # Support / Resistance
        # =========================

        support = df["low"].tail(20).min()

        resistance = df["high"].tail(20).max()

        # =========================
        # Data terbaru
        # =========================

        latest = df.iloc[-1]

        # =========================
        # Trend
        # =========================

        if latest["ema50"] > latest["ema200"]:
            trend = "BULLISH"
        elif latest["ema50"] < latest["ema200"]:
            trend = "BEARISH"
        else:
            trend = "SIDEWAYS"

        return {
            "price": float(latest["close"]),

            "ema50": round(float(latest["ema50"]), 5),
            "ema200": round(float(latest["ema200"]), 5),

            "rsi14": round(float(latest["rsi14"]), 2),

            "macd": round(float(latest["macd"]), 5),
            "macd_signal": round(
                float(latest["macd_signal"]), 5
            ),
            "macd_histogram": round(
                float(latest["macd_histogram"]), 5
            ),

            "atr14": round(float(latest["atr14"]), 5),

            "support": round(float(support), 5),
            "resistance": round(float(resistance), 5),

            "trend": trend
        }

    except Exception as e:

        return {
            "error": f"Indicator error: {str(e)}"
        }

def calculate_multi_timeframe_indicators(market_data):
    """
    Menghitung indikator untuk 5M, 15M dan 1H.
    """

    result = {}

    for timeframe, data in market_data.items():

        if "error" in data:
            result[timeframe] = {
                "error": data["error"]
            }
            continue

        indicators = calculate_indicators(data)

        result[timeframe] = indicators

    return result

MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")
DATASECTORS_API_KEY = os.getenv("DATASECTORS_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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

def analyze_with_gemini(pair, signal_data, price):
    try:

        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-flash-latest:generateContent"
        )

        params = {
            "key": GEMINI_API_KEY
        }

        prompt = f"""
Kamu adalah AI trading analyst profesional.

Analisa pair {pair} berdasarkan data market dan indikator yang diberikan.

PAIR:
{pair}

HARGA:
{price}

DATA MARKET DAN INDIKATOR:
{signal_data}

========================
MULTI TIMEFRAME
========================

5M:
Digunakan untuk melihat momentum dan kondisi entry.

15M:
Digunakan sebagai timeframe setup utama.

1H:
Digunakan sebagai trend utama market.

========================
INDIKATOR
========================

Gunakan:

- EMA 50
- EMA 200
- RSI 14
- MACD
- MACD Signal
- MACD Histogram
- ATR 14
- Support
- Resistance
- Trend

========================
ATURAN ANALISIS
========================

1. TIMEFRAME 1H adalah penentu trend utama.

2. TIMEFRAME 15M digunakan untuk melihat setup.

3. TIMEFRAME 5M digunakan untuk melihat momentum entry.

4. BUY hanya jika:
- Trend 1H bullish
- Setup 15M mendukung bullish
- Momentum 5M mendukung bullish
- MACD mendukung bullish
- RSI tidak terlalu overbought
- Harga tidak terlalu dekat resistance

5. SELL hanya jika:
- Trend 1H bearish
- Setup 15M mendukung bearish
- Momentum 5M mendukung bearish
- MACD mendukung bearish
- RSI tidak terlalu oversold
- Harga tidak terlalu dekat support

6. NO TRADE jika:
- Timeframe saling bertentangan
- Momentum tidak jelas
- Harga terlalu dekat support
- Harga terlalu dekat resistance
- RSI terlalu ekstrem
- MACD tidak mendukung
- Risiko false signal tinggi
- Data tidak cukup

Jangan memaksakan entry.

Confidence harus berdasarkan kekuatan bukti dari semua timeframe.

========================
OUTPUT
========================

Jawab HANYA JSON.

Format:

{{
    "decision": "BUY",
    "confidence": 0,
    "reason": "alasan singkat berdasarkan 1H, 15M dan 5M"
}}

Decision hanya boleh:

BUY
SELL
NO TRADE
"""

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        response = requests.post(
            url,
            params=params,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            return {
                "decision": "NO TRADE",
                "confidence": 0,
                "reason": f"Gemini API error: {response.text}"
            }

        result = response.json()

        ai_text = (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

        # Bersihkan markdown JSON
        ai_text = (
            ai_text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        import json

        ai_result = json.loads(ai_text)

        decision = ai_result.get(
            "decision",
            "NO TRADE"
        )

        confidence = ai_result.get(
            "confidence",
            0
        )

        reason = ai_result.get(
            "reason",
            ""
        )

        # Validasi keputusan
        if decision not in [
            "BUY",
            "SELL",
            "NO TRADE"
        ]:
            decision = "NO TRADE"

        return {
            "decision": decision,
            "confidence": confidence,
            "reason": reason
        }

    except Exception as e:

        return {
            "decision": "NO TRADE",
            "confidence": 0,
            "reason": f"Gemini AI error: {str(e)}"
        }

        
def process_signal(pair, signal_data):

    # =========================
    # 1. CEK NEWS PAUSE
    # =========================

    news = is_news_pause(pair)

    if news["pause"]:
        return {
            "decision": "PAUSE",
            "pair": pair,
            "reason": news["reason"],
            "currency": news["currency"],
            "volatility": news["volatility"],
            "event_time": news["event_time"]
        }

    # =========================
    # 2. FORMAT SYMBOL
    # =========================

    symbol = pair.upper().replace("/", "")

    if len(symbol) == 6:
        symbol = f"{symbol[:3]}/{symbol[3:]}"

    # =========================
    # 3. HARGA TERBARU
    # =========================

    price = get_forex_price(symbol)

    # =========================
    # 4. AMBIL MULTI TIMEFRAME
    # =========================

    market_data = get_multi_timeframe_data(symbol)

    # =========================
    # 5. HITUNG INDIKATOR
    # =========================

    indicators = calculate_multi_timeframe_indicators(
        market_data
    )

    # =========================
    # 6. CEK ERROR
    # =========================

    valid_timeframes = 0

    for timeframe, data in indicators.items():

        if "error" not in data:
            valid_timeframes += 1

    if valid_timeframes == 0:

        return {
            "decision": "NO TRADE",
            "confidence": 0,
            "reason": "Tidak ada data indikator yang berhasil",
            "pair": pair,
            "price": price
        }

    # =========================
    # 7. GABUNGKAN DATA
    # =========================

    signal_with_indicators = {

        "signal": signal_data,

        "timeframes": {

            "5M": indicators.get(
                "5min",
                {}
            ),

            "15M": indicators.get(
                "15min",
                {}
            ),

            "1H": indicators.get(
                "1h",
                {}
            )
        }
    }

    # =========================
    # 8. GEMINI
    # =========================

    ai = analyze_with_gemini(

        pair=pair,

        signal_data=signal_with_indicators,

        price=price
    )

    # =========================
    # 9. RETURN
    # =========================

    return {

        "decision": ai["decision"],

        "confidence": ai["confidence"],

        "reason": ai["reason"],

        "pair": pair,

        "price": price,

        "indicators": indicators
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

    else:

        text = f"""
🤖 CLAUDE AI SIGNAL

Pair: {pair}

Harga:
{price}

━━━━━━━━━━━━━━
DECISION: {result.get("decision")}
CONFIDENCE: {result.get("confidence")}%
━━━━━━━━━━━━━━

Reason:
{result.get("reason")}
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
        "status": "success",
        "decision": result.get("decision")
    }, 200

@app.route("/test-indicators", methods=["GET"])
def test_indicators():
    symbol = "XAU/USD"

    market_data = get_market_data(
        symbol=symbol,
        interval="15min",
        outputsize=100
    )

    indicators = calculate_indicators(market_data)

    return {
        "status": "success",
        "symbol": symbol,
        "indicators": indicators
        }


@app.route("/test-multi-timeframe", methods=["GET"])
def test_multi_timeframe():

    symbol = "XAU/USD"

    market_data = get_multi_timeframe_data(symbol)

    indicators = calculate_multi_timeframe_indicators(
        market_data
    )

    return jsonify({
        "status": "success",
        "symbol": symbol,
        "timeframes": indicators
    })

@app.route("/test-webhook/<pair>", methods=["GET"])
def test_webhook(pair):

    pair = pair.upper().replace("/", "")

    # Proses signal
    result = process_signal(
        pair,
        {
            "source": "MOBILE_TEST",
            "symbol": pair
        }
    )

    # Kirim hasil ke Telegram
    if result["decision"] == "PAUSE":

        text = f"""
🔴 NEWS PAUSE

Pair: {pair}

Status: PAUSE

News:
{result.get("reason")}

Currency:
{result.get("currency")}

Volatility:
{result.get("volatility")}

Event Time:
{result.get("event_time")}
"""

    else:

        text = f"""
🤖 CLAUDE AI SIGNAL

Pair: {pair}

Harga:
{result.get("price")}

━━━━━━━━━━━━━━
DECISION: {result.get("decision")}
CONFIDENCE: {result.get("confidence")}%
━━━━━━━━━━━━━━

Reason:
{result.get("reason")}
"""

    telegram_response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=15
    )

    return jsonify({
        "status": "success",
        "pair": pair,
        "decision": result.get("decision"),
        "confidence": result.get("confidence"),
        "reason": result.get("reason"),
        "telegram_status": telegram_response.status_code
    })
    
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

