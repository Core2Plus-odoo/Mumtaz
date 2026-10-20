#!/usr/bin/env python3
"""
IG Square — Odoo finance demo recorder (best-effort, run ON THE VPS).

This container can't reach the VPS, so run this on the server itself, where
Odoo is reachable at http://localhost:8071 (dbfilter = Mumtaz_IG2).

It drives the real UI headless and records the whole walkthrough to a video.
Each scene is wrapped in try/except: if a selector misses it logs "SKIP <scene>"
and carries on, so you still get a full recording. Tell me which scenes it
skipped and I'll fix those selectors.

----------------------------------------------------------------------------
SETUP (once, on the VPS):

    sudo apt-get install -y ffmpeg                     # optional: webm -> mp4
    python3 -m venv /tmp/pwdemo && . /tmp/pwdemo/bin/activate
    pip install playwright
    playwright install chromium
    playwright install-deps chromium                    # system libs

RUN (credentials come from env — nothing is hard-coded here):

    export ODOO_URL=http://localhost:8071
    export ODOO_DB=Mumtaz_IG2
    export ODOO_USER='your-login@igsquare'              # email/login
    export ODOO_PASSWORD='your-password'
    python /path/to/record_demo.py

OUTPUT:
    ./demo_video/<random>.webm   (and demo_video/igsquare_demo.mp4 if ffmpeg)
----------------------------------------------------------------------------
"""
import os
import glob
import shutil
import subprocess

from playwright.sync_api import sync_playwright

URL = os.environ.get("ODOO_URL", "http://localhost:8071").rstrip("/")
DB = os.environ.get("ODOO_DB", "Mumtaz_IG2")
USER = os.environ.get("ODOO_USER", "")
PWD = os.environ.get("ODOO_PASSWORD", "")
OUT = os.path.abspath("demo_video")
VENDOR = os.environ.get("DEMO_VENDOR", "A.F.Ferguson & Co.")

# Pacing (ms). Bigger = slower, more watchable.
BEAT = 1500
HOLD = 3500


def log(*a):
    print("REC|", *a, flush=True)


def scene(fn):
    """Run a scene, never let one failure abort the recording."""
    def wrap(page):
        try:
            log("scene:", fn.__name__)
            fn(page)
        except Exception as e:
            log("SKIP", fn.__name__, "->", repr(e)[:160])
    return wrap


def click_text(page, text, timeout=8000, exact=False):
    page.get_by_text(text, exact=exact).first.click(timeout=timeout)
    page.wait_for_timeout(BEAT)


def open_app_menu(page, name):
    """Open a top-level Odoo app/menu by visible text."""
    page.wait_for_timeout(BEAT)
    page.get_by_role("menuitem", name=name).first.click(timeout=8000)
    page.wait_for_timeout(BEAT)


def login(page):
    log("login", URL, "db", DB, "user", USER or "(unset)")
    page.goto(URL + "/web/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(BEAT)
    # If a DB selector is shown, this still works; fill the standard fields.
    try:
        page.fill("input[name='login']", USER, timeout=8000)
        page.fill("input[name='password']", PWD, timeout=8000)
        page.click("button[type='submit']", timeout=8000)
    except Exception as e:
        log("login form issue:", repr(e)[:160])
    # Odoo keeps a long-poll bus connection open, so "networkidle" never
    # fires. Wait for the web client navbar instead.
    try:
        page.wait_for_selector(".o_main_navbar", timeout=30000)
        log("login OK (navbar visible)")
    except Exception as e:
        log("post-login navbar NOT seen (login may have failed):",
            repr(e)[:120])
    page.wait_for_timeout(HOLD)


@scene
def s_dashboard(page):
    page.goto(URL + "/odoo/accounting", wait_until="domcontentloaded",
              timeout=60000)
    page.wait_for_timeout(HOLD)


@scene
def s_financial_reports(page):
    # Open the statements wizard from the Reporting menu, then run a few.
    open_app_menu(page, "Reporting")
    page.wait_for_timeout(BEAT)
    for label in ("Financial Statements", "Mumtaz Financial",
                  "Financial Report", "Statements"):
        try:
            click_text(page, label)
            break
        except Exception:
            continue
    page.wait_for_timeout(HOLD)
    # Try each report type + Print, holding on each so it's visible.
    for rpt in ("Profit", "Trial Balance", "Balance Sheet",
                "General Ledger", "Aged Receivable", "Aged Payable"):
        try:
            click_text(page, rpt)
            page.wait_for_timeout(HOLD)
        except Exception as e:
            log("  report option miss:", rpt, repr(e)[:90])


@scene
def s_vendor_wht(page):
    page.goto(URL + "/odoo/action-base.action_partner_form",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(BEAT)
    try:
        page.get_by_role("searchbox").first.fill(VENDOR)
        page.keyboard.press("Enter")
        page.wait_for_timeout(HOLD)
        click_text(page, VENDOR)
        page.wait_for_timeout(BEAT)
        click_text(page, "Accounting")   # the Accounting notebook tab
        page.wait_for_timeout(HOLD)
    except Exception as e:
        log("  vendor nav miss:", repr(e)[:120])


@scene
def s_payment_voucher(page):
    open_app_menu(page, "Payment / Receipt Voucher")
    page.wait_for_timeout(HOLD)
    try:
        # Party
        page.get_by_label("Party").fill(VENDOR, timeout=6000)
        page.wait_for_timeout(BEAT)
        page.keyboard.press("Enter")
        page.wait_for_timeout(BEAT)
    except Exception as e:
        log("  party fill miss:", repr(e)[:90])
    try:
        click_text(page, "Load Open Items")
        page.wait_for_timeout(HOLD)   # hold on the WHT columns
        page.wait_for_timeout(HOLD)
    except Exception as e:
        log("  load items miss:", repr(e)[:90])
    # NOTE: posting is left manual on purpose so the recording doesn't
    # create a live entry unattended. Set DEMO_POST=1 to auto-post.
    if os.environ.get("DEMO_POST") == "1":
        try:
            click_text(page, "Post Voucher")
            page.wait_for_timeout(HOLD)
        except Exception as e:
            log("  post miss:", repr(e)[:90])


@scene
def s_withholding_codes(page):
    open_app_menu(page, "Withholding")
    page.wait_for_timeout(BEAT)
    try:
        click_text(page, "Withholding Codes")
        page.wait_for_timeout(HOLD)
    except Exception as e:
        log("  wht codes miss:", repr(e)[:90])


def main():
    if not (USER and PWD):
        log("ERROR: set ODOO_USER and ODOO_PASSWORD env vars first.")
        return
    if os.path.isdir(OUT):
        shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=OUT,
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        login(page)
        s_dashboard(page)
        s_financial_reports(page)
        s_vendor_wht(page)
        s_payment_voucher(page)
        s_withholding_codes(page)
        s_dashboard(page)
        context.close()   # flushes the video file
        browser.close()
    webms = sorted(glob.glob(os.path.join(OUT, "*.webm")))
    if not webms:
        log("no video produced")
        return
    src = webms[-1]
    log("video:", src)
    if shutil.which("ffmpeg"):
        mp4 = os.path.join(OUT, "igsquare_demo.mp4")
        subprocess.run(["ffmpeg", "-y", "-i", src, "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", mp4],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("mp4:", mp4)
    else:
        log("ffmpeg not found; share the .webm or install ffmpeg for mp4")


if __name__ == "__main__":
    main()
