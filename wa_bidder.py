import os
import pickle
import random
import time
import traceback
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
PROFILE_PATH = r"C:\selenium\writersadmin_profile"
COOKIES_FILE = os.path.join(PROFILE_PATH, "cookies.pkl")
CHECK_INTERVAL = (30, 45)
AUTO_BID = True
MAX_RETRIES = 3  # retry attempts before restarting Chrome

MESSAGES = [
    "Hi! I’m very interested in working on this order. I have strong experience in similar tasks and always ensure timely delivery with well-researched, high-quality content. Kindly consider my bid.",
    "Hello! I’d love the opportunity to handle this paper. I have a solid academic background and make sure all my work is 100% original, polished, and aligned with the given instructions.",
    "Greetings! I’m confident in my ability to deliver this project on time and to your expectations. I value clarity, structure, and originality in every assignment I handle.",
    "Hi there! I’d be glad to take on this task. My writing approach combines thorough research with clear, engaging presentation. Expect professional and plagiarism-free work.",
    "Hi, I’m enthusiastic about starting this order and confident in my ability to provide content that meets high standards. I ensure all my work is 100% original, thoughtfully crafted, and not AI-generated in any way. I appreciate your trust!",
    "Hello! I’m well-versed in this subject and confident in delivering a properly formatted, error-free, and original paper. Quality, communication, and deadlines are always my top priorities.",
    "Hey there! I’ve successfully handled similar assignments before. I guarantee high-quality work, deep analysis, and proper referencing to ensure your satisfaction and success.",
    "Good day! I take pride in producing detailed, well-organized, and plagiarism-free papers. I always tailor each project to match client needs and academic requirements perfectly.",
    "Hi! I’d love to assist with this order. My writing is 100% authentic, well-structured, and thoroughly checked before submission. You can count on me for reliability and excellence.",
    "Hello! I’m confident my experience and attention to detail make me a great fit for this project. I’ll provide an insightful, original, and properly formatted submission right on time."
]


# ==========================================================
# UTILITIES
# ==========================================================
def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{stamp}] {msg}"
    print(entry)
    with open(os.path.join(PROFILE_PATH, "activity.log"), "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def make_driver(headless=True):
    """Create Chrome driver with or without headless mode."""
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

    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver


def save_cookies(driver):
    pickle.dump(driver.get_cookies(), open(COOKIES_FILE, "wb"))
    log("✅ Cookies saved.")


def load_cookies(driver):
    if os.path.exists(COOKIES_FILE):
        try:
            cookies = pickle.load(open(COOKIES_FILE, "rb"))
            for cookie in cookies:
                driver.add_cookie(cookie)
            log("✅ Loaded cookies from file.")
            return True
        except Exception as e:
            log(f"⚠️ Failed to load cookies: {e}")
    return False


def ensure_login(driver):
    """Ensure we’re logged in — only non-headless for manual login."""
    driver.get(SITE_URL)
    time.sleep(5)
    if "login" in driver.current_url.lower():
        log("⚠️ Not logged in. Launching visible browser for manual login...")
        driver.quit()
        manual_driver = make_driver(headless=False)
        manual_driver.get(SITE_URL)
        WebDriverWait(manual_driver, 300).until(lambda d: "available" in d.current_url.lower())
        save_cookies(manual_driver)
        manual_driver.quit()
        log("✅ Login completed and cookies saved.")
        return make_driver(headless=True)
    else:
        log("✅ Already logged in.")
        return driver


def restart_driver(driver):
    """Restart Chrome safely when modal or repeated errors occur."""
    try:
        driver.quit()
    except Exception:
        pass
    log("🔁 Restarting Chrome after repeated failures...")
    new_driver = make_driver(headless=True)
    if load_cookies(new_driver):
        new_driver.get(SITE_URL)
        ensure_login(new_driver)
    else:
        ensure_login(new_driver)
    return new_driver


# ==========================================================
# MODAL HANDLER
# ==========================================================
def wait_for_modal(driver, timeout=25):
    """Wait robustly for the bid modal to appear."""
    try:
        bid_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-take"))
        )
        driver.execute_script("setTimeout(() => arguments[0].click(), 500);", bid_button)
        log("🖱️ Clicked 'Request/Bid' button via JS.")

        end_time = time.time() + timeout
        while time.time() < end_time:
            modals = driver.find_elements(
                By.CSS_SELECTOR,
                ".modal.show, .modal.fade.in, .modal[style*='display: block'], div.modal-dialog"
            )
            if modals:
                modal = modals[0]
                if modal.is_displayed():
                    log("✅ Modal detected successfully.")
                    return modal
            time.sleep(0.5)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        driver.save_screenshot(f"debug_modal_fail_{ts}.png")
        log(f"⚠️ Modal not detected (screenshot: debug_modal_fail_{ts}.png)")
        return None
    except Exception as e:
        log(f"❌ Modal error: {e}")
        return None


# ==========================================================
# BID LOGIC
# ==========================================================
def place_bid(driver, order_url, message):
    """Try placing a bid with retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"🌀 Attempt {attempt}/{MAX_RETRIES} for {order_url}")
            driver.get(order_url)
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-take"))
            )
            log(f"🔍 Opened order: {order_url}")

            modal = wait_for_modal(driver)
            if not modal:
                raise TimeoutException("Modal not detected")

            time.sleep(1.5)
            textarea = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='description']"))
            )
            textarea.clear()
            textarea.send_keys(message)
            log("📝 Message entered.")

            submit = driver.find_element(By.CSS_SELECTOR, "#btn-request")
            driver.execute_script("arguments[0].click();", submit)
            log("✅ Bid submitted successfully.")
            return True

        except Exception as e:
            log(f"⚠️ Error during bid attempt {attempt}: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            driver.save_screenshot(f"debug_bid_error_{ts}.png")
            time.sleep(3)

    # All retries failed
    log(f"❌ All {MAX_RETRIES} attempts failed for {order_url}. Restarting browser...")
    return "restart"


# ==========================================================
# MAIN LOOP
# ==========================================================
def main():
    driver = make_driver(headless=True)
    if not load_cookies(driver):
        log("⚠️ No cookies found, manual login required.")
    driver = ensure_login(driver)

    while True:
        try:
            driver.get(SITE_URL)
            WebDriverWait(driver, 30).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table"))
            )
            log("🔄 Scanning for available orders...")

            rows = driver.find_elements(By.CSS_SELECTOR, "tr")
            order_links = []
            for row in rows:
                onclick = row.get_attribute("onclick")
                if onclick and "order/" in onclick:
                    url = "https://writer.writersadmin.com" + onclick.split("'")[1]
                    order_links.append(url)

            if not order_links:
                log("🕒 No orders found this round.")
            else:
                log(f"🆕 Found {len(order_links)} order(s). Attempting bids...")
                for order_url in order_links:
                    message = random.choice(MESSAGES)
                    result = place_bid(driver, order_url, message)
                    if result == "restart":
                        driver = restart_driver(driver)
                        break
                    time.sleep(random.uniform(3, 6))

            wait_time = random.randint(*CHECK_INTERVAL)
            log(f"💤 Sleeping {wait_time}s before next scan...")
            time.sleep(wait_time)

        except WebDriverException as e:
            log(f"⚠️ Browser issue: {e}. Restarting Chrome...")
            driver = restart_driver(driver)

        except Exception as e:
            log(f"⚠️ Loop error: {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()
