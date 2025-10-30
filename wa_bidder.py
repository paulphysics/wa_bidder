"""
Auto-bidding Selenium bot with dynamic profiles and OpenAI-enhanced messages.
Updated to use openai>=1.0.0 client interface (OpenAI.chat.completions.create).

Before running:
 - pip install --upgrade selenium openai
 - Place matching chromedriver on PATH or update Service() path
 - Replace OPENAI_API_KEY placeholder below locally (do NOT share it)
"""

import os
import pickle
import random
import time
from datetime import datetime
import logging

from openai import OpenAI  # new client
import openai  # keep for potential helper constants if needed
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
CHECK_INTERVAL = (30, 45)  # seconds between scans
MAX_RETRIES = 3
INACTIVITY_LIMIT = 120  # seconds before switching profile
OPENAI_MODEL = "gpt-4o-mini"  # change to a model available on your account if needed
OPENAI_TIMEOUT = 12  # seconds to wait for OpenAI response

# ======= Replace with your key locally (DO NOT paste key into chats) =======
OPENAI_API_KEY = "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"
# ===========================================================================

# ==========================================================
# PROFILES (10 messages each - using "work")
# ==========================================================
PROFILES = {
    "Paul": [
        "Hi! I’m excited about this work and confident I can deliver a well-researched, clearly structured result by your deadline.",
        "Hello! I’d be glad to handle this work — I guarantee originality, clear argumentation, and correct formatting.",
        "Greetings! I focus on producing polished, thoroughly-researched work tailored to instructions and timelines.",
        "Hi there! I approach every work with care and detail, delivering accurate and well-referenced results on time.",
        "Good day! I’m ready to take on this work and provide consistent communication and a professional final deliverable.",
        "Hello! I produce authoritative, well-structured work that follows instructions closely and meets quality expectations.",
        "Hi! I prioritize clarity, originality, and accurate referencing when delivering work — you’ll receive a high-quality file.",
        "Hello there! I can complete this work with careful research and clean formatting to match your requirements.",
        "Hey! I’ll make sure this work is well-argued, thoroughly checked, and properly referenced before submission.",
        "Hi! I’m dependable and detail-oriented — I’ll deliver the requested work promptly and to specification."
    ],
    "Wamboo": [
        "Hi! I’m very interested in this work and confident I can deliver clear, original, and timely results.",
        "Hello! I’ll approach this work with structured research and careful formatting to match your instructions.",
        "Greetings! I produce high-quality work, paying attention to detail, citations, and client preferences.",
        "Hi there! Expect well-organized and accurate work delivered within the set timeframe.",
        "Good day! I’m committed to delivering thorough, plagiarism-free work that follows all guidelines.",
        "Hello! I take pride in well-researched and well-written work that communicates ideas clearly.",
        "Hey! I deliver work that balances depth of research with clear presentation and punctual delivery.",
        "Hi! I ensure the work I deliver is original, well-cited, and tailored to your instructions.",
        "Hello there! I’ll deliver carefully constructed work that demonstrates strong research and editing.",
        "Hi! I’m ready to start this work and will maintain excellent communication throughout the process."
    ],
    "Python": [
        "Hi! I can take on this work and deliver a well-structured, accurate outcome on time.",
        "Hello! My approach to work is research-driven, organized, and tailored to your specifications.",
        "Greetings! I’ll complete this work with attention to detail and solid argumentation.",
        "Hi there! I offer reliable delivery of clear, original, and correctly referenced work.",
        "Good day! Expect a polished, well-edited piece of work that follows the provided guidelines.",
        "Hello! I focus on producing clear, concise, and accurate work suited to the task.",
        "Hey! I’ll ensure your work is well-researched, formatted, and delivered punctually.",
        "Hi! I can provide work that meets academic and client expectations, with proper citations.",
        "Hello there! I’ll approach this work with careful research and clean presentation.",
        "Hi! I’m prepared to deliver dependable, plagiarism-free work within the deadline."
    ]
}

# Build profile paths dynamically
PROFILE_DIRS = {name: os.path.join(PROFILE_BASE_DIR, name) for name in PROFILES.keys()}

# Choose initial profile at random
PROFILE_NAME = random.choice(list(PROFILES.keys()))
PROFILE_PATH = PROFILE_DIRS[PROFILE_NAME]
MESSAGES = PROFILES[PROFILE_NAME]
COOKIES_FILE = os.path.join(PROFILE_PATH, "cookies.pkl")

# ==========================================================
# Logging setup
# ==========================================================
os.makedirs(PROFILE_PATH, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(PROFILE_PATH, "activity.log"), encoding="utf-8")
    ]
)
log = logging.getLogger("bidbot").info
warn = logging.getLogger("bidbot").warning
error = logging.getLogger("bidbot").error

