import requests

# ----------------------------
# PUT YOUR CREDS HERE DIRECTLY
# ----------------------------
BOT_TOKEN = "8331147432:AAGSG4mI8d87sWEBsY0qtarAtwWbpa4viq0"
CHANNEL_ID = "-1003494200670"   # your flatxx channel ID


def send_to_channel(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHANNEL_ID,
        "text": msg
    }
    r = requests.post(url, data=data)
    print(r.json())


if __name__ == "__main__":
    send_to_channel("Hello from bot.py! 🎯")
