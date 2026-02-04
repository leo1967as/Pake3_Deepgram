import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config_manager import config
import os
import json

def test_config():
    print("🧪 Testing ConfigManager...")
    
    # 1. Check Load
    print(f"Current Config Keys: {list(config.config.keys())}")
    
    # 2. Check Default Value
    print(f"Enable Translation: {config.get('enable_translation')}")
    
    # 3. Modify & Save
    print("📝 Modifying 'max_tokens_translate' to 9999...")
    old_val = config.get("max_tokens_translate")
    config.set("max_tokens_translate", 9999)
    
    # 4. Reload to verify persistence
    # We simulate reload by reading file directly
    with open("data/config.json", "r") as f:
        data = json.load(f)
        saved_val = data.get("max_tokens_translate")
        print(f"💾 Saved Value on Disk: {saved_val}")
        
    if saved_val == 9999:
        print("✅ Config Persistence Passed!")
    else:
        print("❌ Config Persistence FAILED.")
        
    # Restore
    config.set("max_tokens_translate", old_val)
    print("🔄 Restored original value.")

if __name__ == "__main__":
    test_config()
