import requests
import time
import json
from datetime import datetime
from flat_api import FlattradeApi
from gen_token import GenerateFlattradeToken

# put your credentials here
USERID = "FZ19246"
JKEY = None

token_api = GenerateFlattradeToken()
api = FlattradeApi(USERID, JKEY)

SENSIBUL_FUTURE_EXPIRY = None   # SENSIBUL_FUTURE_EXPIRY = "NIFTY25OCTFUT"
OPTION_EXPIRY = None # "28OCT25"
TRADING_ACTIVE = False  # Fetch from Json Keeper check refresh_vwap_file_config()
FIRST_TRADE = True
ACTIVE_POSITION = None
NTFY = "fin22error"


def generate_token():
    global JKEY
    """
    Generate or refresh the Flattrade token.
    Returns the token string or None on failure.
    """
    token = token_api.gen_token()
    if token:
        JKEY = token
        print(JKEY)
        print(f"✅ Token generated successfully: {token[:20]}...")
        # Optional: Read full details from file if needed
        try:
            with open("token.json", "r") as f:
                token_data = json.load(f)
                # Use token_data if you need more (e.g., expiry)
        except FileNotFoundError:
            pass
        return token
    else:
        print("❌ Token generation failed.")
        return None

def refresh_token():
    global api, JKEY
    token = generate_token()
    if token:
        JKEY = token
        api = FlattradeApi(USERID, JKEY)  # Re-init API with new token
        print(f"🔄 Refreshed JKEY.")
        return True
    else:
        print("❌ Token refresh failed. Keeping previous token.")
        return False

def refresh_vwap_file_config():
    global SENSIBUL_FUTURE_EXPIRY, OPTION_EXPIRY, TRADING_ACTIVE
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
    TRADING_ACTIVE = data.get("TRADING_ACTIVE", False)
    return SENSIBUL_FUTURE_EXPIRY, OPTION_EXPIRY, TRADING_ACTIVE

def calculate_ema(prices, span):
    """
    Calculate Exponential Moving Average (EMA) manually and return the latest value.
    """
    if not prices:
        return 0.0
    alpha = 2 / (span + 1)
    ema = prices[0]  # Initialize with first price
    for price in prices[1:]:
        ema = alpha * price + (1 - alpha) * ema
    return round(ema, 2)

def fetch_vwap():
    if not SENSIBUL_FUTURE_EXPIRY:
        print("❗ SENSIBUL_FUTURE_EXPIRY not configured.")
        return None, None, None, None, None
    
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://oxide.sensibull.com/v1/compute/candles/{SENSIBUL_FUTURE_EXPIRY}"
    payload = {
        "from_date": today,
        "to_date": today,
        "interval": "1M",
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
            return None, None, None, None, None

        # Collect closes for EMA
        closes = [c["close"] for c in candles]

        # Calculate VWAP
        cum_pv, cum_vol = 0, 0
        for c in candles:
            tp = (c["high"] + c["low"] + c["close"]) / 3
            vol = c["volume"]
            cum_pv += tp * vol
            cum_vol += vol

        vwap = round(cum_pv / cum_vol, 2) if cum_vol else 0

        # Calculate latest EMA9 and EMA21 on closes
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)

        latest = candles[-1]
        return latest["ts"], latest["close"], vwap, ema9, ema21

    except Exception as e:
        print(f"❌ VWAP fetch error: {e}")
        return None, None, None, None, None
    
def fetch_nt_total():
    url = "https://webapi.niftytrader.in/webapi/option/option-chain-data?symbol=nifty&exchange=nse&expiryDate=&atmBelow=0&atmAbove=10"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "accept": "application/json"
    }

    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        totals = data["resultData"]["opTotals"]["total_calls_puts"]
        coi_pcr = totals["total_puts_change_oi"] - totals["total_calls_change_oi"]
        return coi_pcr

    except Exception as e:
        print(f"❌ NT fetch error: {e}")
        return None

def get_day_change():
    url = "https://webapi.niftytrader.in/webapi/symbol/today-spot-data?symbol=nifty&created_at="
    headers = {
        "User-Agent": "Mozilla/5.0",
        "accept": "application/json"
    }
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        return data["resultData"]["change_value"]
    except Exception as e:
        print(f"❌ Change fetch error: {e}")
        return None

def format_output(ts, ltp, vwap, coi_pcr, change_pts):
    time_str = datetime.fromisoformat(ts).strftime("%H:%M")
    vwap_flag = "🟢" if ltp > vwap else "🔴"
    coi_flag = "🟢" if coi_pcr > 0 else "🔴"
    coi_pcr_k = round(coi_pcr / 1000, 1)
    change_emoji = "🟢" if change_pts >= 0 else "🔴"

    print(f"🕒 {time_str} | {ltp} | {change_pts} {change_emoji} | {vwap}{vwap_flag} | {coi_pcr_k}K{coi_flag}")

    send_to_sheet(
        time_str=time_str,
        ltp=ltp,
        change_pts=change_pts,
        change_emoji=change_emoji,
        vwap_flag=vwap_flag,
        coi_flag=coi_flag,
        coi_pcr_k=coi_pcr_k
    )

