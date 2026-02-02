from curl_cffi import requests
from bs4 import BeautifulSoup

class ForexFactoryScraper:
    def __init__(self):
        # URL ของ Forex Factory Calendar
        self.url = "https://www.forexfactory.com/calendar?week=this"
        # ใช้การปลอม TLS fingerprint ให้เหมือน Chrome 110
        self.impersonation = "chrome110"

    def fetch_news(self, timeframe="today"):
        """
        Fetch news from Forex Factory.
        :param timeframe: 'today' or 'week'
        """
        if timeframe == "week":
            target_url = "https://www.forexfactory.com/calendar?week=this"
        else:
            target_url = "https://www.forexfactory.com/calendar?day=today"
            
        # print(f"   (DEBUG) Fetching from: {target_url}")

        try:
            response = requests.get(target_url, impersonate=self.impersonation, timeout=15)
            if response.status_code != 200:
                print(f"❌ Connection Failed: {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, "html.parser")
            table = soup.find("table", class_="calendar__table")
            
            if not table:
                print("❌ เข้าถึงเว็บได้ แต่ไม่พบตาราง (โครงสร้างเว็บอาจเปลี่ยน)")
                return []

            news_list = []
            rows = table.find_all("tr", class_="calendar__row")
            
            # Debug counters
            counts = {"High": 0, "Medium": 0, "Low": 0, "Non-Econ": 0}

            for row in rows:
                try:
                    # 1. ตรวจระดับความแรงของข่าว (Impact)
                    impact_span = row.find("span", class_="on")
                    
                    if not impact_span: 
                        # Try finding ANY span with class starting with 'icon--ff-impact'
                        potential_impact = row.select_one("span[class*='icon--ff-impact']")
                        if potential_impact:
                             impact_span = potential_impact
                        else:
                             continue # Skip if really no impact token found
                    
                    impact_class = impact_span.get("class", [])
                    impact = "Low"
                    if "icon--ff-impact-red" in impact_class:
                        impact = "High"
                    elif "icon--ff-impact-ora" in impact_class:
                        impact = "Medium"
                    elif "icon--ff-impact-yel" in impact_class:
                        impact = "Low"
                    elif "icon--ff-impact-gra" in impact_class:
                        impact = "Non-Econ"
                    else:
                        impact = "Unknown"

                    if impact in counts:
                        counts[impact] += 1

                    # 2. ดึงเวลา (Format: 9:30pm or Tentative)
                    time_cell = row.find("td", class_="calendar__time")
                    time_str = time_cell.text.strip() if time_cell else ""

                    # 3. ดึงชื่อสกุลเงิน
                    currency_cell = row.find("td", class_="calendar__currency")
                    currency = currency_cell.text.strip() if currency_cell else ""

                    # 4. ดึงชื่อข่าว
                    event_cell = row.find("td", class_="calendar__event")
                    title = event_cell.text.strip() if event_cell else ""

                    # 5. ดึงตัวเลข (Actual, Forecast, Previous)
                    actual_cell = row.find("td", class_="calendar__actual")
                    forecast_cell = row.find("td", class_="calendar__forecast")
                    previous_cell = row.find("td", class_="calendar__previous")

                    actual = actual_cell.text.strip() if actual_cell else ""
                    forecast = forecast_cell.text.strip() if forecast_cell else ""
                    previous = previous_cell.text.strip() if previous_cell else ""

                    news_item = {
                        "time": time_str,
                        "currency": currency,
                        "impact": impact,
                        "title": title,
                        "actual": actual,
                        "forecast": forecast,
                        "previous": previous
                    }
                    news_list.append(news_item)

                except Exception as e:
                    continue

            # print(f"   -> Stats: {counts}") 
            return news_list

        except Exception as e:
            print(f"⚠️ Error scraping: {e}")
            return []

# --- ทดสอบการใช้งาน ---
if __name__ == "__main__":
    scraper = ForexFactoryScraper()
    
    print("\n" + "="*50)
    print("⏳ [TODAY] กำลังดึงข่าวทั้งหมดวันนี้...")
    news_today = scraper.fetch_news(timeframe="today")
    
    if news_today:
        print(f"✅ พบข่าววันนี้ {len(news_today)} ข่าว:")
        # กรองเฉพาะ High Impact เพื่อแสดงผลตัวอย่าง
        high_impact = [n for n in news_today if n['impact'] == 'High']
        print(f"   🔴 ข่าวแดง: {len(high_impact)} ข่าว")
        for news in high_impact:
            print(f"   � {news['time']} | {news['currency']} | {news['title']}")
            
        print(f"   ⚪ ข่าวอื่นๆ: {len(news_today) - len(high_impact)} ข่าว")
    else:
        print("❌ ไม่พบข่าววันนี้")

    print("="*50 + "\n")