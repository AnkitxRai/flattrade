import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # Add src/ to path

from telegram.bot import send_to_channel  # Now relative to src/

send_to_channel("Hello from test.py! 🧪abc")