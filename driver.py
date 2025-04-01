"""
Module to retrieve and send the current menu for Moulton Union and
Thorne Hall.
"""

import datetime
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv
from music_metadata_filter.filters import make_amazon_filter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION
# ----------------------------------------------------------------------
logging.basicConfig(
    filename="./bowdoin_menus.log",
    # filename="/home/wbor/bowdoin-menus/bowdoin_menus.log",  # for production
    filemode="a",  # or "w" to overwrite each run
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# ----------------------------------------------------------------------

load_dotenv()

BOT_ID = os.getenv("BOT_ID")
if not BOT_ID:
    raise ValueError("BOT_ID environment variable is missing or empty!")

SPINITRON_PROXY_BASE = os.getenv("SPINITRON_PROXY_BASE", "https://api-1.wbor.org/api")
if not SPINITRON_PROXY_BASE:
    RETURN_SONG = False
else:
    RETURN_SONG = True

MENU_API = os.getenv("MENU_API", "https://apps.bowdoin.edu/orestes/api.jsp")
GROUPME_API = os.getenv("GROUPME_API", "https://api.groupme.com/v3/bots/post")

METADATA_FILTER = make_amazon_filter()

# ----------------------------------------------------------------------
# CLOSED-STATE TRACKING
# ----------------------------------------------------------------------
CLOSED_STATE_FILE = "closed_state.txt"


# ----------------------------------------------------------------------
# RETRY DECORATOR FOR HTTP REQUESTS
# ----------------------------------------------------------------------
@retry(
    wait=wait_exponential(
        multiplier=1, min=2, max=10
    ),  # Exponential backoff (2s, 4s, 8s...)
    stop=stop_after_attempt(3),  # Stop after 3 failed attempts
    retry=retry_if_exception_type(
        requests.exceptions.RequestException
    ),  # Retry on request failures
)
def make_post_request(url, data, headers=None, timeout=10):
    """Helper function to make a POST request with retry logic."""
    return requests.post(url, data=data, headers=headers, timeout=timeout)


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
)
def make_get_request(url, timeout=10):
    """Helper function to make a GET request with retry logic."""
    return requests.get(url, timeout=timeout)


# ----------------------------------------------------------------------


def has_closed_message_already_been_sent():
    """
    Returns True if a file exists indicating we've already sent the
    'The campus dining halls are closed.' message.
    """
    return os.path.isfile(CLOSED_STATE_FILE)


def set_closed_message_sent():
    """
    Creates a file to indicate that we have sent the 'closed' message.
    """
    logging.info("Setting closed-state file to mark 'closed' message as sent.")
    with open(CLOSED_STATE_FILE, "w", encoding="utf-8") as f:
        f.write("CLOSED")


def clear_closed_message_state():
    """
    Removes the file if it exists, signifying that we can send the
    closed message again in the future if needed.
    """
    if Path(CLOSED_STATE_FILE).exists():
        logging.info("Removing closed-state file to allow future 'closed' messages.")
        os.remove(CLOSED_STATE_FILE)


# ----------------------------------------------------------------------


class Location:
    """
    Menu ID for a physical location.
    """

    MOULTON = 48
    THORNE = 49


