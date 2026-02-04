import re
import datetime

def parse_md_log(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The format seems to be blocks separated by newlines
    # Key anchor is the timestamp line: "Feb 4, 12:28 AM"
    
    # Regex to find blocks starting with date
    # Example: Feb 4, 12:28 AM
    parts = re.split(r'(Feb \d+, \d+:\d+ [AP]M)', content)
    
    total_cost = 0.0
    timestamps = []
    
    # The split result will be [preamble, date1, block1, date2, block2, ...]
    # We skip index 0
    
    count = 0
    
    for i in range(1, len(parts), 2):
        ts_str = parts[i].strip()
        block = parts[i+1]
        
        # Try to parse timestamp
        try:
            # Assuming current year 2026 based on context, but let's use 2026 as per user context
            dt = datetime.datetime.strptime(f"2026 {ts_str}", "%Y %b %d, %I:%M %p")
            timestamps.append(dt)
        except Exception as e:
            print(f"Error parsing date {ts_str}: {e}")
            continue

        # Look for cost in the block
        # Pattern seems to be: 
        # ...
        # 0.00152 (Cost)
        # $
        # ...
        
        # We can look for lines that look like small floats followed by a line with "$"
        # Or simply search for the floating point number before the "$" sign.
        
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        
        cost_found = False
        for j, line in enumerate(lines):
            if line == '$':
                # The line BEFORE '$' should be the cost
                if j > 0:
                    try:
                        cost_str = lines[j-1]
                        cost = float(cost_str)
                        total_cost += cost
                        cost_found = True
                        count += 1
                    except:
                        pass
                break
                
        if not cost_found:
            # Fallback: look for just a float that is small
            pass

    if not timestamps:
        print("No entries found.")
        return

    timestamps.sort()
    start_time = timestamps[0]
    end_time = timestamps[-1]
    
    # Duration might be zero if all in same minute, assume 1 min minimum or diff
    duration = (end_time - start_time).total_seconds() / 60
    if duration == 0:
        duration = 1.0 # fallback

    print(f"--- Analysis Report ---")
    print(f"Transactions: {count}")
    print(f"Total Cost: ${total_cost:.4f}")
    print(f"Start Time: {start_time}")
    print(f"End Time:   {end_time}")
    print(f"Duration:   {duration:.2f} minutes")
    
    if duration > 0:
        cost_per_hour = (total_cost / duration) * 60
        print(f"Hourly Burn Rate: ${cost_per_hour:.4f}")
        
        # Monthly 2h * 20d = 40h
        monthly = cost_per_hour * 40
        print(f"Monthly Projection (40h): ${monthly:.2f}")

if __name__ == "__main__":
    parse_md_log(r"d:\GoogleDriveSync\Work\2026\Pake3_Deepgram\openrouterlog.md")
