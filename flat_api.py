import requests
import json

class FlattradeApi:
    def __init__(self, uid, jkey):
        self.uid = uid
        self.actid = uid
        self.jkey = jkey
        self.base_url = "https://piconnect.flattrade.in/PiConnectTP"
        
        self.routes = {
            "getquotes": "/GetQuotes",
            "optionchain": "/GetOptionChain",
            "orderbook": "/OrderBook",
            "positions": "/PositionBook",
            "placeorder": "/PlaceOrder",
            "modifyorder": "/ModifyOrder",
            "cancelorder": "/CancelOrder",
            "singleorder": "/SingleOrdHist",
            "test": "/Test"
        }

        self.headers = {
            "Content-Type": "application/json"
            # "Content-Type": "application/x-www-form-urlencoded"
        }

    def call_api(self, key: str, data: dict = None):
        if key not in self.routes:
            raise ValueError(f"Unknown API key: {key}")

        if data is None:
            data = {}
        
        # Ensure UID is included automatically
        if "uid" not in data:
            data["uid"] = self.uid

        # Ensure actid is included automatically
        if "actid" not in data:
            data["actid"] = self.actid

        payload = f'jData={json.dumps(data)}&jKey={self.jkey}'
        url = self.base_url + self.routes[key]
        try:
            resp = requests.post(url, data=payload, headers=self.headers, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def get_quote(self, exch: str, token: str):
        return self.call_api("getquotes", {"exch": exch, "token": token})
    
    def get_atm_spot(self, strike_step: int = 50):
        spot = self.get_quote("NSE", "26000")
        if spot.get("stat") != "Ok":
            raise Exception("Failed to fetch NIFTY spot:", spot)

        ltp = float(spot["lp"])
        atm_strike = round(ltp / strike_step) * strike_step
        return ltp, atm_strike

    def get_atm_option(self, expiry, isCallOrPut: str = "C"):
        try:
            ltp, atm = self.get_atm_spot()
        except Exception as e:
            print("❌ get_atm_option failed:", e)
            return None
        option_type = "C" if isCallOrPut.upper() == "C" else "P"
        option_symbol = f"NIFTY{expiry}{option_type}{atm}"
        return option_symbol

    def get_order_book(self):
        return self.call_api("orderbook")

    def get_single_order_detail(self, norenordno):
        if not norenordno:
            raise ValueError("norenordno is required.")

        norenordno = str(norenordno)
        data = {"norenordno": norenordno}

        order_details = self.call_api("singleorder", data)
        order_data = order_details[0]
        return order_data

    def cancel_order(self, norenordno: str):
        data = {
            "norenordno": norenordno
        }
        return self.call_api("cancelorder", data)

    def cancel_all_pending_mis_orders(self):
        orders = self.get_order_book() or []
        if isinstance(orders, dict) or not orders:
            print("ℹ️ No active orders found or API returned an invalid response.")
            return
        
        # New code with exception
        canceled_count = 0

        for order in orders:
            try:
                # Check if order is pending and type is MIS
                if order.get("status") == "OPEN" and order.get("s_prdt_ali") == "MIS":
                    order_no = order.get("norenordno")
                    if order_no:
                        resp = self.cancel_order(order_no)
                        if resp.get("stat") == "Ok":
                            canceled_count += 1
                            print(f"Canceled order {order_no} successfully.")
                        else:
                            print(f"Failed to cancel order {order_no}: {resp.get('emsg')}")
            except Exception as e:
                print(f"Exception while canceling order {order.get('norenordno')}: {str(e)}")
        
        print(f"Total canceled MIS orders: {canceled_count}")

    def get_positions(self):
        return self.call_api("positions")

    def close_all_positions(self):
        positions = self.get_positions() or []

        if isinstance(positions, dict) or not positions:
            print("⚠️ No valid positions found or API returned error.")
            return

        for pos in positions:
            if pos.get("stat") != "Ok":
                continue

            tsym = pos["tsym"]
            netqty = int(pos["netqty"])
            prd = pos.get("prd", "")

            # ✅ Only close intraday positions
            if prd != "I":
                continue

            if netqty > 0:  # LONG → SELL
                resp = self.place_order(
                    exch="NFO",
                    tsym=tsym,
                    qty=netqty,
                    prc=0,
                    prd="I",
                    trantype="S",
                    prctyp="MKT"
                )
                if resp is None or resp.get("stat") != "Ok":
                    print(f"[Error] Failed to close LONG {tsym}: {resp}")
                else:
                    print(f"Closing LONG {tsym}: {resp.get('norenordno', 'Reverse Order Placed')}")

            elif netqty < 0:  # SHORT → BUY
                resp = self.place_order(
                    exch="NFO",
                    tsym=tsym,
                    qty=abs(netqty),
                    prc=0,
                    prd="I",
                    trantype="B",
                    prctyp="MKT"
                )
                if resp is None or resp.get("stat") != "Ok":
                    print(f"[Error] Failed to close SHORT {tsym}: {resp}")
                else:
                    print(f"Closing SHORT {tsym}: {resp.get('norenordno', 'Reverse Order Placed')}")

    def calculate_realized_pnl(self):
        position_book = self.get_positions() or []

        if not position_book or isinstance(position_book, dict):
            print("⚠️ No valid positions found or API returned error. Returning PnL = 0.")
            return 0.0
        
        # print('POS', position_book)
        total_pnl = 0.0
        for pos in position_book:
            try:
                pnl_str = pos.get("rpnl", "0").replace(",", "")
                total_pnl += float(pnl_str)
            except (ValueError, TypeError):
                continue
        return total_pnl

    def send_telegram_message(self, msg, imp=True):
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

    def place_order(self, exch: str, tsym: str, qty: int, prc: float, prd: str, trantype: str, prctyp: str, ret: str = "DAY"):
        try:
            data = {
                "uid": self.uid,
                "actid": self.uid,
                "exch": exch,
                "tsym": tsym,
                "qty": str(qty),
                "prc": str(prc),
                "prd": prd,
                "trantype": trantype,
                "prctyp": prctyp,
                "ret": ret
            }

            response = self.call_api("placeorder", data)

            # If call_api returns an error dict (network issue)
            if response is None or "error" in response:
                print(f"[Network/API Error] Could not place order: {response.get('error', response)}")
                return None
            
            # Check API response for failure
            if response.get("stat") != "Ok":
                print(f"[Order Failed] {response.get('emsg', 'Unknown API error')}")
                return response
            
            # Success
            order = self.get_single_order_detail(response.get("norenordno"))
            tran_ball = "🟢" if order.get("trantype") == "B" else "🔴"

            pnl = self.calculate_realized_pnl()
            self.send_telegram_message(f"{tran_ball} | {order.get('tsym')} | {order.get('avgprc')} | {order.get('qty')} | {pnl}")
            
            print(f"[Order Placed]:{order.get('trantype')} {order.get('tsym')} Avg Price: {order.get('avgprc')} Qty: {order.get('qty')}")
            return response

        except Exception as e:
            print(f"[Exception] Failed to place order: {str(e)}")
            return None
    
    def place_atm_order(self, expiry, callOrPut: str = "C", qty=75, offset=2):
        option_strike = self.get_atm_option(expiry, callOrPut)  # should return e.g., "NIFTY28OCT25C55200"

        if not option_strike:
            print("Failed to get ATM option symbol")
            return
        
        placing_atm_order = self.place_order(
            exch="NFO",
            tsym=option_strike,
            qty=qty,
            prc=0,
            prd="I",
            trantype="B",
            prctyp="MKT",
            ret="DAY")
        
        if placing_atm_order and placing_atm_order.get("stat") == "Ok":
            print(f"✅ [ATM Order Placed] {option_strike}, Order No: {placing_atm_order.get('norenordno', 'N/A')}")
        else:
            print(f"❌ [ATM Order Failed] {option_strike}, Error: {placing_atm_order.get('emsg', 'Unknown error')}")

        return placing_atm_order