class Meals:
    """
    Meal periods.
    """

    BREAKFAST = "breakfast"
    BRUNCH = "brunch"
    LUNCH = "lunch"
    DINNER = "dinner"

    def get_upcoming_meal(self, location: Location):
        """
        The next upcoming meal is set after the current meal expires.
        During a meal period, it is still 'upcoming'.
        Only handles whole hours, so 12:30 p.m. is rounded up to 1 p.m.
        """
        current_hour = datetime.datetime.now().time().hour
        current_day = datetime.datetime.now().strftime("%a").lower()
        logging.debug(
            "Determining upcoming meal for location=`%s`, day=`%s`, hour=`%s`.",
            location,
            current_day,
            current_hour,
        )

        if location == Location.MOULTON:
            # Monday–Friday
            if current_day not in ["sat", "sun"]:
                # Breakfast: 7:00 a.m. to 10:00 a.m.
                if 0 <= current_hour < 10 or 19 <= current_hour < 24:
                    if current_day == "fri" and 19 <= current_hour < 24:
                        return Meals.BRUNCH
                    else:
                        return Meals.BREAKFAST
                # Lunch: 11:00 a.m. to 2:00 p.m.
                if 10 <= current_hour < 14:
                    return Meals.LUNCH
                # Dinner: 5:00 p.m. to 7:00 p.m.
                if 14 <= current_hour < 19:
                    return Meals.DINNER

            # Saturday–Sunday
            if current_day in ["sat", "sun"]:
                # Breakfast: 8:00 a.m. to 11:00 a.m.
                if 0 <= current_hour < 11 or 19 <= current_hour < 24:
                    if current_day == "sun" and 19 <= current_hour < 24:
                        return Meals.BREAKFAST
                    return Meals.BRUNCH
                # Brunch: 11:00 a.m. to 12:30 p.m.
                if 11 <= current_hour < 13:
                    return Meals.LUNCH
                # Dinner: 5:00 p.m. to 7:00 p.m.
                if 13 <= current_hour < 19:
                    return Meals.DINNER

        if location == Location.THORNE:
            # Monday–Friday
            if current_day not in ["sat", "sun"]:
                # Breakfast: 8:00 a.m. to 10:00 a.m.
                if 0 <= current_hour < 10 or 20 <= current_hour < 24:
                    if current_day == "fri" and 20 <= current_hour < 24:
                        return Meals.BRUNCH
                    else:
                        return Meals.BREAKFAST
                # Lunch: 11:30 a.m. to 2:00 p.m.
                if 10 <= current_hour < 14:
                    return Meals.LUNCH
                # Dinner: 5:00 p.m. to 8:00 p.m.
                if 14 <= current_hour < 20:
                    return Meals.DINNER

            # Saturday–Sunday
            if current_day in ["sat", "sun"]:
                # Brunch: 11:00 a.m. to 1:30 p.m.
                if 0 <= current_hour < 14 or 20 <= current_hour < 24:
                    if current_day == "sun" and 20 <= current_hour < 24:
                        return Meals.BREAKFAST
                    return Meals.BRUNCH
                # Dinner: 5:00 p.m. to 7:30 p.m.
                if 14 <= current_hour < 20:
                    return Meals.DINNER

        # If we got here without returning, fallback to breakfast
        logging.debug("Meal not found in normal schedule, defaulting to BREAKFAST.")
        return Meals.BREAKFAST


def build_request(location: Location) -> dict:
    """
    Builds the request data to be sent to the menu API.
    """
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    meal = Meals().get_upcoming_meal(location)
    request_data = {
        "unit": location,
        "date": current_date,
        "meal": meal,
    }
    logging.info(
        "Building menu request for location=`%s`, date=`%s`, meal=`%s`.",
        location,
        current_date,
        meal,
    )
    return request_data


def request(location: Location) -> str:
    """
    Makes a POST request to the menu API with retry logic.
    """
    data = build_request(location)
    logging.info("Sending POST request to the menu API for location=`%s`.", location)

    try:
        response = make_post_request(MENU_API, data)
        if response.status_code == 200:
            logging.debug("Received a 200 OK from menu API.")
            return response.content
        logging.error("Error calling menu API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Failed to retrieve menu data: `%s`", e)

    return None


