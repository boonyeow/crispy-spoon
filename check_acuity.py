import os
from datetime import date

import requests


# ============================================================
# CONFIGURATION
# ============================================================
# You already have an appointment on 2026-11-17, so ONLY slots
# dated BEFORE that are worth alerting on.
#
# OWNER / APPOINTMENT_TYPE_ID come from the environment (set in the
# workflow's `env:`, or exported locally) so the same script can
# monitor any site without code changes. No defaults — they are required.
# CALENDAR_ID / TIMEZONE / cutoff are fixed for this monitor.

API_URL = "https://app.acuityscheduling.com/api/scheduling/v1/availability/times"

try:
    OWNER = os.environ["OWNER"]
except KeyError:
    raise SystemExit("ERROR: OWNER env var is required (Acuity owner key).")

try:
    APPOINTMENT_TYPE_ID = os.environ["APPOINTMENT_TYPE_ID"]
except KeyError:
    raise SystemExit("ERROR: APPOINTMENT_TYPE_ID env var is required.")

CALENDAR_ID = "any"
TIMEZONE = "Asia/Singapore"

BOOKING_URL = (
    f"https://app.acuityscheduling.com/schedule/{OWNER}/"
    f"appointment/{APPOINTMENT_TYPE_ID}/calendar/{CALENDAR_ID}"
)

# Exclusive cutoff: slots on/after this date are ignored.
EXISTING_APPOINTMENT_DATE = date(2026, 11, 17)


# ============================================================
# TELEGRAM (same secrets as check_hotel.py)
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram_message(message):
    """Send a message to Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("WARNING: TELEGRAM_TOKEN / TELEGRAM_CHAT_ID not set, skipping send.")
        return

    telegram_url = (
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    )

    response = requests.post(
        telegram_url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    response.raise_for_status()


# ============================================================
# ACUITY AVAILABILITY
# ============================================================

def today_in_singapore():
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime

        return datetime.now(ZoneInfo(TIMEZONE)).date()
    except Exception:
        return date.today()


def check_acuity():
    today = today_in_singapore()

    if today >= EXISTING_APPOINTMENT_DATE:
        print(
            f"Existing appointment date ({EXISTING_APPOINTMENT_DATE}) "
            f"reached/passed (today is {today}) — nothing earlier to watch for."
        )
        return

    # Sliding start: today, NOT a hardcoded date. A hardcoded startDate
    # 422s ("must not be before the current day") once it passes.
    start = today

    # Window: today .. day before your existing appointment (e.g. Nov 9..16).
    max_days = max((EXISTING_APPOINTMENT_DATE - start).days, 1)

    print(f"Checking Acuity availability from {start} for {max_days} day(s), "
          f"only slots BEFORE {EXISTING_APPOINTMENT_DATE}...")

    # No cookies/headers needed — verified 2026-11-09.
    # Only these query params are required.
    response = requests.get(
        API_URL,
        params={
            "owner": OWNER,
            "appointmentTypeId": APPOINTMENT_TYPE_ID,
            "calendarId": CALENDAR_ID,
            "startDate": start.isoformat(),
            "maxDays": str(max_days),
            "timezone": TIMEZONE,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    # --------------------------------------------------------
    # Parse slots: {"2026-11-14": [{"time": "2026-11-14T09:00:00+0800",
    #                               "slotsAvailable": 3}, ...]}
    # {} when fully booked.
    # --------------------------------------------------------
    slots = []

    if isinstance(data, dict):
        for day, entries in data.items():
            try:
                if date.fromisoformat(day[:10]) >= EXISTING_APPOINTMENT_DATE:
                    continue  # on/after Nov 17 — ignore
            except Exception:
                pass

            if not isinstance(entries, list):
                continue

            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                available = entry.get("slotsAvailable")
                if available is not None and int(available) <= 0:
                    continue

                slot_time = entry.get("time", "?")
                slots.append(f"{slot_time.replace('T', ' ')} ({available} left)")

    slots = sorted(slots)

    print(f"\nFound {len(slots)} slot(s) before {EXISTING_APPOINTMENT_DATE}:")

    for slot in slots:
        print(f"  - {slot}")

    # No seen-state persistence: slots are booked very quickly, so any
    # slot present on a check is worth alerting on immediately.
    if not slots:
        print("\nNo slots available.")
        return

    # ========================================================
    # EARLIER SLOT FOUND
    # ========================================================
    print("\n🚨 EARLIER SLOT FOUND!")

    message_lines = [
        "🚨 EARLIER ACUITY SLOT FOUND!",
        "",
        f"📅 You have an appointment on {EXISTING_APPOINTMENT_DATE},",
        "   but earlier slot(s) are now available:",
        "",
    ]

    for slot in slots[:50]:
        message_lines.append(f"• {slot}")

    if len(slots) > 50:
        message_lines.append(f"…and {len(slots) - 50} more")

    message_lines.extend([
        "",
        "👉 BOOK NOW:",
        BOOKING_URL,
    ])

    message = "\n".join(message_lines)

    print("\nTelegram message:")
    print(message)

    send_telegram_message(message)

    print("\nTelegram notification sent!")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    try:
        check_acuity()

    except Exception as error:
        print(f"ERROR: {error}")
        raise
