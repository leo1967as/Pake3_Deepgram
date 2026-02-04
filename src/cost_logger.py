import csv
import os
import datetime

# Log file will be saved in data/cost_log_detailed.csv
# We assume the CWD is the project root
LOG_DIR = "data"
LOG_FILE = os.path.join(LOG_DIR, "cost_log_detailed.csv")

def init_log():
    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Type", "Model", "PromptTokens", "CompletionTokens", "TotalTokens", "Cost", "BatchNum"])
            print(f"✅ Created cost log at: {LOG_FILE}")
    except Exception as e:
        print(f"⚠️ Failed to init cost log: {e}")

def log_api_cost(event_type, model, usage, cost, batch_num="-"):
    try:
        if not os.path.exists(LOG_FILE):
            init_log()
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        p_tok = usage.get("prompt_tokens", 0)
        c_tok = usage.get("completion_tokens", 0)
        t_tok = usage.get("total_tokens", 0)
        
        # Ensure cost is a float
        try:
            cost_val = float(cost)
        except:
            cost_val = 0.0

        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, event_type, model, p_tok, c_tok, t_tok, f"{cost_val:.6f}", batch_num])
            
    except Exception as e:
        print(f"⚠️ Failed to write to cost log: {e}")
