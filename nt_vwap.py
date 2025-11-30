import requests
import time
import json
from datetime import datetime
from multigen import generate_token
from nt_api import FlattradeApi

api = FlattradeApi("dummy", "dummy")
SENSIBUL_FUTURE_EXPIRY = None   # SENSIBUL_FUTURE_EXPIRY = "NIFTY25OCTFUT"
OPTION_EXPIRY = None # "28OCT25"
QTY = None
TRADING_ACTIVE = False  # Fetch from Json Keeper check refresh_vwap_file_config()
FIRST_TRADE = False
ACTIVE_POSITION = None

def refresh_vwap_file_config():
    global SENSIBUL_FUTURE_EXPIRY, OPTION_EXPIRY, QTY, TRADING_ACTIVE
    json_url = "https://www.jsonkeeper.com/b/EDZIR"

    try:
        resp = requests.get(json_url, timeout=10)
        data = resp.json()
        if not isinstance(data, dict):
            print(f"⚠️ Invalid JSON format from {json_url}: {data}")
            return None, None, None
    except Exception as e:
        print(f"❌ Config fetch failed: {e}")
        return None, None, None

    SENSIBUL_FUTURE_EXPIRY = data.get("SENSIBUL_FUTURE_EXPIRY")
    OPTION_EXPIRY = data.get("OPTION_EXPIRY")
    QTY = data.get("QTY")
    TRADING_ACTIVE = data.get("TRADING_ACTIVE", False)
    return SENSIBUL_FUTURE_EXPIRY, OPTION_EXPIRY, QTY, TRADING_ACTIVE

def ema(values, period):
    k = 2 / (period + 1)
    ema_prev = values[0]
    for v in values:
        ema_prev = (v - ema_prev) * k + ema_prev
        yield ema_prev

def get_nifty_macd():
    today = datetime.now().strftime("%Y-%m-%d")
    url = "https://oxide.sensibull.com/v1/compute/candles/NIFTY"
    payload = {
        "from_date": today,
        "to_date": today,
        "interval": "5M",
        "skip_last_ts": True
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        data = res.json()

        candles = data["payload"]["candles"]
        if not candles:
            return None, None

        close_prices = [c["close"] for c in candles]


        ema12 = list(ema(close_prices, 12))
        ema26 = list(ema(close_prices, 26))
        macd = ema12[-1] - ema26[-1]

        # Signal line = EMA(9) of MACD list
        macd_list = [a - b for a, b in zip(ema12, ema26)]
        signal = list(ema(macd_list, 9))[-1]
        return macd, signal

    except Exception as e:
        print("❌ MACD error:", e)
        return None, None

def get_day_change():
    url = "https://webapi.niftytrader.in/webapi/symbol/today-spot-data?symbol=NIFTY+50"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "accept": "application/json"
    }
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        index = data["resultData"]["last_trade_price"]
        change = data["resultData"]["change_value"]
        rounded = round(index / 50) * 50

        # print(index, change, rounded)
        return index, change, rounded
    except Exception as e:
        print(f"❌ Change fetch error: {e}")
        return None

def fetch_nt_total():
    url = "https://webapi.niftytrader.in/webapi/option/option-chain-data?symbol=nifty&exchange=nse&expiryDate=&atmBelow=2&atmAbove=2"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "accept": "application/json"
    }

    try:
        res = requests.get(url, headers=headers)
        return res.json()

    except Exception as e:
        print(f"❌ NT fetch error: {e}")
        return None

def send_telegram_message(msg, imp=True):
    BOT_TOKEN = "8331147432:AAGSG4mI8d87sWEBsY0qtarAtwWbpa4viq0" # zapy
    CHANNEL_ID = "-1003494200670"   # your flatxx channel ID
    CHANNEL_ID_IMP = "-1003448158591"   # your flatxx imp channel ID

    chat_id = CHANNEL_ID_IMP if imp else CHANNEL_ID

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": msg}
    try:
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print("❌ send_telegram_message error:", e)

def format_output(index, change, coi_pcr, cltp, cvwap, pltp, pvwap, macd, signal):
    time_str = datetime.now().strftime("%H:%M")
    index = int(index)
    cvwap_flag = "🟢" if cltp > cvwap else "🔴"
    pvwap_flag = "🟢" if pltp > pvwap else "🔴"
    macd_flag = "🟢" if macd > signal else "🔴"
    coi_flag = "🟢" if coi_pcr > 0 else "🔴"
    coi_pcr_k = int(coi_pcr / 1000)
    change_emoji = "🟢" if change >= 0 else "🔴"

    send_telegram_message(f"🕒{time_str} | {index} | {change} {change_emoji} | ᴄᴠ:{cvwap_flag} | ᴘᴠ:{pvwap_flag} | ᴍᴀ:{macd_flag} | {coi_pcr_k}K{coi_flag}", False)
    print(f"🕒{time_str} | {index} | {change} {change_emoji} | ᴄᴠ:{cvwap_flag} | ᴘᴠ:{pvwap_flag} | ᴍᴀ:{macd_flag} | {coi_pcr_k}K{coi_flag}")

