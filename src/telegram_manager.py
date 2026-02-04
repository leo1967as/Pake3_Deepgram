import json
import os
import httpx
import threading

TELEGRAM_CONFIG_PATH = os.path.join("data", "telegram_config.json")

DEFAULT_TG_CONFIG = {
    "bot_token": "",
    "channels": [
        # {"name": "Test Group", "chat_id": "123456789", "active": True}
    ],
    "templates": {
        "analysis_update": "🚨 <b>{sentiment} UPDATE</b>\nImpact: {impact}\n\n\"{summary}\"\n\n#Forex #Gold",
        "session_summary": "🌍 <b>BIG PICTURE UPDATE</b>\n\n<b>{title}</b>\n\n{bullets}\n\n🔮 <b>Strategy:</b> {strategy}",
        "manual_alert": "📢 <b>ADMIN ALERT</b>\n\n{message}"
    },
    "auto_post_hawk_dove": False,
    "auto_post_all": False,
    "auto_post_summary": True  # New config for Big Picture
}

class TelegramManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramManager, cls).__new__(cls)
            cls._instance.config = {}
            cls._instance.history = []  # Runtime log history
            cls._instance.load_config()
        return cls._instance

    def log_activity(self, msg_type, content):
        """Log activity for the dashboard"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.history.insert(0, {"time": timestamp, "type": msg_type, "msg": content})
        # Keep last 50 logs
        if len(self.history) > 50:
            self.history.pop()

    def load_config(self):
        if not os.path.exists("data"):
            os.makedirs("data")
            
        defaults = {
            "bot_token": "",
            "channels": [],
            "templates": {
                "analysis_update": "🚨 <b>{sentiment} UPDATE</b>\nImpact: {impact}\n\n\"{summary}\"\n\n#Forex #Gold",
                "session_summary": "🌍 <b>BIG PICTURE UPDATE</b>\n\n<b>{title}</b>\n\n{bullets}\n\n🔮 <b>Strategy:</b> {strategy}",
                "manual_alert": "📢 <b>ADMIN ALERT</b>\n\n{message}"
            },
            "auto_post_hawk_dove": False,
            "auto_post_all": False,
            "auto_post_summary": True
        }

        try:
            if os.path.exists(TELEGRAM_CONFIG_PATH):
                with open(TELEGRAM_CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    
                # Merge defaults (shallow merge for top level, specific check for templates)
                for key, val in defaults.items():
                    if key not in loaded:
                        loaded[key] = val
                    elif key == "templates":
                        # Ensure 'templates' key exists in loaded before merging sub-keys
                        if not isinstance(loaded.get("templates"), dict):
                            loaded["templates"] = {}
                        # Merge missing templates
                        for t_key, t_val in defaults["templates"].items():
                            if t_key not in loaded["templates"]:
                                loaded["templates"][t_key] = t_val
                                
                self.config = loaded
            else:
                self.config = defaults
                self.save_config()
        except Exception as e:
            print(f"⚠️ Failed to load TG config: {e}")
            self.config = defaults

    def save_config(self):
        try:
            with open(TELEGRAM_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"❌ Failed to save TG config: {e}")

    def add_channel(self, name, chat_id):
        self.config["channels"].append({"name": name, "chat_id": chat_id, "active": True})
        self.save_config()

    def remove_channel(self, chat_id):
        self.config["channels"] = [c for c in self.config["channels"] if c["chat_id"] != chat_id]
        self.save_config()

    def send_to_all(self, text):
        """Broadcasts message to all active channels in a separate thread."""
        threading.Thread(target=self._broadcast_thread, args=(text,), daemon=True).start()

    def _broadcast_thread(self, text):
        token = self.config.get("bot_token")
        if not token:
            print("⚠️ No Bot Token configured.")
            return

        for channel in self.config["channels"]:
            if channel.get("active"):
                self._send_one(token, channel["chat_id"], text)

    def _send_one(self, token, chat_id, text):
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            response = httpx.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"❌ TG Send Failed ({chat_id}): {response.text}")
                self.log_activity("ERROR", f"Failed to {chat_id}: {response.text}")
            else:
                print(f"✅ TG Sent to {chat_id}")
                # Log success (only once per broadcast to avoid spam in UI, logging here is per-chat)
                # Let's log 'Sent' in the UI logic instead or log here but maybe filtered
                pass 
        except Exception as e:
            print(f"❌ TG Network Error: {e}")
            self.log_activity("ERROR", f"Network Error: {e}")

    def get_recent_chats(self):
        """Fetch recent interactions to find Chat IDs."""
        token = self.config.get("bot_token")
        if not token:
            print("⚠️ No Bot Token to fetch updates.")
            return []

        url = f"https://api.telegram.org/bot{token}/getUpdates"
        try:
            print(f"🔍 Fetching updates from: {url}")
            resp = httpx.get(url, timeout=10)
            data = resp.json()
            
            if not data.get("ok"):
                print(f"❌ Telegram Error: {data.get('description')}")
                return []

            # Extract unique chats
            chats = {}
            for result in data.get("result", []):
                # Try to find 'chat' object in various update types
                chat = None
                if 'message' in result: chat = result['message'].get('chat')
                elif 'channel_post' in result: chat = result['channel_post'].get('chat')
                elif 'my_chat_member' in result: chat = result['my_chat_member'].get('chat')
                elif 'edited_message' in result: chat = result['edited_message'].get('chat')

                if chat and 'id' in chat:
                    chat_id = str(chat['id'])
                    # Prioritize readable names
                    title = chat.get('title') or chat.get('username') or chat.get('first_name') or "Unknown"
                    chat_type = chat.get('type', 'private')
                    
                    chats[chat_id] = {
                        "name": title,
                        "type": chat_type,
                        "id": chat_id
                    }
            
            found = list(chats.values())
            print(f"✅ Found {len(found)} active chats.")
            return found

        except Exception as e:
            print(f"❌ Error fetching updates: {e}")
            return []

tg_manager = TelegramManager()
