import os
import pickle
import random
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ==========================================================
# CONFIGURATION
# ==========================================================
SITE_URL = "https://writer.writersadmin.com/orders/available"

PROFILE_BASE_DIR = os.path.expanduser(r"~\selenium_bid_bot_profiles")
PROFILE_DIRS = [
    os.path.join(PROFILE_BASE_DIR, "Paul"),
    os.path.join(PROFILE_BASE_DIR, "Wamboo")
]

PROFILE_PATH = random.choice(PROFILE_DIRS)
COOKIES_FILE = os.path.join(PROFILE_PATH, "cookies.pkl")

CHECK_INTERVAL = (30, 60)  # seconds
AUTO_BID = True
MAX_RETRIES = 1
INACTIVITY_LIMIT = 120  # seconds of no new orders before switching profile

MESSAGES_PAUL = [
    "Hi! I’m excited about this task and confident I can provide a well-structured, thoroughly researched, and plagiarism and AI free work.",
    "Hello! I’ve successfully completed similar tasks before and would love to deliver top-quality work for you within your deadline.",
    "Greetings! I approach every order with professionalism and dedication, ensuring clarity, accuracy, and originality throughout.",
    "Hi there! I specialize in delivering clear, concise, and properly formatted work that exceed client expectations.",
    "Good day! I have vast experience handling similar topics and guarantee excellent communication and timely submission of plagiarism and AI-free work.",
    "Hello! I take pride in crafting detailed and accurate work that’s 100% original and done from scratch by myself. No AI involvement.",
    "Hi! I’d be honored to work on this task. Expect high-quality content that’s free from plagiarism or AI.",
    "Hello there! My skills align perfectly with this assignment. I’ll ensure prompt delively of plagiarism and AI-free work.",
    "Hey! I always tailor my work to the client’s requirements while ensuring proper analysis whenever required.",
    "Hi! I can confidently handle this, guaranteeing a polished, well-formatted, and insightful submission that meets all standards."
]

MESSAGES_WAMBOO = [
    "Hi! I’m very interested in working on this order. I have strong experience in similar tasks and always ensure timely delivery with well-researched, high-quality content. Kindly consider my bid.",
    "Hello! I’d love the opportunity to handle this. I have a solid background in this, and I make sure all my work is 100% original, polished, free of AI, and aligned with the given instructions.",
    "Greetings! I’m confident in my ability to deliver this project on time and to your expectations. I value clarity, structure, and originality in every assignment I handle.",
    "Hi there! I’d be glad to take on this task. My approach combines thorough research with clear, engaging presentation. Expect professional AI-free and plagiarism-free work.",
    "Hi, I’m enthusiastic about starting this order and confident in my ability to provide content that meets high standards. I ensure all my work is 100% original, AI-free, thoughtfully crafted. I appreciate your trust!",
    "Hello! I’m well-versed in this subject and confident in delivering a properly formatted, error-free, and original output. Quality, communication, and deadlines are always my top priorities.",
    "Hey there! I’ve successfully handled similar assignments before. I guarantee high-quality work, deep analysis to ensure your satisfaction and success.",
    "Good day! I take pride in producing detailed, well-organized, plagiarism-free, and AI-free work. I always tailor each project to match client needs and academic requirements perfectly.",
    "Hi! I’d love to assist with this order. My work is 100% authentic, well-structured, and thoroughly checked before submission. You can count on me for reliability and excellence.",
    "Hello! I’m confident my experience and attention to detail makes me a great fit for this project. I’ll provide an insightful, original, and properly formatted submission right on time."
]

if "Wamboo" in PROFILE_PATH:
    MESSAGES = MESSAGES_WAMBOO
    PROFILE_NAME = "Wamboo"
else:
    MESSAGES = MESSAGES_PAUL
    PROFILE_NAME = "Paul"

print(f"👤 Using profile: {PROFILE_NAME}")
print(f"💬 Loaded {len(MESSAGES)} messages for this session.")

# ==========================================================
# UTILITIES
# ==========================================================
def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{stamp}] {msg}"
    print(entry)
    os.makedirs(PROFILE_PATH, exist_ok=True)
    try:
        with open(os.path.join(PROFILE_PATH, "activity.log"), "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as e:
        print(f"!! Failed to write to log file: {e}")

def make_driver(headless=True):
    os.makedirs(PROFILE_PATH, exist_ok=True)
    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={PROFILE_PATH}")
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-pipe")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")
    service = Service()
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        return driver
    except WebDriverException as e:
        print("\n!! CRITICAL DRIVER ERROR: CHROME FAILED TO LAUNCH !!")
        print(f"Details: {e}")
        return None
    except Exception as e:
        print(f"\n!! UNEXPECTED DRIVER ERROR: {e} !!")
        return None

