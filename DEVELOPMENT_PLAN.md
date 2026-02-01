# 🚀 แผนพัฒนา Pake Live Analyzer

> สร้างเมื่อ: 1 กุมภาพันธ์ 2026  
> สถานะ: รอดำเนินการ

---

## 📊 สรุปสถานะปัจจุบัน

| ส่วน | สถานะ | หมายเหตุ |
|------|-------|----------|
| เวลาในคลิป | ✅ ถูกต้อง | ใช้ `segment["start"]` อยู่แล้ว |
| API URL | ✅ ถูกต้อง | ไม่มีช่องว่างท้าย |
| Prompt วิเคราะห์ | ⚠️ ต้องปรับ | วิเคราะห์ "ทรงตัว" มากเกินไป |
| Error Handling | ⚠️ ต้องเพิ่ม | ไม่มี retry mechanism |

---

## 🎯 งานที่ต้องทำ (จัดลำดับความสำคัญ)

### 1. ✅ ปรับปรุง Prompt วิเคราะห์การเงิน (สำคัญมาก)

**ไฟล์**: `pake_gui.py` → `AnalysisWorker.run()`  
**บรรทัด**: ~225-241

**Prompt ใหม่**:
```python
prompt = f"""คุณคือนักวิเคราะห์การเงินมืออาชีพ วิเคราะห์บทสนทนาต่อไปนี้อย่างเด็ดขาด:

กฎข้อบังคับ:
1. ⚠️ ห้ามใช้ "ทรงตัว" เว้นแต่เนื้อหาเป็นเชิงบริหารล้วนๆ (เช่น "ประชุมเสร็จแล้ว")
2. หากมีคำเหล่านี้ → ต้องกำหนดทิศทางชัดเจน:
   - HAWKISH: interest rates, inflation, tightening, restrictive policy, tariffs
   - DOVISH: rate cut, easing, stimulus, recession concerns, slowdown
3. วิเคราะห์ตลาดต้องมีเหตุผลสั้นกระชับ (ไม่เกิน 8 คำ)
4. หากผู้พูดแสดงความกังวลเรื่องเศรษฐกิจ → DOVISH
5. หากผู้พูดแสดงความมั่นใจ/เข้มงวด → HAWKISH

บทสนทนา:
{self.text}

ตอบเป็น JSON เท่านั้น:
{{
    "summary": "สรุป 1-2 ประโยค",
    "prediction": "คาดการณ์ 1 ประโยค",
    "sentiment": "HAWKISH|DOVISH|NEUTRAL",
    "gold": "ขึ้น/ลง: เหตุผลสั้น",
    "forex": "แข็ง/อ่อน: เหตุผลสั้น",
    "stock": "ขึ้น/ลง: หมวดหุ้นที่ได้รับผลกระทบ"
}}"""
```

---

### 2. ✅ เพิ่ม Retry Logic สำหรับ API Calls

**ไฟล์**: `pake_gui.py`  
**ส่วนที่ต้องเพิ่ม**: `TranslateWorker.run()` และ `AnalysisWorker.run()`

**โค้ดใหม่**:
```python
import time

MAX_RETRIES = 2

def run(self):
    for attempt in range(MAX_RETRIES + 1):
        try:
            # ... existing API call code ...
            return  # สำเร็จ → ออกจากลูป
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"❌ API failed after {MAX_RETRIES+1} attempts: {e}")
                self.finished.emit({"error": str(e), "batch_num": self.batch_num})
            else:
                wait_time = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                print(f"⚠️ Retry {attempt+1}/{MAX_RETRIES} in {wait_time}s...")
                time.sleep(wait_time)
```

---

### 3. 🔄 ปรับปรุง Speaker Context (Optional)

**ไฟล์**: `pake_live.py` → `add_to_batch()`

เพิ่มบริบทผู้พูดในแต่ละ batch:
```python
def add_to_batch(segment: dict):
    # ... existing code ...
    
    # เพิ่ม speaker context
    speaker = segment["speaker"]
    speaker_history = [s["text"] for s in session_data["segments"] 
                       if s["speaker"] == speaker][-3:]
    segment["speaker_context"] = " | ".join(speaker_history)
```

---

## 📁 โครงสร้างไฟล์

```
Pake3_Deepgram/
├── pake_deepgram.py    # Batch transcription (ไม่ต้องแก้)
├── pake_live.py        # Real-time transcription + GUI broadcast
├── pake_gui.py         # GUI + AI Analysis ← แก้ไขหลักที่นี่
├── .env                # API Keys
├── .gitignore          # ✅ สร้างแล้ว
└── transcripts/        # Output folder
```

---

## 🔧 คำสั่งรัน

```batch
:: Terminal 1: รัน GUI ก่อน
python pake_gui.py

:: Terminal 2: รัน Transcription (รอ GUI พร้อมก่อน)
python pake_live.py
```

---

## ✅ Checklist

- [ ] ปรับ Prompt ใน `AnalysisWorker` ให้วิเคราะห์เด็ดขาด
- [ ] เพิ่ม retry logic ใน `TranslateWorker`
- [ ] เพิ่ม retry logic ใน `AnalysisWorker`
- [ ] (Optional) เพิ่ม speaker context ใน `pake_live.py`
- [ ] ทดสอบกับ YouTube Live จริง

---

## 📈 ผลลัพธ์ที่คาดหวัง

| ตัวชี้วัด | ก่อนปรับ | หลังปรับ |
|----------|----------|----------|
| สัดส่วน "ทรงตัว" | ~90% | ≤30% |
| API Stability | ~70% | ≥95% (มี retry) |
| วิเคราะห์ตรงประเด็น | ต่ำ | สูงขึ้น |

---

> 💡 **หมายเหตุ**: ไม่ต้องใช้ N8N Webhook — ระบบส่งข้อมูลผ่าน TCP Socket (localhost:8765) อยู่แล้ว
