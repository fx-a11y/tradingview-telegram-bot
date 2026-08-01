from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = "8609166528:AAHDRNf1QQlwb5LWbU3L53apUEZV1buMWLY"
CHAT_ID = "1723200337"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    text = str(data)

    requests.post(
        f"https://api.telegram.org/bot{8609166528:AAHDRNf1QQlwb5LWbU3L53apUEZV1buMWLY}/sendMessage",
        json={
            "chat_id": 1723200337,
            "text": text
        }
    )

    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