print(f"👤 Using profile: {PROFILE_NAME}")
print(f"💬 Loaded {len(MESSAGES)} messages for this session.")

# ==========================================================
# OpenAI client setup (new API)
# ==========================================================
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_message_openai(profile_name: str, base_message: str, order_details: dict) -> str:
    """
    Use OpenAI client to rewrite/expand the base_message to match order details and profile tone.
    Falls back to the base_message if the API fails.
    """
    system_prompt = (
        "You are an assistant that rewrites short freelancer bids to be concise, human, "
        "and tailored to the order. Use the word 'work' (not 'essay' or 'paper'). Keep the result "
        "to 1-3 short sentences and avoid mentioning you are an AI or using internal notes."
    )

    user_prompt = (
        f"Profile name: {profile_name}\n"
        f"Base message (adapt this, don't repeat exactly): \"{base_message}\"\n\n"
        f"Order title: {order_details.get('title','N/A')}\n"
        f"Order instructions (short): {order_details.get('instructions','N/A')[:800]}\n"
        f"Word count text: {order_details.get('word_count','N/A')}\n"
        f"Keywords: {order_details.get('keywords','')}\n\n"
        "Rewrite the base message to sound human, polite, and tailored to the order. Keep it concise (<= 280 chars)."
    )

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=140,
            temperature=0.7,
            timeout=OPENAI_TIMEOUT
        )
        # new API structure: access first choice message content
        text = resp.choices[0].message.content.strip()
        log(f"🧠 OpenAI enhanced message for {profile_name}.")
        return text
    except Exception as e:
        warn(f"⚠️ OpenAI failed: {e}. Using base message as fallback.")
        return base_message

# ==========================================================
# Selenium / Browser helpers (unchanged)
# ==========================================================
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
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    )
    service = Service()  # change to Service("/path/to/chromedriver") if needed
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        return driver
    except WebDriverException as e:
        error(f"CRITICAL DRIVER ERROR: {e}")
        return None

def save_cookies(driver):
    try:
        pickle.dump(driver.get_cookies(), open(COOKIES_FILE, "wb"))
        log("✅ Cookies saved.")
    except Exception as e:
        warn(f"⚠️ Error saving cookies: {e}")

def load_cookies(driver):
    if os.path.exists(COOKIES_FILE):
        try:
            cookies = pickle.load(open(COOKIES_FILE, "rb"))
            driver.get(SITE_URL.split("/orders")[0])
            for cookie in cookies:
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    cookie['sameSite'] = 'Lax'
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass
            log("✅ Loaded cookies from file.")
            return True
        except Exception as e:
            warn(f"⚠️ Failed to load cookies: {e}")
    return False

def ensure_login(driver):
    driver.get(SITE_URL)
    time.sleep(3)
    if "login" in driver.current_url.lower():
        warn("⚠️ Not logged in. Opening visible browser for manual login...")
        try:
            driver.quit()
        except Exception:
            pass
        manual_driver = make_driver(headless=False)
        if manual_driver is None:
            error("❌ Failed to launch manual browser for login.")
            return None
        manual_driver.get(SITE_URL)
        log("Please complete manual login in the opened browser window. This will close after login.")
        try:
            WebDriverWait(manual_driver, 300).until(lambda d: "available" in d.current_url.lower())
            log("✅ Manual login detected. Saving cookies.")
            pickle.dump(manual_driver.get_cookies(), open(COOKIES_FILE, "wb"))
        except TimeoutException:
            warn("❌ Manual login timeout.")
        finally:
            manual_driver.quit()
        headless_driver = make_driver(headless=True)
        if headless_driver is None:
            error("❌ Could not create headless driver after manual login.")
            return None
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
    log("🔁 Restarting Chrome...")
    new_driver = make_driver(headless=True)
    if new_driver is None:
        error("❌ Failed to restart driver.")
        return None
    if not load_cookies(new_driver):
        warn("⚠️ No cookies found for this profile after restart.")
    return ensure_login(new_driver)