def all_data():
    index, change, rounded = get_day_change()
    option_chain = fetch_nt_total()
    macd, signal = get_nifty_macd()

    if not option_chain:
        print("❌ No option chain data")
        return None

    try:
        # coi pcr
        totals = option_chain["resultData"]["opTotals"]["total_calls_puts"]
        coi_pcr = totals["total_puts_change_oi"] - totals["total_calls_change_oi"]

        data_list = option_chain["resultData"]["opDatas"]
        match = next((item for item in data_list if item["strike_price"] == rounded), None)

        if not match:
            print("⚠️ No matching strike:", rounded)
            return None

        cltp = match.get("calls_ltp")
        cvwap = match.get("calls_average_price")
        pltp = match.get("puts_ltp")
        pvwap = match.get("puts_average_price")

        format_output(index, change, coi_pcr, cltp, cvwap, pltp, pvwap, macd, signal)
        return (index, change, coi_pcr, cltp, cvwap, pltp, pvwap, macd, signal)

    except Exception as e:
        print("❌ Error searching data:", e)
        return None

def before_execution():
    try:
        pnl = api.calculate_realized_pnl()
        print(f"Realized PNL: {pnl}")
    except Exception as e:
        print(f"Error calculating PNL: {e}")
        return

    # ✅ Skip trade if loss exceeds threshold
    if pnl < -3000:
        print("⚠️ Loss exceeds -3000, skipping trade execution.")
        return False

    try:
        api.close_all_positions()
        api.cancel_all_pending_mis_orders()
    except Exception as e:
        print(f"Error closing/cancelling orders: {e}")
        return False

    return True

def execute_call_trade():
    global ACTIVE_POSITION, FIRST_TRADE, QTY

    # 🟡 Skip the first CALL trade only once
    if FIRST_TRADE and ACTIVE_POSITION != 'CALL':
        ACTIVE_POSITION = 'CALL'
        FIRST_TRADE = False
        print("⏸ Skipping first CALL trade (initial trigger).")
        return

    if not before_execution():
        return
    api.place_atm_order(OPTION_EXPIRY, "C", QTY)
    ACTIVE_POSITION = 'CALL'
    send_telegram_message("🟢 Entered Call position")
    print("🟢 Entered Call position")

def execute_put_trade():
    global ACTIVE_POSITION, FIRST_TRADE, QTY

    # 🟡 Skip the first PUT trade only once
    if FIRST_TRADE and ACTIVE_POSITION != 'PUT':
        ACTIVE_POSITION = 'PUT'
        FIRST_TRADE = False
        print("⏸ Skipping first PUT trade (initial trigger).")
        return

    if not before_execution():
        return
    api.place_atm_order(OPTION_EXPIRY, "P", QTY)
    ACTIVE_POSITION = 'PUT'
    send_telegram_message("🔴 Entered Put position")
    print("🔴 Entered Put position")

def close_all_position():
    global ACTIVE_POSITION
    api.close_all_positions()
    ACTIVE_POSITION = None
    print("❌ Closing all position")
    send_telegram_message("❌ Closing all position")

def monitor_loop():
    global ACTIVE_POSITION

    try:
        index, change, coi_pcr, cltp, cvwap, pltp, pvwap, macd, signal = all_data()
    except Exception as e:
        print("❌ all_data() failed:", e)
        return

    try:
        cltp = float(cltp) if cltp is not None else None
        cvwap = float(cvwap) if cvwap is not None else None
        pltp = float(pltp) if pltp is not None else None
        pvwap = float(pvwap) if pvwap is not None else None
        macd = float(macd) if macd is not None else None
        signal = float(signal) if signal is not None else None
    except Exception:
        print("❌ invalid numeric values")
        return
    
    # ----- close call position -----
    if ACTIVE_POSITION == "call":
        if (cltp is None or cvwap is None) or ((cltp < cvwap) or (pltp is not None and pltp > pvwap) or (macd is not None and macd < signal)):
            print("Closing CALL position")
            close_all_position()
        else:
            print("CALL active — no exit signal")
            return

    # ----- close put position -----
    elif ACTIVE_POSITION == "put":
        if (pltp is None or pvwap is None) or ((pltp < pvwap) or (cltp is not None and cltp > cvwap) or (macd is not None and macd > signal)):
            print("Closing PUT position")
            close_all_position()
        else:
            print("PUT active — no exit signal")
            return

    # ----- Entry condition -----
    if ACTIVE_POSITION is None:
        if cltp is not None and cvwap is not None and cltp > cvwap:
            print("Executing CALL trade")
            execute_call_trade()
            return

        if pltp is not None and pvwap is not None and pltp > pvwap:
            print("Executing PUT trade")
            execute_put_trade()
            return
    print("No entry / No action")

if __name__ == "__main__":
    # generate_token()

    execute_call_trade()

    while True:
        try:
            refresh_vwap_file_config()  # Refresh config every minute for runtime updates
            
            if not TRADING_ACTIVE:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Trading inactive. Sleeping for 1 minute...")
                time.sleep(60)
                continue

            try:
                monitor_loop()
            except Exception as e:
                print(f"❌ Monitor error: {e}")

            time.sleep(60)

        except KeyboardInterrupt:
            print("🛑 Monitor stopped by user.")
            break

        except Exception as e:
            print(f"🔥 FATAL loop crash: {e}")
            time.sleep(30)  # prevent instant restart loop if repeated crash