def send_to_sheet(time_str, ltp, change_pts, change_emoji, vwap_flag, coi_flag, coi_pcr_k):
    # 1️⃣ Print formatted log
    # print(f"🕒 {time_str} | {ltp} | {change_pts} {change_emoji} | VWAP {vwap_flag} | {coi_pcr_k}K {coi_flag}")

    # 2️⃣ Prepare payload for Google Sheet
    payload = {
        "time": time_str,
        "ltp": ltp,
        "change_points": f"{change_emoji} {change_pts}",
        "data_a": vwap_flag,  # Already an emoji from API caller
        "data_b": coi_flag,   # Already an emoji from API caller
        "score": f"{coi_pcr_k}K"
    }

    try:
        sheetUrl = "https://script.google.com/macros/s/AKfycbwXgO0_pgXT92ptoMRRbv1fJMhvHwAMiBU4-iz6XAWt6cSO6hSHVlEjInu5UmCXd_DO/exec"
        response = requests.post(sheetUrl, json=payload)
        if response.status_code == 200:
            pass
            # print("✅ Data sent successfully")
        else:
            print(f"⚠️ Failed to send data. Status code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print("❌ Error sending data:", e)

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

    api.close_all_positions()
    api.cancel_all_pending_mis_orders()
    return True  # ready to trade

def execute_call_trade():
    global ACTIVE_POSITION, FIRST_TRADE

    # 🟡 Skip the first CALL trade only once
    if FIRST_TRADE and ACTIVE_POSITION != 'CALL':
        ACTIVE_POSITION = 'CALL'
        FIRST_TRADE = False
        print("⏸ Skipping first CALL trade (initial trigger).")
        return

    if not before_execution():
        return
    api.place_atm_order(OPTION_EXPIRY, "C", 75)
    ACTIVE_POSITION = 'CALL'
    print("🟢 Entered CALL position")

def execute_put_trade():
    global ACTIVE_POSITION, FIRST_TRADE

    # 🟡 Skip the first PUT trade only once
    if FIRST_TRADE and ACTIVE_POSITION != 'PUT':
        ACTIVE_POSITION = 'PUT'
        FIRST_TRADE = False
        print("⏸ Skipping first PUT trade (initial trigger).")
        return

    if not before_execution():
        return
    api.place_atm_order(OPTION_EXPIRY, "P", 75)
    ACTIVE_POSITION = 'PUT'
    print("🔴 Entered PUT position")

def close_all_position():
    global ACTIVE_POSITION
    api.close_all_positions()
    ACTIVE_POSITION = None
    print("❌ Closing all position")

def monitor_loop():
    ts, ltp, vwap, ema9, ema21 = fetch_vwap()
    coi_pcr = fetch_nt_total()
    change_pts = get_day_change()

    if ts is None or ltp is None or vwap is None or ema9 is None or ema21 is None or coi_pcr is None or change_pts is None:
        print(f"{datetime.now().strftime('%H:%M')} | Data fetch error, skipping…")
        return  # Skip without sleeping here; sleep is in main loop

    format_output(ts, ltp, vwap, coi_pcr, change_pts)
    # print(f"[{datetime.now().strftime('%H:%M:%S')}] LTP: {ltp}, VWAP: {vwap}, EMA9: {ema9}, EMA21: {ema21}, PCR: {coi_pcr}, Change: {change_pts}")
    
    global ACTIVE_POSITION
    
    # Long (Call) Logic
    if ACTIVE_POSITION == 'CALL':
        if ltp < vwap or ema9 < ema21:
            close_all_position()

    elif ACTIVE_POSITION is None:
        if ltp > vwap and ema9 > ema21:
            execute_call_trade()

    # Short (Put) Logic
    if ACTIVE_POSITION == 'PUT':
        if ltp > vwap or ema9 > ema21:
            close_all_position()

    elif ACTIVE_POSITION is None:
        if ltp < vwap and ema9 < ema21:
            execute_put_trade()

if __name__ == "__main__":
    # generate_token()
    ok = refresh_token()
    if not ok:
        print("Token unavailable. Exiting.")
        exit(1)

    pnl = api.calculate_realized_pnl()
    print("PNL:", pnl)

    refresh_vwap_file_config()
    if not SENSIBUL_FUTURE_EXPIRY:
        print("No SENSIBUL_FUTURE_EXPIRY configured. Exiting.")
        exit(1)

    print(f"Starting monitor with SENSIBUL_FUTURE_EXPIRY={SENSIBUL_FUTURE_EXPIRY}, TRADING_ACTIVE={TRADING_ACTIVE}")
    
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
