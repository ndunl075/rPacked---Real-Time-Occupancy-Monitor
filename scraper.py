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

# --- Firebase Setup ---
cred_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
try:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://rpacked-fd51e.firebaseio.com'
    })
    db = firestore.client()
    print("Firebase connection established.")
except Exception as e:
    print(f"!!! Firebase initialization failed: {e}")
    print("Please make sure 'serviceAccountKey.json' is in the same folder as this script.")
    exit()

# --- Scraper Configuration ---
RPAC_URL = 'https://recsports.osu.edu/facilities/recreation-and-physical-activity-center-rpac'
CONTAINER_CLASS = 'c-meter'             # The main div for one location
NAME_CLASS = 'c-meter__title'           # The class for the location name
STATUS_CLASS = 'c-meter__status'        # The class for the "Open / Last updated..." text
COUNT_METER_SELECTOR = 'meter.c-meter__meter' # The <meter> tag that holds the count

def scrape_rpac_data():
    print("Attempting to scrape RPAC data using Selenium...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    driver = None
    try:
        print("Initializing Chrome browser driver...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        print(f"Loading page: {RPAC_URL} ...")
        driver.get(RPAC_URL)
        
        print(f"Waiting for JavaScript to load live data (class: '{CONTAINER_CLASS}')...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, CONTAINER_CLASS))
        )
        
        print("Live data found! Grabbing page source.")
        time.sleep(0.5) 
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        locations = soup.find_all('div', class_=CONTAINER_CLASS)
        
        if not locations:
            print("!!! SCRAPER FAILED: Found no elements with class 'c-meter'.")
            return

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
                else:
                    print(f"Debug: Found '{name}' but could not parse raw_text: '{raw_text}'. Skipping.")

            except Exception as e:
                print(f"Error parsing one location: {e}")

        if not scraped_locations:
            print("!!! SCRAPER FAILED: Parsed 0 locations successfully.")
            return

        # --- Save to Firebase ---
        doc_ref = db.collection('live_counts').document('RPAC')
        doc_ref.set({
            'locations': scraped_locations,
            'last_updated': firestore.SERVER_TIMESTAMP
        })
        
        print(f"\n--- SUCCESS ---")
        print(f"Successfully scraped and saved {len(scraped_locations)} locations to Firestore.")

    except TimeoutException:
        print("\n--- ERROR: TIMEOUT ---")
        print(f"The page loaded, but the element with class '{CONTAINER_CLASS}' did not appear after 15 seconds.")
        
    except Exception as e:
        print(f"\n--- ERROR: An unexpected error occurred ---")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            print("Shutting down browser.")
            driver.quit()

# --- Run the scraper ---
if __name__ == "__main__":
    scrape_rpac_data()

