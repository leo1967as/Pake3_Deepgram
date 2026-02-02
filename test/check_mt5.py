import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"Initialize failed, error code = {mt5.last_error()}")
    quit()

print("MetaTrader5 Package Version:", mt5.__version__)
print("\nAvailable functions in mt5:")
for func in dir(mt5):
    if "calendar" in func.lower():
        print(f" - {func}")

mt5.shutdown()
