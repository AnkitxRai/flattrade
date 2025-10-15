from flat_api import FlattradeApi

# put your credentials here
USERID = "FZ19246"
JKEY = "779fd0c8bd37e48c33f4b7cf8aee0abf32103f19ffc2b1e34e2a3088d22e39ed"

api = FlattradeApi(USERID, JKEY)

# print("Test:", api.test())
# print(api.get_quote("NSE", "22"))
# print("order book", api.get_order_book())
# print("position", api.get_positions())
# print("atm option", api.get_atm_option("28OCT25"))
# print("cancel order", api.cancel_all_pending_mis_orders())
print("pnl", api.calculate_realized_pnl())
# print("atm order", api.place_atm_order("28OCT25", "P"))
# print("atm order", api.place_atm_order("28OCT25", "P", 75))
# print("closing position", api.close_all_positions())


# How to call generate token py 

# from gen_token import GenerateFlattradeToken
# token_api = GenerateFlattradeToken()
# token = token_api.gen_token()
