import requests
import pyotp
import hashlib
import json
from urllib.parse import urlparse, parse_qs

# -------------------------------------------------
# Load all accounts from accounts.json
# -------------------------------------------------
with open("accounts.json", "r") as f:
    ACCOUNTS = json.load(f)


class GenerateFlattradeToken:
    def __init__(self, acc):
        self.APIKEY = acc["APIKEY"]
        self.SECRETKEY = acc["SECRETKEY"]
        self.TOTP_KEY = acc["TOTP_KEY"]
        self.USERID = acc["USERID"]
        self.PASSWORD = acc["PASSWORD"]

    def gen_token(self):
        headerJson = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://auth.flattrade.in/"
        }

        try:
            ses = requests.Session()

            # Step 1: SID
            res_pin = ses.post("https://authapi.flattrade.in/auth/session", headers=headerJson)
            sid = res_pin.text

            # Step 2: TOTP
            totp = pyotp.TOTP(self.TOTP_KEY).now()

            # Step 3: Login
            passwordEncrypted = hashlib.sha256(self.PASSWORD.encode()).hexdigest()

            payload_login = {
                "UserName": self.USERID,
                "Password": passwordEncrypted,
                "PAN_DOB": totp,
                "App": "",
                "ClientID": "",
                "Key": "",
                "APIKey": self.APIKEY,
                "Sid": sid,
                "Override": "Y",
                "Source": "AUTHPAGE"
            }

            res2 = ses.post("https://authapi.flattrade.in/ftauth", json=payload_login)
            login_json = res2.json()

            parsed = urlparse(login_json['RedirectURL'])
            reqCode = parse_qs(parsed.query)['code'][0]

            # Step 4: Secret
            raw = self.APIKEY + reqCode + self.SECRETKEY
            hashed_secret = hashlib.sha256(raw.encode()).hexdigest()

            # Step 5: Token
            payload_token = {
                "api_key": self.APIKEY,
                "request_code": reqCode,
                "api_secret": hashed_secret
            }

            res3 = ses.post("https://authapi.flattrade.in/trade/apitoken", json=payload_token)
            token_response = res3.json()

            return token_response.get("token")  # return only token

        except Exception as e:
            print(f"Error for {self.USERID}:", e)
            return None


# -------------------------------------------------
# MAIN LOOP — update accounts.json
# -------------------------------------------------

def generate_token():
    for acc in ACCOUNTS:
        if not acc.get("STATUS", False):   # <-- skip false status
            print(f"⏭ Skipping {acc['USERID']} (STATUS = false)")
            continue
        
        print(f"\n🔐 Generating token for {acc['USERID']} ...")
        gen = GenerateFlattradeToken(acc)

        token = gen.gen_token()

        if token:
            print(f"✔ Token generated for {acc['USERID']}")
            acc["TOKEN"] = token        # <-- save token IN SAME OBJECT
        else:
            print(f"❌ Failed for {acc['USERID']}")
            acc["TOKEN"] = None


    # -------------------------------------------------
    # Save updated accounts back to accounts.json
    # -------------------------------------------------
    with open("accounts.json", "w") as f:
        json.dump(ACCOUNTS, f, indent=2)

    print("\n💾 All tokens saved back into accounts.json")
