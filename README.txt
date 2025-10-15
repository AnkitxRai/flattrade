Strategy : Vwap + 9ema 21ema crossover

flat_vwap_api file consists vwap changes trigger, that needs to be run from 10 am to 3 pm by cronjob
whenever vwap will trigger it will execute call or put order which is inside flat_api file
we are using jsonkeeper to update global config because once we host it is on vps we do not want to update regularly
content inside jsonkeeper url
{
  "JKEY": "03919a08c4c676b8350d8e6d60b5f42cc342228aa891e3429a481c76fd94529b",
  "OPTION_EXPIRY": "28OCT25",
  "SENSIBUL_FUTURE_EXPIRY": "NIFTY25OCTFUT",
  "TRADING_ACTIVE": true
}

JKEY is the session key of flattrade
Option Expiry is the option expiry date we gonna trade in flattrade
sensibul expiry is for fetching vwap and ohlc of sensibul monthly nifty future
trading active is trigger if it is false then trading script will not execute


Imp files
4. Note : only 2 files are imp : flat_api and flat_vwap_api and gen_token 
5. Only run flat_vwap_api file it will import algo_flattrade file 
6. this is api based algo where you need to generate token
7. Web based folder required session Jkey which can be used from web login cookie Jkey


Setup 
1. pip3 install pyotp --break-system-packages
2. Replace password in gen_token file
3. update OPTION_EXPIRY and SENSIBUL_FUTURE_EXPIRY in jsonkeeper config file, check refresh_vwap_file_config()
4. you can control trading start/stop from jsonkeeper
5. Run flat_vwap_api