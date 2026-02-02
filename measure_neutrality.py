"""
วัด % "ทรงตัว" จากการประชุมเฟดจริง
รันหลังจากแก้ไขระบบแล้ว
"""

import json
from pathlib import Path
import sys

def measure_neutrality(transcript_file: str):
    path = Path(transcript_file)
    if not path.exists():
        print(f"❌ File not found: {transcript_file}")
        return False
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    batches = data.get("batches", [])
    total = len(batches)
    neutral = 0
    
    for batch in batches:
        sentiment = batch.get("sentiment", "").upper()
        if "NEUTRAL" in sentiment or "ทรงตัว" in str(batch):
            neutral += 1
    
    neutral_pct = (neutral / total * 100) if total > 0 else 100
    
    print(f"📊 ผลการวัดจาก {path.name}")
    print(f"   ทั้งหมด: {total} batches")
    print(f"   ทรงตัว: {neutral} batches ({neutral_pct:.1f}%)")
    
    if neutral_pct <= 30:
        print(f"✅ ผ่านเกณฑ์: ทรงตัว ≤30%")
        return True
    else:
        print(f"❌ ยังไม่ผ่าน: ทรงตัว >30% (ต้องปรับปรุงเพิ่ม)")
        # Show some examples of Neutral to help debug
        print("\nตัวอย่างที่ถูกระบุว่า Neutral:")
        count = 0
        for batch in batches:
            sentiment = batch.get("sentiment", "").upper()
            if "NEUTRAL" in sentiment and count < 3:
                print(f"- Batch #{batch.get('batch_num')}: {batch.get('summary')}")
                count += 1
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python measure_neutrality.py <path_to_transcript_json>")
        print("Example: python measure_neutrality.py transcripts/last_meeting.json")
        # Try to find a recent file in transcripts folder
        if Path("transcripts").exists():
            files = list(Path("transcripts").glob("*.json"))
            if files:
                latest_file = max(files, key=os.path.getctime)
                print(f"\nRunning with latest file: {latest_file}")
                measure_neutrality(str(latest_file))
            else:
                sys.exit(1)
        else:
            sys.exit(1)
    else:
        measure_neutrality(sys.argv[1])