# ==========================================================
# Order parsing & bid flow (uses given selectors - unchanged)
# ==========================================================
def get_order_details(driver):
    """
    Read title from h4.__web-inspector-hide-shortcut__ and instructions from div[bis_skin_checked] p
    """
    try:
        title = "Untitled Work"
        instructions = ""
        word_count = "N/A"
        keywords = ""

        # Title selector provided
        try:
            title_el = driver.find_element(By.CSS_SELECTOR, "h4.__web-inspector-hide-shortcut__")
            title = title_el.text.strip()
        except Exception:
            try:
                title_el = driver.find_element(By.CSS_SELECTOR, "h1, h2, h3, h4")
                title = title_el.text.strip()
            except Exception:
                pass

        # Instructions via the provided div/p structure
        try:
            paragraphs = driver.find_elements(By.CSS_SELECTOR, "div[bis_skin_checked] p")
            if paragraphs:
                instructions = " ".join(p.text.strip() for p in paragraphs if p.text.strip())
        except Exception:
            try:
                instr_el = driver.find_element(By.CSS_SELECTOR, ".order-instructions, .description, .order-desc")
                instructions = instr_el.text.strip()
            except Exception:
                pass

        # Very heuristic word count detection (search for "word" tokens)
        combined = f"{title} {instructions}".lower()
        try:
            import re
            m = re.search(r"(\d{2,5})\s+words?", combined)
            if m:
                word_count = m.group(1)
        except Exception:
            pass

        # basic keyword extraction
        key_list = []
        for kw in ["research", "analysis", "case study", "literature review", "presentation", "report", "code", "math", "statistics", "whitepaper", "white paper"]:
            if kw in combined:
                key_list.append(kw)
        keywords = ", ".join(key_list)

        log(f"📄 Title: {title or 'N/A'}")
        log(f"📋 Instr preview: {(instructions[:200] + '...') if instructions else 'N/A'}")
        log(f"🔢 Word count: {word_count}")
        log(f"🔎 Keywords: {keywords or 'None'}")

        return {"title": title, "instructions": instructions, "word_count": word_count, "keywords": keywords}
    except Exception as e:
        warn(f"⚠️ Failed to read order details: {e}")
        return {"title":"N/A","instructions":"N/A","word_count":"N/A","keywords":""}

def wait_for_modal_and_fill(driver, message):
    """
    Click the take/request button, wait for modal, fill textarea and submit.
    """
    try:
        bid_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-take, .take-btn, .btn-request")) )
        driver.execute_script("setTimeout(() => arguments[0].click(), 250);", bid_button)
        log("🖱️ Clicked Request/Bid button.")
    except Exception as e:
        raise Exception(f"Could not click bid button: {e}")

    modal_selector = ".modal.show, .modal.fade.in, .modal[style*='display: block'], div.modal-dialog"
    end_time = time.time() + 20
    while time.time() < end_time:
        modals = driver.find_elements(By.CSS_SELECTOR, modal_selector)
        for modal in modals:
            if modal.is_displayed():
                try:
                    textarea = modal.find_element(By.CSS_SELECTOR, "textarea[name='description'], textarea")
                    textarea.clear()
                    textarea.send_keys(message)
                    log("📝 Entered message into modal.")
                    submit_button = modal.find_element(By.CSS_SELECTOR, "#btn-request, .btn-primary[type='submit'], button.submit")
                    driver.execute_script("arguments[0].click();", submit_button)
                    log("✅ Submitted bid.")
                    WebDriverWait(driver, 10).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, modal_selector)))
                    return True
                except Exception as e:
                    raise Exception(f"Failed to fill/submit modal: {e}")
        time.sleep(0.4)
    raise Exception("Modal did not appear in time.")