def parse_response(request_content: str) -> dict:
    """
    Parses the XML response from the menu API and
    returns a dictionary like:
    { 'Main Course': [...], 'Desserts': [...], ... }.

    If there's no data or an error is returned, we return None to
    indicate no menu.
    """
    logging.debug("Parsing XML response from the menu API.")

    try:
        root = ET.fromstring(request_content)
    except ET.ParseError as e:
        logging.error("Failed to parse XML response: `%s`", e)
        return None

    # Check if the response contains an <error> node with "No records found"
    error_element = root.find(".//error")
    if error_element is not None:
        logging.info("No records found (or error) in the XML response.")
        return None

    course_values = []
    item_names = []

    for record in root.findall(".//record"):
        course_element = record.find("course")
        course = course_element.text if course_element is not None else "Uncategorized"

        web_long_name_element = record.find("webLongName")
        web_long_name = (
            web_long_name_element.text if web_long_name_element is not None else None
        )

        course_values.append(course)
        item_names.append(web_long_name)

    # Build a dict with keys = courses
    menu = {key: [] for key in set(course_values)}

    # Populate items
    for idx, item in enumerate(item_names):
        # Clean up consecutive spaces
        if item:
            item = re.sub(r"\s+", " ", item)
        course_key = course_values[idx]
        menu[course_key].append(item)

    # Sort keys to place certain categories on top
    custom_order = ["Main Course", "Desserts"]
    sorted_menu = {key: menu[key] for key in custom_order if key in menu}
    # Add any other categories afterward
    for key in menu:
        if key not in sorted_menu:
            sorted_menu[key] = menu[key]

    # If there's absolutely nothing in sorted_menu, treat as None
    if not any(sorted_menu.values()):
        logging.info("Menu is empty after sorting.")
        return None

    # Add emojis before category headers
    for key in list(sorted_menu.keys()):
        if key == "Main Course":
            sorted_menu["🍽️ " + key] = sorted_menu.pop(key)
        elif key == "Desserts":
            sorted_menu["🍰 " + key] = sorted_menu.pop(key)
        elif key == "Starches":
            sorted_menu["🍚 " + key] = sorted_menu.pop(key)
        elif key == "Vegetables":
            sorted_menu["🥦 " + key] = sorted_menu.pop(key)
        elif key == "Soup":
            sorted_menu["🍲 " + key] = sorted_menu.pop(key)
        elif key == "Salads":
            sorted_menu["🥗 " + key] = sorted_menu.pop(key)
        elif key == "Breads":
            sorted_menu["🍞 " + key] = sorted_menu.pop(key)
        elif key == "Condiments":
            sorted_menu["🧂 " + key] = sorted_menu.pop(key)
        elif key == "Vegan Entree":
            sorted_menu["🌱 " + key] = sorted_menu.pop(key)
        elif key == "Deli":
            sorted_menu["🥪 " + key] = sorted_menu.pop(key)
        elif key == "Express Meal":
            sorted_menu["🥡 " + key] = sorted_menu.pop(key)
        elif key == "Display":
            sorted_menu["👀 " + key] = sorted_menu.pop(key)

    return sorted_menu


def stringify(location: Location, menu: dict) -> str:
    """
    Converts the menu dictionary into a formatted string. If there's no
    menu (None or empty), returns an empty string.
    """
    if menu is None:
        logging.debug(
            "No menu data for location=`%s`. Returning empty string.", location
        )
        return ""

    if not any(menu.values()):
        logging.debug("Menu dictionary is empty for location=`%s`.", location)
        return ""

    meal = Meals().get_upcoming_meal(location)
    timestamp = datetime.datetime.now().strftime("%d %b %Y")
    loc_name = "🏠 Moulton Union" if location == Location.MOULTON else "🌲 Thorne"

    output_string = f"{loc_name} {meal.capitalize()} - {timestamp}:\n\n"
    for category, items in menu.items():
        if items:
            output_string += f"{category}:\n"
            for item in items:
                if item:  # skip None or empty
                    output_string += f"- {item}\n"
            output_string += "\n"

    return output_string


def send_message(message_text: str) -> requests.Response:
    """
    Sends a message to GroupMe via POST with retry logic.
    """
    logging.info("Sending message to GroupMe bot.")
    data = {"text": message_text, "bot_id": BOT_ID}
    headers = {"Content-Type": "application/json"}
    try:
        response = make_post_request(GROUPME_API, json.dumps(data), headers=headers)
        if response.status_code != 202:
            logging.warning(
                "GroupMe API responded with status `%s`", response.status_code
            )
        return response
    except requests.exceptions.RequestException as e:
        logging.error("Error sending message to GroupMe: `%s`", e)
        return None


