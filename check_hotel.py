import os
import time
import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_URL = "https://hoshinoresorts.com/api/rooms"

BOOKING_URL = (
    "https://hoshinoresorts.com/EN/hotels/0000000006/search"
    "?checkIn=2027%2F02%2F09&stay=2&a=4&b=0&c=0&d=0"
)

ROOMS_TO_CHECK = {
    "0000000023": "Standard Quadruple Room",
    "0000000007": "Family Quadruple Room",
    "0000000006": "Kids Quadruple Room",
}


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
VACANCY_THRESHOLD = int(os.environ["VACANCY_THRESHOLD"])

def send_telegram_message(message):
    """Send a message to Telegram."""

    telegram_url = (
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": False,
    }

    response = requests.post(
        telegram_url,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()


# ============================================================
# HOTEL AVAILABILITY
# ============================================================

def check_hotel():

    # Generate current Unix timestamp in milliseconds
    timestamp = str(int(time.time() * 1000))

    params = {
        "hotelId": "0000000006",
        "checkIn": "2027/02/09",
        "stayLength": "2",
        "adult": "4",
        "underTwelve": "0",
        "underSeven": "0",
        "underFour": "0",
        "lang": "EN",
        "_": timestamp,
    }

    print("Checking Hoshino Resorts availability...")
    print(f"Timestamp: {timestamp}")

    response = requests.get(
        API_URL,
        params=params,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )

    response.raise_for_status()

    data = response.json()

    # --------------------------------------------------------
    # Parse rooms
    # --------------------------------------------------------

    found_rooms = {}

    for room in data.get("roomList", []):

        room_id = room.get("roomId")

        if room_id in ROOMS_TO_CHECK:

            vacancy = room.get("vacancy", 0)

            # Make sure vacancy is treated as a number
            try:
                vacancy = int(vacancy)
            except (ValueError, TypeError):
                vacancy = 0

            found_rooms[room_id] = {
                "name": ROOMS_TO_CHECK[room_id],
                "vacancy": vacancy,
                "price": room.get("charge", {})
                .get("searchChargeDetail", {})
                .get("totalAllPriceStr"),
            }

    # --------------------------------------------------------
    # Make sure all requested rooms were found
    # --------------------------------------------------------

    for room_id, room_name in ROOMS_TO_CHECK.items():

        if room_id not in found_rooms:

            print(
                f"WARNING: Room {room_name} "
                f"({room_id}) was not found in API response."
            )

            found_rooms[room_id] = {
                "name": room_name,
                "vacancy": 0,
                "price": None,
            }

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print("\nAvailability:")

    for room_id, room in found_rooms.items():

        print(
            f"  {room['name']}: "
            f"vacancy={room['vacancy']}"
        )

    # --------------------------------------------------------
    # Check whether ANY room has vacancy
    # --------------------------------------------------------

    available_rooms = [
        room
        for room in found_rooms.values()
        if room["vacancy"] >= VACANCY_THRESHOLD
    ]

    if not available_rooms:

        print("\nNo vacancy found.")

        return

    # ========================================================
    # VACANCY FOUND
    # ========================================================

    print("\n🚨 VACANCY FOUND!")

    message_lines = [
        "🚨 HOSHINO TOMAMU VACANCY FOUND!",
        "",
        "📅 9 Feb 2027 – 11 Feb 2027",
        "👨‍👩‍👦 4 adults",
        "",
    ]

    for room_id, room in found_rooms.items():

        vacancy = room["vacancy"]

        if vacancy >= VACANCY_THRESHOLD:
            line = (
                f"🚨 {room['name']}: {vacancy}"
            )
        else:
            line = (
                f"❌ {room['name']}: 0"
            )

        message_lines.append(line)

    message_lines.extend([
        "",
        "👉 CHECK NOW:",
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
        check_hotel()

    except Exception as error:

        print(f"ERROR: {error}")

        # Re-raise the error so GitHub Actions
        # marks the run as failed.
        raise
