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

SITE_URL = "https://employer.writersadmin.com/orders"
PROFILE_BASE_DIR = os.path.expanduser(r"~\selenium_bid_bot_profiles")

# --- Define all profiles and messages ---
PROFILES = {
    "Wamboo": [
        "Hi! I’m very interested in working on this order. I have strong experience in similar tasks and always ensure timely delivery with well-researched, high-quality content. Kindly consider my bid.",
        "Hello! I’m confident in delivering an exceptional, plagiarism-free paper that meets all instructions. I always maintain clear formatting and proper referencing. Looking forward to your approval!",
        "Hi there! I’m skilled at producing professional and original work with a strong focus on clarity, structure, and academic integrity. I’d be happy to complete this order promptly.",
        "Greetings! I’ve handled similar assignments successfully, ensuring high-quality, properly referenced, and plagiarism-free papers. Please consider my bid.",
        "Hello! I deliver high-quality and well-researched work that adheres to all client guidelines. You can rely on me for accuracy, originality, and timely delivery.",
        "Hi! I always ensure professional writing, originality, and proper formatting in every task. I’d love to assist with this order and guarantee excellent results.",
        "Hello! I’ve worked on similar papers before and consistently delivered top-quality content. I’m ready to start immediately and meet your deadline.",
        "Greetings! My experience and attention to detail ensure that all client requirements are met. I can guarantee accuracy, coherence, and high-quality results."
    ],

    "Python": [
        "Hi! I’m ready to handle this task with attention to detail and deliver original, high-quality work on time. My background in data-driven writing ensures clear and logical content.",
        "Hello! I specialize in structured and evidence-based academic writing. I’ll provide a thoroughly researched, plagiarism-free paper that meets every instruction.",
        "Hi! I focus on clarity, precision, and academic integrity. I ensure all papers are well-organized, properly referenced, and tailored to the client’s needs.",
        "Greetings! I have a strong record of delivering polished, accurate, and timely assignments. I’ll make sure this project meets the highest quality standards.",
        "Hello! I’m confident in delivering exceptional results for this order. My writing is concise, professional, and supported by credible sources.",
        "Hi! I pay close attention to guidelines and always ensure perfect formatting and referencing. I’m committed to quality and timeliness.",
        "Hello there! I bring analytical thinking and a structured approach to each task, ensuring coherence and originality. I’d love to work on this order.",
        "Greetings! I’m experienced in producing academic and technical content that meets all client expectations. Quality and accuracy are always my top priorities."
    ]
}

# --- Build dynamic profile directories ---
PROFILE_DIRS = {name: os.path.join(PROFILE_BASE_DIR, name) for name in PROFILES.keys()}

# Randomly select a profile at startup
PROFILE_NAME = random.choice(list(PROFILES.keys()))
PROFILE_PATH = PROFILE_DIRS[PROFILE_NAME]
MESSAGES = PROFILES[PROFILE_NAME]
COOKIES_FILE = os.path.join(PROFILE_PATH, "cookies.pkl")

print(f"👤 Using profile: {PROFILE_NAME}")
print(f"💬 Loaded {len(MESSAGES)} messages for this session.")


# ==========================================================
# DRIVER CONFIGURATION
# ==========================================================

def make_driver(profile_path):
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1366,768")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--headless=new")  # remove if you want UI
    chrome_options.add_argument(f"--user-data-dir={profile_path}")

    driver_path = Service(r"C:\chromedriver\chromedriver.exe")
    driver = webdriver.Chrome(service=driver_path, options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver


# ==========================================================
# COOKIES HANDLING
# ==========================================================

def save_cookies(driver, path):
    with open(path, "wb") as file:
        pickle.dump(driver.get_cookies(), file)

def load_cookies(driver, path):
    try:
        with open(path, "rb") as file:
            cookies = pickle.load(file)
        for cookie in cookies:
            if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                cookie['sameSite'] = 'Lax'
            driver.add_cookie(cookie)
        print("✅ Cookies loaded successfully.")
    except Exception:
        print("⚠️ No valid cookies found. Manual login required.")


# ==========================================================
# PROFILE SWITCHING
# ==========================================================

def switch_profile(current_name):
    names = list(PROFILES.keys())
    current_index = names.index(current_name)
    next_index = (current_index + 1) % len(names)
    new_name = names[next_index]
    new_path = PROFILE_DIRS[new_name]
    new_messages = PROFILES[new_name]
    global COOKIES_FILE
    COOKIES_FILE = os.path.join(new_path, "cookies.pkl")
    print(f"\n🔄 Switching to profile: {new_name}")
    return new_path, new_messages, new_name


# ==========================================================
# LOGIN HANDLING
# ==========================================================

def ensure_login(driver):
    driver.get(SITE_URL)
    time.sleep(5)
    if "login" in driver.current_url.lower():
        print("🔐 Manual login required.")
        try:
            WebDriverWait(driver, 300).until_not(lambda d: "login" in d.current_url.lower())
            save_cookies(driver, COOKIES_FILE)
        except TimeoutException:
            print("❌ Login timeout reached.")


# ==========================================================
# ORDER SCANNING & BIDDING
# ==========================================================

def scan_orders(driver):
    driver.get(SITE_URL)
    time.sleep(random.uniform(3, 6))
    orders = driver.find_elements(By.CSS_SELECTOR, ".table > tbody > tr")
    print(f"🔍 Found {len(orders)} orders.")
    return orders

def place_bid(driver, order_element, message):
    try:
        bid_button = order_element.find_element(By.CSS_SELECTOR, ".btn.btn-success.btn-sm")
        driver.execute_script("arguments[0].click();", bid_button)
        time.sleep(random.uniform(1, 3))

        textarea = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea.form-control"))
        )
        textarea.clear()
        textarea.send_keys(message)

        submit_button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-primary")
        driver.execute_script("arguments[0].click();", submit_button)
        print(f"💰 Bid placed successfully with message: {message}")
        return True
    except Exception as e:
        print(f"⚠️ Failed to place bid: {e}")
        return False


# ==========================================================
# MAIN LOGIC LOOP
# ==========================================================

def main_loop():
    global PROFILE_PATH, MESSAGES, PROFILE_NAME
    driver = make_driver(PROFILE_PATH)
    ensure_login(driver)
    load_cookies(driver, COOKIES_FILE)

    failure_count = 0
    while True:
        try:
            orders = scan_orders(driver)
            for order in orders:
                message = random.choice(MESSAGES)
                success = place_bid(driver, order, message)
                if success:
                    time.sleep(random.uniform(15, 30))
            time.sleep(random.uniform(60, 120))
        except WebDriverException:
            print("⚠️ Browser crashed, restarting...")
            driver.quit()
            PROFILE_PATH, MESSAGES, PROFILE_NAME = switch_profile(PROFILE_NAME)
            driver = make_driver(PROFILE_PATH)
            ensure_login(driver)
            load_cookies(driver, COOKIES_FILE)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            failure_count += 1
            if failure_count >= 3:
                PROFILE_PATH, MESSAGES, PROFILE_NAME = switch_profile(PROFILE_NAME)
                failure_count = 0
        time.sleep(random.uniform(30, 60))


if __name__ == "__main__":
    main_loop()