def place_bid(driver, order_url, profile_name):
    """
    Open order, read details, create message (base -> OpenAI enhanced), and place bid.
    Returns True on success, "restart" on persistent failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"🌀 Attempt {attempt}/{MAX_RETRIES} for {order_url}")
            driver.get(order_url)
            WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "body")))
            time.sleep(random.uniform(0.8, 1.6))

            details = get_order_details(driver)

            base_msg = random.choice(PROFILES.get(profile_name, list(MESSAGES)))
            enhanced = generate_message_openai(profile_name, base_msg, details)
            message = enhanced.strip() if enhanced else base_msg

            if len(message) > 1000:
                message = message[:1000]

            log(f"✉️ Message to send (snippet): {message[:200]}")
            success = wait_for_modal_and_fill(driver, message)
            if success:
                log(f"✅ Bid placed for {order_url}")
                return True
        except Exception as e:
            warn(f"⚠️ Error during bid attempt {attempt}: {e}")
            time.sleep(2)
    warn(f"❌ All {MAX_RETRIES} attempts failed for {order_url}. Requesting restart.")
    return "restart"

# ==========================================================
# Profile switching
# ==========================================================
def switch_profile(current_name):
    names = list(PROFILES.keys())
    try:
        idx = names.index(current_name)
    except ValueError:
        idx = 0
    next_idx = (idx + 1) % len(names)
    new_name = names[next_idx]
    new_path = PROFILE_DIRS[new_name]
    new_messages = PROFILES[new_name]
    global COOKIES_FILE
    COOKIES_FILE = os.path.join(new_path, "cookies.pkl")
    return new_path, new_messages, new_name

# ==========================================================
# Main loop
# ==========================================================
def main():
    global PROFILE_PATH, MESSAGES, PROFILE_NAME, COOKIES_FILE

    driver = make_driver(headless=True)
    if driver is None:
        error("!! SCRIPT EXITING DUE TO DRIVER FAILURE !!")
        return

    if not load_cookies(driver):
        warn("⚠️ No cookies found - manual login will be required.")
    driver = ensure_login(driver)
    if driver is None:
        error("!! SCRIPT EXITING DUE TO LOGIN FAILURE !!")
        return

    last_order_time = time.time()
    failed_bid_count = 0

    while True:
        try:
            log(f"--- Scanning as {PROFILE_NAME} ---")
            driver.get(SITE_URL)
            WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table, .orders, .order-list")))
            log("🔄 Scanning for available orders...")

            rows = driver.find_elements(By.CSS_SELECTOR, "tr[onclick*='order/'], a[href*='/order/'], .order-row")
            order_links = []
            for row in rows:
                try:
                    onclick = row.get_attribute("onclick") or ""
                    href = row.get_attribute("href") or ""
                    if "order/" in onclick:
                        parts = onclick.split("'")
                        if len(parts) >= 2:
                            url_part = parts[1]
                            url = "https://writer.writersadmin.com" + url_part if url_part.startswith("/") else url_part
                            order_links.append(url)
                    elif href and "/order/" in href:
                        url = ("https://writer.writersadmin.com" + href) if href.startswith("/") else href
                        order_links.append(url)
                except Exception as e:
                    warn(f"⚠️ Could not parse link from row: {e}")

            # dedupe & shuffle
            order_links = list(dict.fromkeys(order_links))
            random.shuffle(order_links)

            if not order_links:
                log("...No new orders found.")
                if time.time() - last_order_time >= INACTIVITY_LIMIT:
                    log(f"⏳ {INACTIVITY_LIMIT}s inactivity — switching profile...")
                    PROFILE_PATH, MESSAGES, PROFILE_NAME = switch_profile(PROFILE_NAME)
                    log(f"👤 Switched to profile: {PROFILE_NAME}")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = make_driver(headless=True)
                    if driver is None:
                        error("❌ Failed to launch driver after profile switch. Exiting.")
                        return
                    if not load_cookies(driver):
                        warn("⚠️ No cookies found for new profile; manual login may be required.")
                    driver = ensure_login(driver)
                    if driver is None:
                        error("❌ Login failed after switching profile. Exiting.")
                        return
                    last_order_time = time.time()
            else:
                log(f"🆕 Found {len(order_links)} order(s). Attempting bids...")
                last_order_time = time.time()
                for order_url in order_links:
                    log(f"--- Bidding on: {order_url} ---")
                    result = place_bid(driver, order_url, PROFILE_NAME)
                    if result == "restart":
                        failed_bid_count += 1
                        warn(f"⚠️ Consecutive failed bids: {failed_bid_count}")
                        if failed_bid_count >= 2:
                            log("⏳ Multiple consecutive failures — switching profile...")
                            PROFILE_PATH, MESSAGES, PROFILE_NAME = switch_profile(PROFILE_NAME)
                            log(f"👤 Now using profile: {PROFILE_NAME}")
                            try:
                                driver.quit()
                            except Exception:
                                pass
                            driver = make_driver(headless=True)
                            if driver is None:
                                error("❌ Failed to launch driver after profile switch. Exiting.")
                                return
                            if not load_cookies(driver):
                                warn("⚠️ No cookies found for this profile; manual login may be required.")
                            driver = ensure_login(driver)
                            if driver is None:
                                error("❌ Failed to login after profile switch. Exiting.")
                                return
                            failed_bid_count = 0
                            break
                        else:
                            driver = restart_driver(driver)
                            if driver is None:
                                error("❌ Failed to restart driver. Exiting.")
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
            warn(f"⚠️ Browser issue: {e}. Restarting...")
            driver = restart_driver(driver)
            if driver is None:
                error("❌ Could not restart driver. Exiting.")
                return
            time.sleep(10)
        except Exception as e:
            warn(f"⚠️ Unexpected main loop error: {e}. Restarting driver...")
            driver = restart_driver(driver)
            if driver is None:
                error("❌ Could not restart driver. Exiting.")
                return
            time.sleep(30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
