import csv
from datetime import datetime, timedelta

def parse_time(t_str):
    # Format appears to be MM:SS.s
    # We will treat them as minutes and seconds relative to an arbitrary hour
    # We need to handle hour rollovers manually based on the sequence
    try:
        parts = t_str.split(':')
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes, seconds
    except:
        return None, None

def calculate_duration(times):
    # Times are in reverse chronological order (newest first)
    # We need to detect hour rollovers (e.g., 00:xx after 59:xx)
    
    # Sort chronologically (oldest first)
    times = sorted(times, key=lambda x: x['original_index'], reverse=True)
    
    if not times:
        return 0

    started = times[0]
    ended = times[-1]
    
    total_minutes = 0
    last_min = times[0]['min']
    
    # Simple duration estimation:
    # If the log is continuous, just converting to timeline
    
    # Let's just assume standard minute progression
    # If minute jumps from 59 to 0, add 60 to the counter
    
    current_hour_offset = 0
    start_timestamp = times[0]['min'] + times[0]['sec']/60
    
    # We calculate relative to start
    timestamps = []
    
    previous_min = times[0]['min']
    
    for t in times:
        m = t['min']
        s = t['sec']
        
        # Detect rollover (e.g. 59 -> 00)
        # Since we sorted chronologically, finding 59 then 00 means new hour
        # But wait, raw data might be reverse chronological.
        # Let's trace gaps.
        
        if m < previous_min and (previous_min - m) > 30:
             # e.g. prev=59, curr=0. Rollover
             current_hour_offset += 60
        
        previous_min = m
        timestamp = current_hour_offset + m + s/60
        timestamps.append(timestamp)

    duration_minutes = timestamps[-1] - timestamps[0]
    return duration_minutes

def analyze(file_path):
    total_cost = 0.0
    valid_entries = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        for i, row in enumerate(rows):
            if not row['cost_total']:
                continue
                
            try:
                cost = float(row['cost_total'])
                total_cost += cost
                
                t_str = row['created_at']
                m, s = parse_time(t_str)
                
                if m is not None:
                    valid_entries.append({
                        'original_index': i,
                        'min': m,
                        'sec': s,
                        'cost': cost
                    })
            except Exception as e:
                pass

    duration_mins = calculate_duration(valid_entries)
    
    print(f"Total Cost in Log: ${total_cost:.4f}")
    print(f"Estimated Duration: {duration_mins:.2f} minutes")
    
    if duration_mins > 0:
        cost_per_hour = (total_cost / duration_mins) * 60
        print(f"Average Cost per Hour: ${cost_per_hour:.4f}")
        
        # Monthly Projection (2h/day * 20 days)
        monthly_cost = cost_per_hour * 2 * 20
        print(f"Monthly Projection (2h * 20d): ${monthly_cost:.2f}")
    else:
        print("Could not calculate duration.")

if __name__ == "__main__":
    analyze("d:\\GoogleDriveSync\\Work\\2026\\Pake3_Deepgram\\openrouter_activity_2026-02-03.csv")
