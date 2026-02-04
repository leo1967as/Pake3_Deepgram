import json
import os
import logging

CONFIG_PATH = os.path.join("data", "config.json")

DEFAULT_CONFIG = {
    # System Settings
    "deepgram_ws_url": "wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1",
    "target_media_url": "", # e.g. YouTube URL
    
    # AI Models
    "model_translate": "google/gemini-2.5-flash-lite",
    "model_analysis": "google/gemini-3-flash-preview",
    "model_summary": "google/gemini-3-flash-preview",
    
    # Limits & Parameters
    "max_tokens_translate": 1024,
    "max_tokens_analysis": 1024,
    "max_tokens_summary": 4096,
    
    # Feature Toggles (Cost Saving)
    "enable_translation": True,
    "enable_analysis": True,
}

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config = {}
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """Loads config from JSON file, creates default if missing."""
        if not os.path.exists("data"):
            os.makedirs("data")

        if not os.path.exists(CONFIG_PATH):
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()
            print(f"⚙️ Created default config at {CONFIG_PATH}")
        else:
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge defaults to ensure no missing keys
                    self.config = {**DEFAULT_CONFIG, **loaded}
            except Exception as e:
                print(f"⚠️ Failed to load config: {e}. Using defaults.")
                self.config = DEFAULT_CONFIG.copy()

    def save_config(self):
        """Saves current config to JSON."""
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            print("💾 Config saved.")
        except Exception as e:
            print(f"❌ Failed to save config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

# Global instance
config = ConfigManager()
