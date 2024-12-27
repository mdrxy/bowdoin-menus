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

load_dotenv()

botID = os.getenv("BOT_ID")
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
    with open(CLOSED_STATE_FILE, "w") as f:
        f.write("CLOSED")


def clear_closed_message_state():
    """
    Removes the file if it exists, signifying that we can
    send the closed message again in the future if needed.
    """
    if os.path.isfile(CLOSED_STATE_FILE):
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

        if location == Location.MOULTON:
            # Monday–Friday
            if current_day not in ["sat", "sun"]:
                # Breakfast: 7:00 a.m. to 10:00 a.m.
                if 0 <= current_hour < 10 or 19 <= current_hour < 24:
                    # Late Friday transitions to Brunch (Sat)
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
                    # Late Sunday transitions to Breakfast (Mon)?
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


def build_request(location):
    """
    Builds the request data to be sent to the menu API.
    """
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    location_unit = location

    request_data = {
        "unit": {location_unit},
        "date": {current_date},
        "meal": {Meals().get_upcoming_meal(location)},
    }
    return request_data


def request(location):
    """
    Makes a POST request to the menu API.
    """
    response = requests.post(MENU_API, data=build_request(location), timeout=10)
    if response.status_code == 200:
        return response.content
    print("Error calling menu API:", response.status_code)
    return None


def parse_response(request_content):
    """
    Parses the XML response from the menu API and
    returns a dictionary like { 'Main Course': [...], 'Desserts': [...], ... }.
    If there's no data or an error is returned, we return None to indicate no menu.
    """
    root = ET.fromstring(request_content)

    # Check if the response contains an <error> node with "No records found"
    error_element = root.find(".//error")
    if error_element is not None:
        # If "No records found" then just return None (meaning empty menu)
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
        return None

    return sorted_menu


def stringify(location, menu):
    """
    Converts the menu dictionary into a formatted string.
    If there's no menu (None or empty), returns an empty string.
    """
    if menu is None:
        # Return empty string, meaning "no data"
        return ""

    if not any(menu.values()):
        # Also empty
        return ""

    meal = Meals().get_upcoming_meal(location)
    timestamp = datetime.datetime.now().strftime("%d %b %Y")

    # Format the header
    loc_name = "Moulton Union" if location == Location.MOULTON else "Thorne"
    output_string = f"{loc_name} {meal.capitalize()} - {timestamp}:\n\n"

    # Add each category and items
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
    data = {"text": text, "bot_id": botID}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            GROUPME_API, data=json.dumps(data), headers=headers, timeout=10
        )
        return response
    except requests.exceptions.RequestException as e:
        print("Error sending message:", e)
        return None


if __name__ == "__main__":
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
        # Both empty => possibly "closed"
        if not has_closed_message_already_been_sent():
            # We haven't announced closed yet => do it once
            send_message("The campus dining halls are closed.")
            set_closed_message_sent()
        else:
            # Already announced => do nothing
            pass
    else:
        # At least one has data => clear the "closed" state
        clear_closed_message_state()

        # If Thorne has menu text, send it
        if thorne_text and len(thorne_text) < 1000:
            send_message(thorne_text)
        elif thorne_text:
            # If it's >1000 chars, do something else (like chunk it), or just print for debugging
            print(thorne_text)

        # If Moulton has menu text, send it
        if moulton_text and len(moulton_text) < 1000:
            send_message(moulton_text)
        elif moulton_text:
            print(moulton_text)
