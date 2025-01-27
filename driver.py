"""
Module to retrieve and send the current menu for Moulton Union and Thorne Hall.
"""

import os
import datetime
import json
import re
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import requests
import logging

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION
# ----------------------------------------------------------------------
logging.basicConfig(
    # filename="./bowdoin_menus.log",
    filename="/home/wbor/bowdoin-menus/bowdoin_menus.log",  # for production
    filemode="a",  # or "w" to overwrite each run
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# ----------------------------------------------------------------------

load_dotenv()

botID = os.getenv("BOT_ID")
if not botID:
    raise ValueError("BOT_ID environment variable is missing or empty!")

MENU_API = "https://apps.bowdoin.edu/orestes/api.jsp"
GROUPME_API = "https://api.groupme.com/v3/bots/post"

# ----------------------------------------------------------------------
# CLOSED-STATE TRACKING
# ----------------------------------------------------------------------
CLOSED_STATE_FILE = "closed_state.txt"


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
    with open(CLOSED_STATE_FILE, "w") as f:
        f.write("CLOSED")


def clear_closed_message_state():
    """
    Removes the file if it exists, signifying that we can
    send the closed message again in the future if needed.
    """
    if os.path.isfile(CLOSED_STATE_FILE):
        logging.info("Removing closed-state file to allow future 'closed' messages.")
        os.remove(CLOSED_STATE_FILE)


# ----------------------------------------------------------------------


class Location:
    """
    Represents the location of the menu.
    """

    MOULTON = 48
    THORNE = 49


class Meals:
    """
    Represents the meal period.
    """

    BREAKFAST = "breakfast"
    BRUNCH = "brunch"
    LUNCH = "lunch"
    DINNER = "dinner"

    def get_upcoming_meal(self, location):
        """
        The next upcoming meal is set after the current meal expires.
        During a meal period, it is still 'upcoming'.
        Only handles whole hours, so 12:30 p.m. is rounded up to 1 p.m.
        """
        current_hour = datetime.datetime.now().time().hour
        current_day = datetime.datetime.now().strftime("%a").lower()
        logging.debug(
            f"Determining upcoming meal for location={location}, day={current_day}, hour={current_hour}."
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


def build_request(location):
    """
    Builds the request data to be sent to the menu API.
    """
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    meal = Meals().get_upcoming_meal(location)
    request_data = {
        "unit": {location},
        "date": {current_date},
        "meal": {meal},
    }
    logging.info(
        f"Building menu request for location={location}, date={current_date}, meal={meal}."
    )
    return request_data


def request(location):
    """
    Makes a POST request to the menu API.
    """
    data = build_request(location)
    logging.info(f"Sending POST request to the menu API for location={location}.")
    response = requests.post(MENU_API, data=data, timeout=10)
    if response.status_code == 200:
        logging.debug("Received a 200 OK from menu API.")
        return response.content
    logging.error("Error calling menu API: %s", response.status_code)
    return None


def parse_response(request_content):
    """
    Parses the XML response from the menu API and
    returns a dictionary like { 'Main Course': [...], 'Desserts': [...], ... }.
    If there's no data or an error is returned, we return None to indicate no menu.
    """
    logging.debug("Parsing XML response from the menu API.")
    root = ET.fromstring(request_content)

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

    return sorted_menu


def stringify(location, menu):
    """
    Converts the menu dictionary into a formatted string.
    If there's no menu (None or empty), returns an empty string.
    """
    if menu is None:
        logging.debug(f"No menu data for location={location}. Returning empty string.")
        return ""

    if not any(menu.values()):
        logging.debug(f"Menu dictionary is empty for location={location}.")
        return ""

    meal = Meals().get_upcoming_meal(location)
    timestamp = datetime.datetime.now().strftime("%d %b %Y")
    loc_name = "Moulton Union" if location == Location.MOULTON else "Thorne"

    output_string = f"{loc_name} {meal.capitalize()} - {timestamp}:\n\n"
    for category, items in menu.items():
        if items:
            output_string += f"{category}:\n"
            for item in items:
                if item:  # skip None or empty
                    output_string += f"- {item}\n"
            output_string += "\n"

    return output_string


def send_message(text):
    """
    Sends a message to GroupMe via POST.
    """
    logging.info("Sending message to GroupMe bot.")
    data = {"text": text, "bot_id": botID}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            GROUPME_API, data=json.dumps(data), headers=headers, timeout=10
        )
        if response.status_code != 202:
            logging.warning(f"GroupMe API responded with status {response.status_code}")
        else:
            logging.debug("Message accepted by GroupMe API.")
        return response
    except requests.exceptions.RequestException as e:
        logging.error("Error sending message to GroupMe: %s", e)
        return None


def get_now_playing():
    """
    Using WBOR's API, gets the currently playing song.

    https://api-1.wbor.org/spins/get
    """
    logging.info("Retrieving currently playing song from WBOR API.")
    try:
        response = requests.get("https://api-1.wbor.org/spins/get", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data["spin-0"]:
                song = data["spin-0"]["song"]
                artist = data["spin-0"]["artist"]
                return {"song": song, "artist": artist}
        logging.error("Error calling WBOR API: %s", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Error calling WBOR API: %s", e)
    return None


if __name__ == "__main__":
    logging.info("Starting the menu retrieval script.")

    # 1. Request the data for both halls
    thorne_xml = request(Location.THORNE)
    moulton_xml = request(Location.MOULTON)

    # 2. Parse both
    thorne_menu = parse_response(thorne_xml) if thorne_xml else None
    moulton_menu = parse_response(moulton_xml) if moulton_xml else None

    # 3. Convert both to text
    thorne_text = stringify(Location.THORNE, thorne_menu)
    moulton_text = stringify(Location.MOULTON, moulton_menu)

    # 4. Check if both are empty => "closed" logic
    if not thorne_text and not moulton_text:
        if not has_closed_message_already_been_sent():
            logging.info("Both dining halls appear closed, sending closed message.")
            send_message("The campus dining halls are closed.")
            set_closed_message_sent()
        else:
            logging.info(
                "Both dining halls still appear closed, but we've already sent the message."
            )
    else:
        logging.info("At least one dining hall has data => clearing closed state.")
        clear_closed_message_state()

        now_playing = get_now_playing()

        if thorne_text and moulton_text:
            logging.info("Both dining halls have menu data.")
            logging.info("Append now playing song info to Moulton's menu.")
            if now_playing:
                moulton_text += f"Now playing on WBOR.org: {now_playing['song']} by {now_playing['artist']}"
        else:
            logging.info("Only one dining hall has menu data.")
            logging.info(
                "Add the now playing song info to the menu of the hall that has data."
            )
            if now_playing:
                if thorne_text:
                    thorne_text += f"Now playing on WBOR.org: {now_playing['song']} by {now_playing['artist']}"
                if moulton_text:
                    moulton_text += f"Now playing on WBOR.org: {now_playing['song']} by {now_playing['artist']}"

        # If Thorne has menu text, send it
        if thorne_text:
            if len(thorne_text) < 1000:
                send_message(thorne_text)
            else:
                logging.warning(
                    "Thorne text is too long to send (>1000 chars). Printing locally."
                )
                print(thorne_text)

        # If Moulton has menu text, send it
        if moulton_text:
            if len(moulton_text) < 1000:
                send_message(moulton_text)
            else:
                logging.warning(
                    "Moulton text is too long to send (>1000 chars). Printing locally."
                )
                print(moulton_text)

    logging.info("Menu retrieval script finished.")