def get_current_spin_details() -> dict:
    """
    Get the most recent spin from a Spinitron API proxy (WBOR's) with
    retry logic.
    """
    url = SPINITRON_PROXY_BASE + "/spins"
    logging.info("Retrieving currently playing song from `%s`", url)
    try:
        response = make_get_request(url)
        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logging.error("Failed to parse JSON from Spinitron: %s", e)
                return None
            spins = data.get("items", [])
            logging.debug("Received %d spins", len(spins))
            if not spins:
                logging.info("No spins found in response")
                return None

            current_spin = spins[0]
            song = current_spin.get("song")
            artist = current_spin.get("artist")
            if not current_spin or not song or not artist:
                logging.warning("Data missing from Spinitron response!")
                return None

            duration_s = current_spin.get("duration", 0)
            start = current_spin.get("start", 0)
            try:
                start_time = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError as e:
                logging.error("Error parsing start time `%s`: `%s`", start, e)
                return None

            elapsed_s = int(
                (
                    datetime.datetime.now(datetime.timezone.utc) - start_time
                ).total_seconds()
            )
            logging.debug(
                "Current spin - song: `%s`, artist: `%s`, duration: `%s`, elapsed: `%s`",
                song,
                artist,
                duration_s,
                elapsed_s,
            )
            return {
                "song": song,
                "artist": artist,
                "duration": duration_s,
                "elapsed": elapsed_s,
            }
        logging.error("Error calling WBOR API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Error calling WBOR API: `%s`", e)
    return None


def get_persona_name(p_id: int) -> str:
    """
    Get the persona name from an ID using a Spinitron API proxy (WBOR's) with retry logic.
    """
    if not isinstance(p_id, int):
        logging.warning("Invalid persona ID: %s", p_id)
        return None

    url = SPINITRON_PROXY_BASE + f"/personas/{p_id}"
    logging.info("Retrieving persona name from `%s`", url)
    try:
        response = make_get_request(url)
        if response.status_code == 200:
            data = response.json()
            name = data.get("name")
            if not name:
                logging.warning("Data missing from Spinitron response!")
                return None
            logging.debug("Retrieved persona name: `%s`", name)
            return name
        logging.error("Error calling WBOR API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Error calling WBOR API: `%s`", e)
    return None


def get_current_playlist_details() -> dict:
    """
    Get the most recent playlist from a Spinitron API proxy (WBOR's) with retry logic.
    """
    url = SPINITRON_PROXY_BASE + "/playlists"
    logging.info("Retrieving currently playing playlist from `%s`", url)
    try:
        response = make_get_request(url)
        if response.status_code == 200:
            data = response.json()
            playlists = data.get("items", [])
            logging.debug("Received %d playlists", len(playlists))
            if not playlists:
                logging.info("No playlists found in response")
                return None

            current_playlist = playlists[0]
            title = current_playlist.get("title")
            p_id = current_playlist.get("persona_id")
            is_automated = current_playlist.get("automation")
            if not current_playlist or not title or is_automated is None:
                logging.warning("Data missing from Spinitron response!")
                logging.debug(
                    "Current playlist - title: `%s`, persona_id: `%s`, automation: `%s`",
                    title,
                    p_id,
                    is_automated,
                )
                return None
            logging.debug(
                "Current playlist - title: `%s`, persona_id: `%s`, automation: `%s`",
                title,
                p_id,
                is_automated,
            )
            return {
                "title": title,
                "persona_id": p_id,
                "automation": is_automated,
            }
        logging.error("Error calling WBOR API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Error calling WBOR API: `%s`", e)
    return None


