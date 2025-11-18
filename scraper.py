import time
import re
import firebase_admin
from firebase_admin import credentials, firestore
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os
import sys

# --- Firebase Setup ---
cred_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
print(f"Looking for service account key at: {cred_path}")

if not os.path.exists(cred_path):
    print(f"!!! ERROR: serviceAccountKey.json not found at {cred_path}")
    sys.exit(1)

try:
    print("Initializing Firebase Admin SDK...")
    # Check if Firebase app is already initialized (can happen in some environments)
    try:
        app = firebase_admin.get_app()
        print("Firebase app already initialized, reusing existing app...")
        db = firestore.client()
    except ValueError:
        # App doesn't exist, initialize it
        print("Creating new Firebase app...")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://rpacked-fd51e.firebaseio.com'
        })
        db = firestore.client()
    print("✓ Firebase connection established.")
except Exception as e:
    print(f"!!! Firebase initialization failed: {e}")
    print("Please make sure 'serviceAccountKey.json' is in the same folder as this script.")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# --- Scraper Configuration ---
FACILITIES = {
    'RPAC': 'https://recsports.osu.edu/facilities/recreation-and-physical-activity-center-rpac',
    'JOS': 'https://recsports.osu.edu/fms/facilities/jos',
    'JON': 'https://recsports.osu.edu/fms/facilities/jon',
    'NRC': 'https://recsports.osu.edu/fms/facilities/nrc'
}

CONTAINER_CLASS = 'c-meter'             # The main div for one location
NAME_CLASS = 'c-meter__title'           # The class for the location name
STATUS_CLASS = 'c-meter__status'        # The class for the "Open / Last updated..." text
COUNT_METER_SELECTOR = 'meter.c-meter__meter' # The <meter> tag that holds the count

def scrape_facility_data(facility_name, facility_url, driver):
    """Scrape a single facility's capacity data."""
    print(f"\n{'=' * 60}")
    print(f"Scraping {facility_name}...")
    print(f"{'=' * 60}")
    print(f"Loading page: {facility_url} ...")
    
    try:
        driver.get(facility_url)
        print("✓ Page loaded.")
        
        print(f"Waiting for JavaScript to load live data (class: '{CONTAINER_CLASS}')...")
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, CONTAINER_CLASS))
            )
            print("✓ Live data found!")
        except TimeoutException:
            print(f"⚠️ WARNING: No capacity meters found on {facility_name} page. This facility may not have capacity tracking.")
            return None
        
        print("Grabbing page source...")
        time.sleep(0.5) 
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        locations = soup.find_all('div', class_=CONTAINER_CLASS)
        print(f"Found {len(locations)} location containers.")
        
        if not locations:
            print(f"⚠️ WARNING: No locations found on {facility_name} page. Skipping.")
            return None

        scraped_locations = []
        
        for location in locations:
            try:
                name_element = location.find('span', class_=NAME_CLASS)
                if not name_element:
                    print("Debug: Found container but no name_element. Skipping.")
                    continue
                name = name_element.text.strip()

                # --- NEW: Get Open/Closed Status ---
                status_element = location.find('span', class_=STATUS_CLASS)
                open_status = "Unknown" # Default
                if status_element:
                    status_text = status_element.text.strip().lower()
                    if status_text.startswith('open'):
                        open_status = "Open"
                    elif status_text.startswith('closed'):
                        open_status = "Closed"
                
                # --- Get Count ---
                meter_element = location.find('meter', class_='c-meter__meter')
                if not meter_element:
                    print(f"Debug: Found '{name}' but no meter element. Skipping.")
                    continue

                raw_text = meter_element.text.strip()
                match = re.search(r'(\d+)\s+out of\s+(\d+)', raw_text)
                
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    
                    scraped_locations.append({
                        'name': name,
                        'status': 'Count', # This means it has a count
                        'openStatus': open_status, # NEW: "Open" or "Closed"
                        'current': current,
                        'total': total,
                        'raw_text': raw_text
                    })
                    print(f"  ✓ Scraped: {name} - {current}/{total} ({open_status})")
                else:
                    print(f"Debug: Found '{name}' but could not parse raw_text: '{raw_text}'. Skipping.")

            except Exception as e:
                print(f"Error parsing one location: {e}")
                import traceback
                traceback.print_exc()

        if not scraped_locations:
            print(f"⚠️ WARNING: Parsed 0 locations successfully for {facility_name}. Skipping.")
            return None

        print(f"✓ Successfully parsed {len(scraped_locations)} locations from {facility_name}.")
        
        # --- Save to Firebase ---
        try:
            doc_ref = db.collection('live_counts').document(facility_name)
            doc_ref.set({
                'locations': scraped_locations,
                'last_updated': firestore.SERVER_TIMESTAMP,
                'facility_name': facility_name
            })
            print(f"✓ Wrote to live_counts/{facility_name}")
            return len(scraped_locations)
        except Exception as e:
            print(f"!!! ERROR writing to live_counts/{facility_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    except Exception as e:
        print(f"\n!!! ERROR scraping {facility_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function to scrape all facilities."""
    print("=" * 60)
    print("Starting OSU Rec Sports Capacity Scraper")
    print("=" * 60)
    print(f"Facilities to scrape: {', '.join(FACILITIES.keys())}")
    
    # Initialize browser once for all facilities
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    driver = None
    total_locations = 0
    successful_facilities = []
    
    try:
        print("\nInitializing Chrome browser driver...")
        # Try to find Chrome binary (works with both Chrome and Chromium)
        import shutil
        chrome_binary = None
        for binary_name in ['google-chrome', 'chromium-browser', 'chromium', 'chrome']:
            chrome_path = shutil.which(binary_name)
            if chrome_path:
                chrome_binary = chrome_path
                print(f"Found browser binary: {chrome_binary}")
                options.binary_location = chrome_binary
                break
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✓ Chrome driver initialized.")
        
        # Scrape each facility
        for facility_name, facility_url in FACILITIES.items():
            location_count = scrape_facility_data(facility_name, facility_url, driver)
            if location_count:
                total_locations += location_count
                successful_facilities.append(facility_name)
        
        # Update the last scraped timestamp in app_metadata
        try:
            last_scraped_ref = db.collection('app_metadata').document('last_scraped')
            last_scraped_ref.set({
                'timestamp': firestore.SERVER_TIMESTAMP,
                'total_locations_count': total_locations,
                'facilities_scraped': successful_facilities,
                'facilities_count': len(successful_facilities)
            })
            print(f"\n✓ Wrote to app_metadata/last_scraped")
        except Exception as e:
            print(f"\n!!! ERROR writing to app_metadata/last_scraped: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'=' * 60}")
        print("--- SUCCESS ---")
        print(f"Successfully scraped {len(successful_facilities)} facility/facilities: {', '.join(successful_facilities)}")
        print(f"Total locations scraped: {total_locations}")
        print(f"Updated last scraped timestamp in app_metadata.")
        print(f"{'=' * 60}")
        
        if not successful_facilities:
            print("\n!!! WARNING: No facilities were successfully scraped!")
            sys.exit(1)

    except Exception as e:
        print(f"\n{'=' * 60}")
        print("--- ERROR: An unexpected error occurred ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'=' * 60}")
        sys.exit(1)

    finally:
        if driver:
            print("\nShutting down browser...")
            driver.quit()
            print("✓ Browser closed.")

# --- Run the scraper ---
if __name__ == "__main__":
    try:
        main()
        print("\n✓ Scraper completed successfully!")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n!!! Scraper interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n!!! FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

