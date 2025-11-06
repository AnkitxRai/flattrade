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

CRUDE_OPTION_EXPIRY = None # "28OCT25"
CRUDE_FUTURE_TOKEN = None
CRUDE_TRADING_ACTIVE = False
FIRST_TRADE = True
ACTIVE_POSITION = None


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
    global CRUDE_OPTION_EXPIRY, CRUDE_FUTURE_TOKEN, CRUDE_TRADING_ACTIVE
    json_url = "https://www.jsonkeeper.com/b/EDZIR"

    try:
        resp = requests.get(json_url, timeout=10)
        data = resp.json()
        if not isinstance(data, dict):
            print(f"⚠️ Invalid JSON format from {json_url}: {data}")
            return None, None
    except Exception as e:
        print(f"❌ Config fetch failed: {e}")
        return None, None, None

    CRUDE_OPTION_EXPIRY = data.get("CRUDE_OPTION_EXPIRY")
    CRUDE_FUTURE_TOKEN = data.get("CRUDE_FUTURE_TOKEN")
    CRUDE_TRADING_ACTIVE = data.get("CRUDE_TRADING_ACTIVE", False)
    return CRUDE_OPTION_EXPIRY, CRUDE_FUTURE_TOKEN, CRUDE_TRADING_ACTIVE

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

def fetch_vwap_5paisa():
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://chartstt.5paisa.com/Chart/historical/M/d/{CRUDE_FUTURE_TOKEN}/1m?from={today}&end={today}"

    headers = {
        "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ii1FY0U2TlE0MFJtaUJRQUt6Zm4wYnFheXhZY2JXOXdaaURmZ28wQm52a3cifQ.eyJqdGkiOiJvY2gwVmx3dkpVZEtGTElsRXVoR2kiLCJpc3MiOiJodHRwczovL2lpZmwub25lbG9naW4uY29tL29pZGMvMiIsImlhdCI6MTc2MjM2NzQwNSwiZXhwIjoxNzYyNDEwNjA1LCJhdWQiOiI5YzZhMWU2MC1mYmVlLTAxMzgtNDg2NS0wNjgzMTlkNWZmNjIzODE4OCJ9.H7O70VVV86MSOxy-Te9ISKUnVdf0xQTYGBx33zzGSEjD7VGXVJ_-mK__ZIJkJEHwoXzZ4ULHKTcTE1v3yJHl4dxsOnsYH72nlKkbR7bAVDQuCZoqpNM0OuYwgw02EPl35_tv_sEM0_hzsqM1NSBaLGqBleKNhEky1S_nP5p20oN-UYN6ZgjFo4Y2t0wWcLVHrxpwoj3_F_WvXTUbviqWvxPnSgC4PP9qGqwyd2rPh-foJisJOV-sT8ILCDV1sQ4rWPgUIxZBmX05WOxwQS-_V_I9YWSRTg2Bduwq6bWmawrfGZAlV0JV2jhzxdh2TMYo6Th372Mm5f_qKhyuLpUlJQ",
        "Content-Type": "application/json",
        "Origin": "https://tradechart.5paisa.com",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        # extract candles (both formats supported)
        candles = []
        if "candles" in data:
            candles = data["candles"]
        elif "data" in data and "candles" in data["data"]:
            candles = data["data"]["candles"]

        if not candles:
            print("❗ No candle data returned.")
            return None, None, None, None, None

        # detect cumulative volume
        cumulative = all(candles[i][5] >= candles[i-1][5] for i in range(1, len(candles)))

        cum_pv = 0
        cum_vol = 0
        prev_vol = 0
        closes = []

        for c in candles:
            o, h, l, cl, v = c[1], c[2], c[3], c[4], c[5]
            closes.append(cl)

            # handle cumulative volume
            if cumulative:
                vol = v - prev_vol if prev_vol else v
                prev_vol = v
            else:
                vol = v

            tp = (h + l + cl) / 3
            cum_pv += tp * vol
            cum_vol += vol

        vwap = round(cum_pv / cum_vol, 2) if cum_vol else 0
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)

        latest = candles[-1]
        ts = latest[0]  # timestamp (epoch or ISO)
        ltp = latest[4]

        # print(f"✅ VWAP: {vwap}, EMA9: {ema9}, EMA21: {ema21}", ltp, ts)
        return ts, ltp, vwap, ema9, ema21

    except Exception as e:
        print(f"❌ VWAP fetch error: {e}")
        return None, None, None, None, None

def format_output(ts, ltp, vwap, ema9, ema21):
    time_str = datetime.fromisoformat(ts).strftime("%H:%M")
    vwap_flag = "🟢" if ltp > vwap else "🔴"

    print(f"🕒 {time_str} | {ltp} | {ema9} _ {ema21} | {vwap}{vwap_flag}")

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
    api.crude_place_atm_order(CRUDE_OPTION_EXPIRY, "C", 100)
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
    api.crude_place_atm_order(CRUDE_OPTION_EXPIRY, "P", 100)
    ACTIVE_POSITION = 'PUT'
    print("🔴 Entered PUT position")

def close_all_position():
    global ACTIVE_POSITION
    api.close_all_positions()
    ACTIVE_POSITION = None
    print("❌ Closing all position")

def monitor_loop():
    ts, ltp, vwap, ema9, ema21 = fetch_vwap_5paisa()

    if ts is None or ltp is None or vwap is None or ema9 is None or ema21 is None:
        print(f"{datetime.now().strftime('%H:%M')} | Data fetch error, skipping…")
        return  # Skip without sleeping here; sleep is in main loop

    format_output(ts, ltp, vwap, ema9, ema21)
    # print(f"[{datetime.now().strftime('%H:%M:%S')}] LTP: {ltp}, VWAP: {vwap}, EMA9: {ema9}, EMA21: {ema21}")
    
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
    if not CRUDE_OPTION_EXPIRY:
        print("No CRUDE_OPTION_EXPIRY configured. Exiting.")
        exit(1)

    print(f"Starting monitor with CRUDE_OPTION_EXPIRY={CRUDE_OPTION_EXPIRY}, CRUDE_TRADING_ACTIVE={CRUDE_TRADING_ACTIVE}")
    
    while True:
        try:
            refresh_vwap_file_config()  # Refresh config every minute for runtime updates
            
            if not CRUDE_TRADING_ACTIVE:
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
