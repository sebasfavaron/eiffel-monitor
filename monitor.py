#!/usr/bin/env python3
"""
Eiffel Tower availability monitor.
Uses Playwright to check actual availability by clicking dates.
"""

import json
import time
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import requests

load_dotenv()

TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

TARGET_DATES = ["2026-05-15", "2026-05-16", "2026-05-17", "2026-05-18", "2026-05-19"]
POLL_INTERVAL = 900

STATE_FILE = Path(__file__).parent / "state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "monitor.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            data["alerted_dates"] = set(data.get("alerted_dates", []))
            return data
        except Exception:
            pass
    return {"alerted_dates": set()}


def save_state(state: dict) -> None:
    data = state.copy()
    data["alerted_dates"] = list(state["alerted_dates"])
    STATE_FILE.write_text(json.dumps(data))


def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_USER_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.ok:
            log.info("Telegram alert sent")
            return True
        else:
            log.error(f"Telegram error: {resp.status_code}")
            return False
    except Exception as e:
        log.error(f"Telegram failed: {e}")
        return False


def check_availability() -> dict:
    """Use Playwright to click each date and check real availability."""
    log.info("Checking real availability via Playwright...")
    
    result = {"target_dates_status": {}}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto("https://ticket.toureiffel.paris/fr", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            
            page.evaluate('''() => {
                const root = document.getElementById('tarteaucitronRoot');
                if (root) root.remove();
            }''')
            
            # Navigate to May
            for i in range(15):
                page.evaluate('document.getElementById("d-next").click()')
                time.sleep(1)
                current = page.evaluate('document.querySelector(".d-month").textContent')
                if 'mai' in current.lower():
                    break
            
            time.sleep(1)
            
            # Check each target date by clicking
            month_names = {
                'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
                'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
                'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
            }
            
            for target in TARGET_DATES:
                # Parse target date
                parts = target.split('-')
                year = parts[0]
                month = parts[1]
                day = int(parts[2])
                
                # Find French month name
                month_name = [k for k, v in month_names.items() if v == month]
                if month_name:
                    month_fr = month_name[0]
                    search_text = f"{day} {month_fr}"
                else:
                    continue
                
                log.info(f"Checking {target}...")
                
                # Click on the date
                clicked = page.evaluate(f'''(search) => {{
                    const labels = document.querySelectorAll('.d-table .d-cell label');
                    for (const l of labels) {{
                        if (l.textContent.includes(search)) {{
                            l.dispatchEvent(new MouseEvent('click', {{bubbles: true}}));
                            return true;
                        }}
                    }}
                    return false;
                }}''', search_text)
                
                time.sleep(2)
                
                # Check page content for availability
                page_text = page.evaluate('document.body.innerText').lower()
                
                # Check for "occupé" or "indisponible" or "épuisé"
                is_sold_out = ('occupé' in page_text or 
                              'indisponible' in page_text or 
                              'épuisé' in page_text or
                              'plus de billet' in page_text)
                
                # Check for ticket options (indicates available)
                has_tickets = ('ascenseur' in page_text or 
                              'sommets' in page_text or
                              '2ème étage' in page_text or
                              'billets pour' in page_text)
                
                if is_sold_out:
                    status = "sold_out"
                    log.info(f"  {target}: SOLD OUT")
                elif has_tickets:
                    status = "available"
                    log.info(f"  {target}: AVAILABLE")
                else:
                    status = "unknown"
                    log.info(f"  {target}: UNKNOWN - might be available, check manually")
                
                result["target_dates_status"][target] = status
            
            browser.close()
            
    except Exception as e:
        log.error(f"Playwright error: {e}")
        return {"error": str(e)}
    
    log.info(f"Final status: {result['target_dates_status']}")
    return result


def run_once():
    state = load_state()
    result = check_availability()
    
    if "error" in result:
        log.error(f"Check failed: {result['error']}")
        return
    
    available = [
        d for d, s in result["target_dates_status"].items()
        if s == "available"
    ]
    
    if available:
        new_alerts = [d for d in available if d not in state["alerted_dates"]]
        
        if new_alerts:
            status_str = "\n".join(
                f"- {d}: {result['target_dates_status'][d]}" 
                for d in new_alerts
            )
            msg = f"🎫 <b>ENTRADAS EIFFEL DISPONIBLES!</b>\n\n{status_str}\n\n"
            msg += f"<a href=\"https://ticket.toureiffel.paris/fr\">Comprar (FR)</a>"
            
            if send_telegram(msg):
                state["alerted_dates"].update(new_alerts)
                save_state(state)
                log.info(f"Alerted: {new_alerts}")
        else:
            log.info("Already alerted for these dates")
    else:
        log.info("No availability for target dates")


def run_continuous():
    log.info(f"Starting monitor - dates: {TARGET_DATES}, interval: {POLL_INTERVAL}s")
    while True:
        run_once()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        run_continuous()
