import sys
import os

# Add src to path so we can import the module
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src')
sys.path.append(src_path)

# Update import to use the new class name
from economic_detector import ForexFactoryScraper

def run_verification():
    print("🚀 Starting Economic News Detection Verification (ForexFactory)...")
    
    try:
        scraper = ForexFactoryScraper()
        print(f"✅ Scraper initialized. URL: {scraper.url}")
        
        print("\n📡 Fetching live data from Forex Factory...")
        # Enable verbose debug if the class supports it or we just read stdout
        # The class has internal print debugging now based on previous edits.
        
        red_news = scraper.fetch_news()
        
        print("\n---------------------------------------------------")
        if red_news:
            print(f"✅ FOUND {len(red_news)} HIGH IMPACT NEWS EVENTS:")
            for news in red_news:
                print(f"   🔴 [{news['time']}] {news['currency']} - {news['title']}")
                print(f"      Actual: {news['actual']} | Forecast: {news['forecast']}")
        else:
            print("⚠️ No High Impact news returned.")
            print("   (Check the debug output above for details on what was filtered out)")
            
        print("\n✅ Verification function finished.")
        
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_verification()