def clean_metadata_field(field_type: str, value: str) -> str:
    """
    Cleans up a single metadata field (artist, track) using music-metadata-filter.
    """
    if field_type not in ("artist", "track"):
        raise ValueError(f"Unsupported field_type: {field_type}")
    return METADATA_FILTER.filter_field(field_type, value).strip()


if __name__ == "__main__":
    logging.info("Starting the menu retrieval script...")

    thorne_xml = request(Location.THORNE)
    moulton_xml = request(Location.MOULTON)
    thorne_menu = parse_response(thorne_xml) if thorne_xml else None
    moulton_menu = parse_response(moulton_xml) if moulton_xml else None
    thorne_text = stringify(Location.THORNE, thorne_menu)
    moulton_text = stringify(Location.MOULTON, moulton_menu)

    # Check if both are empty => closed logic
    if not thorne_text and not moulton_text:
        if not has_closed_message_already_been_sent():
            logging.info("Both dining halls appear closed, sending closed message...")
            send_message("The campus dining halls seem to be closed.")
            set_closed_message_sent()
        else:
            logging.info(
                "Both dining halls still appear closed, but closed message has already been sent."
            )
    else:
        logging.info("At least one dining hall has data; clearing closed state...")
        clear_closed_message_state()

        try:
            now_playing = get_current_spin_details()
            playlist = get_current_playlist_details()
            CURRENTLY_AUTOMATED = bool(playlist.get("automation")) if playlist else None
            logging.debug("Currently playing automation: `%s`", CURRENTLY_AUTOMATED)
            PERSONA_ID = playlist.get("persona_id") if playlist else None
            PERSONA_NAME = get_persona_name(PERSONA_ID) if PERSONA_ID else None

            # Sanitize metadata using Amazon filter
            song_name = now_playing.get("song", "")
            artist_name = now_playing.get("artist", "")
            if song_name:
                song_name = clean_metadata_field("track", song_name)
            if artist_name:
                artist_name = clean_metadata_field("artist", artist_name)
            logging.debug(
                "Cleaned song name: `%s`, artist name: `%s`", song_name, artist_name
            )

            if playlist and CURRENTLY_AUTOMATED:
                logging.debug("Automation playlist detected; skipping song info.")
                SONG_INFO = ""
            elif now_playing and now_playing["elapsed"] <= 900:
                SONG_INFO = (
                    "-------------------\n\n"
                    f"🎧 Now playing on WBOR(.org):\n\n"
                    f"🎤 {artist_name} - {song_name}\n\n"
                    f"▶️ on the show {playlist['title']} with 👤 {PERSONA_NAME}"
                )
                logging.debug("Song info: `%s`", SONG_INFO)
            else:
                logging.debug("Some other condition; skipping song info.")
                SONG_INFO = ""
        except (
            KeyError,
            TypeError,
            ValueError,
            requests.exceptions.RequestException,
        ) as e:
            logging.error("Error retrieving or formatting WBOR song info: %s", e)
            SONG_INFO = ""
        except Exception as e:  # pylint: disable=broad-except
            logging.error("Unexpected error: %s", e)
            SONG_INFO = ""

        if SONG_INFO:
            logging.debug("Appending song info to menu text...")
            if thorne_text and moulton_text:
                logging.info(
                    "Both dining halls have menu data; appending song info to Moulton's menu."
                )
                moulton_text += SONG_INFO
            else:
                logging.info("Only one dining hall has menu data; appending song info.")
                if thorne_text:
                    thorne_text += SONG_INFO
                if moulton_text:
                    moulton_text += SONG_INFO

        for text, label in ((thorne_text, "Thorne"), (moulton_text, "Moulton")):
            if text:
                if len(text) < 1000:
                    if not send_message(text):
                        logging.error("Failed to send GroupMe message for `%s`", label)
                else:
                    logging.critical(
                        "`%s` text is too long to send (>1000 chars).",
                        label,
                    )
                    # Print so that we get an email from cron
                    print(f"{label} text is too long to send (>1000 chars).")
