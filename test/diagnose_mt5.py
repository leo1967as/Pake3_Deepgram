import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd
import pytz

def diagnose():
    if not mt5.initialize():
        print("❌ initialize() failed, error code =", mt5.last_error())
        quit()

    print(f"✅ MT5 Package Version: {mt5.__version__}")
    print(f"✅ MT5 Terminal Build: {mt5.version()}")

    # Check for Calendar functions
    print("\n--- Checking Calendar API ---")
    try:
        # 1. Check Countries
        countries = mt5.calendar_country()
        if countries is None:
            print("⚠️ calendar_country() returned None.")
            print("   Error:", mt5.last_error())
        else:
            print(f"✅ calendar_country() working. Found {len(countries)} countries.")

        # 2. Check Value History (The one we likely need)
        now = datetime.now(pytz.timezone("UTC"))
        past = now - timedelta(days=2)
        future = now + timedelta(days=2)
        
        print(f"\n--- Testing calendar_value_history ({past.date()} to {future.date()}) ---")
        # Note: calling without country_code might invalid, let's try 'US' or None
        # Documentation usually says (country_code, from, to)
        
        try:
             # Try fetching all?
            res = mt5.calendar_value_history(None, past, future)
            if res:
                print(f"✅ calendar_value_history(None) returned {len(res)} records.")
            else:
                print(f"⚠️ calendar_value_history(None) returned None/Empty. Error: {mt5.last_error()}")
        except Exception as e:
            print(f"❌ calendar_value_history(None) Failed: {e}")

        # Try specific country keys if needed
        # ...

    except AttributeError:
        print("❌ AttributeError: Calendar functions missing from library.")
    except Exception as e:
        print(f"❌ Diagnostic Error: {e}")

    mt5.shutdown()

if __name__ == "__main__":
    diagnose()
