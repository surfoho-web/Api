import os
import re
import time
import logging
from pathlib import Path

from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("weplay-vercel")

TARGET_URL = "https://weplayapp.com/en-IN/recharge"
PAGE_LOAD_TIMEOUT_MS = 25_000
RESULT_TIMEOUT_MS = 15_000
PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PROJECT_ROOT / ".playwright-browsers"))

app = Flask(__name__)

def fetch_weplay(uid: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        try:
            page = browser.new_page(viewport={"width": 1365, "height": 900})
            page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)
            page.set_default_timeout(10_000)
            page.goto(TARGET_URL, wait_until="domcontentloaded")

            field = None
            for selector in (
                "input.input",
                "input[placeholder*='WePlay ID' i]",
                "input[type='text']",
            ):
                candidate = page.locator(selector).first
                try:
                    candidate.wait_for(state="visible", timeout=2500)
                    field = candidate
                    break
                except PlaywrightTimeoutError:
                    continue
            if field is None:
                raise RuntimeError("UID input not found; WePlay may have changed its page")

            field.fill(uid)
            submitted = False
            for selector in (
                "button:has-text('Search')",
                "button:has-text('Lookup')",
                "button:has-text('Submit')",
                "button:has-text('Confirm')",
                "button:has-text('Check')",
                "button[type='submit']",
            ):
                try:
                    button = page.locator(selector).first
                    if button.is_visible(timeout=400):
                        button.click(timeout=1500)
                        submitted = True
                        break
                except Exception:
                    continue
            if not submitted:
                field.press("Enter")

            deadline = time.monotonic() + RESULT_TIMEOUT_MS / 1000
            while time.monotonic() < deadline:
                try:
                    nickname = page.locator(".nickname").first.inner_text(timeout=400).strip()
                except Exception:
                    nickname = ""
                try:
                    raw = page.locator(".value").first.inner_text(timeout=400).strip()
                except Exception:
                    raw = ""
                match = re.search(r"Charm\s*:\s*([\d,]+)", raw, re.I)
                charm = match.group(1).replace(",", "") if match else re.sub(
                    r"^Charm\s*:\s*", "", raw, flags=re.I
                ).strip()
                try:
                    avatar = page.locator("img.avatar").first.get_attribute("src", timeout=400)
                except Exception:
                    avatar = None
                if not avatar:
                    try:
                        avatar = page.locator("img").evaluate_all(
                            """imgs => {
                              const img = imgs.find(i => /^https?:\\/\\/picuser[^/]*\\.weplayapp\\.com\\//i.test(i.currentSrc || i.src || ''));
                              return img ? (img.currentSrc || img.src || null) : null;
                            }"""
                        )
                    except Exception:
                        avatar = None
                if nickname and charm:
                    return {"nickname": nickname, "charm": charm, "profile_pic_url": avatar}
                page.wait_for_timeout(250)
            raise RuntimeError("Lookup result not found; WePlay may have changed the page or blocked automation")
        finally:
            browser.close()

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "WePlay UID Lookup API",
        "endpoints": ["/health", "/lookup?uid=92661060"],
        "browser": "bundled Playwright Chromium",
    })

@app.route("/health", methods=["GET"])
def health():
    browser_dir = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    return jsonify({"status": "ok", "browser_bundle_present": browser_dir.exists()})

@app.route("/lookup", methods=["GET", "POST"])
def lookup():
    if request.method == "GET":
        uid = str(request.args.get("uid", "")).strip()
    else:
        payload = request.get_json(silent=True) or {}
        uid = str(payload.get("uid", "")).strip()
    if not re.fullmatch(r"\d{5,}", uid):
        return jsonify({"success": False, "error": "Invalid UID"}), 400

    started = time.time()
    try:
        result = fetch_weplay(uid)
        return jsonify({
            "success": True, "uid": uid, **result,
            "cached": False, "took_ms": round((time.time() - started) * 1000),
        })
    except PlaywrightTimeoutError:
        return jsonify({"success": False, "error": "Timeout fetching UID"}), 504
    except Exception as exc:
        log.exception("Lookup failed")
        return jsonify({"success": False, "error": "Failed to fetch UID", "details": str(exc)}), 502