def save_cookies(driver):
    try:
        pickle.dump(driver.get_cookies(), open(COOKIES_FILE, "wb"))
        log("✅ Cookies saved.")
    except Exception as e:
        log(f"⚠️ Error saving cookies: {e}")

def load_cookies(driver):
    if os.path.exists(COOKIES_FILE):
        try:
            cookies = pickle.load(open(COOKIES_FILE, "rb"))
            driver.get(SITE_URL.split("/orders")[0])
            for cookie in cookies:
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    cookie['sameSite'] = 'Lax'
                driver.add_cookie(cookie)
            log("✅ Loaded cookies from file.")
            return True
        except Exception as e:
            log(f"⚠️ Failed to load cookies: {e}")
    return False

def ensure_login(driver):
    driver.get(SITE_URL)
    time.sleep(5)
    if "login" in driver.current_url.lower():
        log("⚠️ Not logged in. Launching visible browser for manual login...")
        driver.quit()
        manual_driver = make_driver(headless=False)
        if manual_driver is None:
            log("❌ Failed to launch manual browser for login.")
            return None
        manual_driver.get(SITE_URL)
        log("...Waiting for you to log in. This window will close after login...")
        try:
            WebDriverWait(manual_driver, 300).until(lambda d: "available" in d.current_url.lower())
            log("✅ Login successful.")
            save_cookies(manual_driver)
        except TimeoutException:
            log("❌ Login timeout. Manual login was not completed.")
        finally:
            manual_driver.quit()
        headless_driver = make_driver(headless=True)
        load_cookies(headless_driver)
        headless_driver.get(SITE_URL)
        return headless_driver
    else:
        log("✅ Already logged in.")
        save_cookies(driver)
        return driver

def restart_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass
    log("🔁 Restarting Chrome after repeated failures...")
    new_driver = make_driver(headless=True)
    if new_driver is None:
        log("❌ Failed to restart driver. Cannot continue.")
        return None
    if not load_cookies(new_driver):
        log("⚠️ No cookies found, manual login required.")
    return ensure_login(new_driver)

# ==========================================================
# MODAL & BID LOGIC
# ==========================================================
def wait_for_modal(driver, timeout=25):
    try:
        bid_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-take")))
        driver.execute_script("setTimeout(() => arguments[0].click(), 500);", bid_button)
        log("🖱️ Clicked 'Request/Bid' button via JS.")
        modal_selector = ".modal.show, .modal.fade.in, .modal[style*='display: block'], div.modal-dialog"
        end_time = time.time() + timeout
        while time.time() < end_time:
            modals = driver.find_elements(By.CSS_SELECTOR, modal_selector)
            for modal in modals:
                if modal.is_displayed():
                    log("✅ Modal detected successfully.")
                    return modal
            time.sleep(0.5)
        log("⚠️ Modal not detected after polling.")
        return None
    except Exception as e:
        log(f"❌ Modal error: {e}")
        return None

def place_bid(driver, order_url, message):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"🌀 Attempt {attempt}/{MAX_RETRIES} for {order_url}")
            driver.get(order_url)
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-take")))
            log(f"🔍 Opened order: {order_url}")
            modal = wait_for_modal(driver)
            if not modal:
                raise TimeoutException("Modal not detected")
            textarea = WebDriverWait(modal, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='description']")))
            textarea.clear()
            textarea.send_keys(message)
            log("📝 Message entered.")
            submit_button_selector = "#btn-request, .btn-primary[type='submit']"
            submit = modal.find_element(By.CSS_SELECTOR, submit_button_selector)
            driver.execute_script("arguments[0].click();", submit)
            log("✅ Bid submitted successfully.")
            WebDriverWait(driver, 15).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".modal.show, .modal.fade.in")))
            return True
        except Exception as e:
            log(f"⚠️ Error during bid attempt {attempt}: {e}")
            time.sleep(3)
    log(f"❌ All {MAX_RETRIES} attempts failed for {order_url}.")
    return "restart"

# ==========================================================
# PROFILE SWITCHING
# ==========================================================
def switch_profile(current_path):
    global COOKIES_FILE
    if "Wamboo" in current_path:
        new_path = os.path.join(PROFILE_BASE_DIR, "Paul")
        new_messages = MESSAGES_PAUL
        new_name = "Paul"
    else:
        new_path = os.path.join(PROFILE_BASE_DIR, "Wamboo")
        new_messages = MESSAGES_WAMBOO
        new_name = "Wamboo"
    COOKIES_FILE = os.path.join(new_path, "cookies.pkl")
    return new_path, new_messages, new_name

