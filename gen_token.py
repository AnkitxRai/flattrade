# Save this as gen_token_flattrade.py (fixed with missing imports and minor corrections)

import requests
import pyotp
import hashlib
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime

APIKEY = "ccf9bbaf3d1041aea02d475399eafe1c"
SECRETKEY = "2025.ff507a473d4949489270602bc1bdfc67b554dabea3450084"
TOTP_KEY = "35LY6332V5YJ36F5RATW36GJ7J446L43"
USERID = "FZ19246"
PASSWORD = "##"

class GenerateFlattradeToken:
    def __init__(self):
        print('🔐 Generating Flattrade Token...')

    def gen_token(self):
        # Headers
        headerJson = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://auth.flattrade.in/"
        }

        try:
            # Start session
            ses = requests.Session()

            # Step 1: Get Session ID
            print("🔐 Getting Session ID...")
            sesUrl = 'https://authapi.flattrade.in/auth/session'
            res_pin = ses.post(sesUrl, headers=headerJson)
            sid = res_pin.text
            print(f"✅ SID: {sid}")

            # Step 2: Generate TOTP
            totp = pyotp.TOTP(TOTP_KEY).now()

            # Step 3: Login
            print("🔑 Sending login payload...")
            url2 = 'https://authapi.flattrade.in/ftauth'
            passwordEncrypted = hashlib.sha256(PASSWORD.encode()).hexdigest()
            payload_login = {
                "UserName": USERID,
                "Password": passwordEncrypted,
                "PAN_DOB": totp,
                "App": "",
                "ClientID": "",
                "Key": "",
                "APIKey": APIKEY,
                "Sid": sid,
                "Override": "Y",
                "Source": "AUTHPAGE"
            }

            res2 = ses.post(url2, json=payload_login)
            login_json = res2.json()
            print(f"🔁 Login Response: {login_json}")

            # Step 4: Extract request_code from redirect URL
            parsed = urlparse(login_json['RedirectURL'])
            reqCode = parse_qs(parsed.query)['code'][0]
            print(f"📬 Request Code: {reqCode}")

            # Step 5: Generate API Secret (SHA256 hash)
            raw_string = APIKEY + reqCode + SECRETKEY
            hashed_secret = hashlib.sha256(raw_string.encode()).hexdigest()

            # Step 6: Get Token
            payload_token = {
                "api_key": APIKEY,
                "request_code": reqCode,
                "api_secret": hashed_secret
            }

            print("🎫 Getting token...")
            res3 = ses.post("https://authapi.flattrade.in/trade/apitoken", json=payload_token)
            token_response = res3.json()
            print(f"✅ Token Response: {token_response}")

            # Step 7: Save token to file
            with open("token.json", "w") as f:
                json.dump(token_response, f, indent=2)
            print("💾 Token saved to token.json")

            # Return the token for use in other code
            return token_response.get('token')  # Adjust key if different

        except Exception as e:
            print("❌ Error occurred:")
            print(e)
            return None

# Optional: Standalone run
if __name__ == "__main__":
    generator = GenerateFlattradeToken()
    token = generator.gen_token()
    if token:
        print(f"Generated Token: {token}")