# ==========================================================
# MAIN LOOP
# ==========================================================
def main():
    global PROFILE_PATH, MESSAGES, PROFILE_NAME, COOKIES_FILE

    driver = make_driver(headless=True)
    if driver is None:
        print("!! SCRIPT EXITING DUE TO DRIVER FAILURE !!")
        return

    if not load_cookies(driver):
        log("⚠️ No cookies found, manual login required.")
    driver = ensure_login(driver)
    if driver is None:
        print("!! SCRIPT EXITING DUE TO LOGIN FAILURE !!")
        return

    last_order_time = time.time()
    failed_bid_count = 0  # consecutive failed bids counter

    while True:
        try:
            log(f"--- Scanning as {PROFILE_NAME} ---")
            driver.get(SITE_URL)
            WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table")))
            log("🔄 Scanning for available orders...")

            rows = driver.find_elements(By.CSS_SELECTOR, "tr[onclick*='order/']")
            order_links = []
            for row in rows:
                try:
                    onclick = row.get_attribute("onclick")
                    if onclick and "order/" in onclick:
                        url_part = onclick.split("'")[1]
                        url = "https://writer.writersadmin.com" + url_part
                        order_links.append(url)
                except Exception as e:
                    log(f"⚠️ Could not parse onclick attribute: {e}")

            if not order_links:
                log("...No new orders found.")
                if time.time() - last_order_time >= INACTIVITY_LIMIT:
                    log(f"⏳ {INACTIVITY_LIMIT}s of inactivity — switching profile...")
                    PROFILE_PATH, MESSAGES, PROFILE_NAME = switch_profile(PROFILE_PATH)
                    log(f"👤 Now using profile: {PROFILE_NAME}")
                    driver.quit()
                    driver = make_driver(headless=True)
                    if driver is None:
                        log("❌ Failed to launch new driver after profile switch. Exiting.")
                        return
                    if not load_cookies(driver):
                        log("⚠️ No cookies found for this profile, manual login required.")
                    driver = ensure_login(driver)
                    if driver is None:
                        log("❌ Failed to login after profile switch. Exiting.")
                        return
                    last_order_time = time.time()

            else:
                log(f"🆕 Found {len(order_links)} order(s). Attempting bids...")
                last_order_time = time.time()
                for order_url in order_links:
                    message = random.choice(MESSAGES)
                    log(f"--- Bidding on: {order_url} ---")
                    result = place_bid(driver, order_url, message)

                    if result == "restart":
                        failed_bid_count += 1
                        log(f"⚠️ Consecutive failed bids: {failed_bid_count}")
                        if failed_bid_count >= 2:
                            log("⏳ Multiple consecutive bid failures — switching profile...")
                            PROFILE_PATH, MESSAGES, PROFILE_NAME = switch_profile(PROFILE_PATH)
                            log(f"👤 Now using profile: {PROFILE_NAME}")
                            driver.quit()
                            driver = make_driver(headless=True)
                            if driver is None:
                                log("❌ Failed to launch driver after profile switch. Exiting.")
                                return
                            if not load_cookies(driver):
                                log("⚠️ No cookies found for this profile, manual login required.")
                            driver = ensure_login(driver)
                            if driver is None:
                                log("❌ Failed to login after profile switch. Exiting.")
                                return
                            failed_bid_count = 0
                            break
                        else:
                            driver = restart_driver(driver)
                            if driver is None:
                                log("❌ Failed to restart driver. Exiting.")
                                return
                            log("...Restarted driver. Breaking bid loop to rescan.")
                            break
                    else:
                        failed_bid_count = 0
                        time.sleep(random.uniform(3, 6))

            wait_time = random.randint(*CHECK_INTERVAL)
            log(f"💤 Sleeping {wait_time}s before next scan...")
            time.sleep(wait_time)

        except WebDriverException as e:
            log(f"⚠️ Browser issue (WebDriverException): {e}. Restarting Chrome...")
            driver = restart_driver(driver)
            if driver is None:
                log("❌ Could not restart driver. Exiting.")
                return
            time.sleep(10)

        except Exception as e:
            log(f"⚠️ Unexpected error in main loop: {e}. Restarting driver...")
            driver = restart_driver(driver)
            if driver is None:
                log("❌ Could not restart driver. Exiting.")
                return
            time.sleep(30)

if __name__ == "__main__":
    main()
