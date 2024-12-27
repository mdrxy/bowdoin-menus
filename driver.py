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

# -- FILE-BASED CLOSED-STATE TRACKING --
CLOSED_STATE_FILE = "closed_state.txt"


def has_closed_message_already_been_sent():
    """
    Returns True if a file exists indicating we've already sent the
    'The campus dining halls are closed.' message.
    """
    return os.path.isfile(CLOSED_STATE_FILE)


def set_closed_message_sent():
    """
    Creates a file to indicate that we have already sent the 'closed' message.
    """
    with open(CLOSED_STATE_FILE, "w") as f:
        f.write("CLOSED\n")


def clear_closed_message_state():
    """
    Removes the file if it exists, signifying that the campus is
    not closed or has reopened for future checks.
    """
    if os.path.isfile(CLOSED_STATE_FILE):
        os.remove(CLOSED_STATE_FILE)


# --------------------------------------


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
        During a meal period, it is still "upcoming".
        Only handles full hours, so 12:30 p.m. is rounded up to 1 p.m.
        """

        current_hour = datetime.datetime.now().time().hour
        current_day = datetime.datetime.now().strftime("%a").lower()

        if location == Location.MOULTON:
            # Monday–Friday
            if current_day != "sat" and current_day != "sun":
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
            if current_day == "sat" or current_day == "sun":
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
            if current_day != "sat" and current_day != "sun":
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
            if current_day == "sat" or current_day == "sun":
                # Brunch: 11:00 a.m. to 1:30 p.m.
                if 0 <= current_hour < 14 or 20 <= current_hour < 24:
                    if current_day == "sun" and 20 <= current_hour < 24:
                        return Meals.BREAKFAST
                    return Meals.BRUNCH
                # Dinner:  5:00 p.m. to 7:30 p.m.
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
    print("Error:", response.status_code)


def parse_response(request_content):
    """
    Parses the XML response from the menu API.
    """
    root = ET.fromstring(request_content)

    # Check if the response contains an error
    error_element = root.find(".//error")
    if error_element is not None:
        error_message = error_element.text
        print(f"Error: {error_message}")
        return None  # Return None to indicate no menu data

    course_values = []
    item_names = []

    # Iterate over each 'record' element in the XML
    for record in root.findall(".//record"):
        # Extract 'course' and 'formal_name' values
        course_element = record.find("course")
        course = course_element.text if course_element is not None else "Uncategorized"
        web_long_name_element = record.find("webLongName")
        web_long_name = (
            web_long_name_element.text if web_long_name_element is not None else None
        )

        course_values.append(course)
        item_names.append(web_long_name)

    menu = {key: [] for key in set(course_values)}

    i = 0
    for item in item_names:
        # Sometimes a NoneType item would be returned; also remove consecutive spaces
        if item:
            item = re.sub(r"\s+", " ", item)
        menu[course_values[i]].append(item)
        i += 1

    # Sort keys to put certain categories on top
    custom_order = ["Main Course", "Desserts"]
    sorted_menu = {key: menu[key] for key in custom_order if key in menu}
    sorted_menu.update({key: menu[key] for key in menu if key not in sorted_menu})

    return sorted_menu


def stringify(location, menu):
    """
    Converts the menu dictionary into a formatted string.
    Returns an empty string if the menu is None or if there are no items.
    """

    # If None, interpret as "No menu data"
    if menu is None:
        return ""  # We return empty here so we don't auto-send "No menu data..."

    # If the menu is empty or no items, also return empty
    if not any(menu.values()):
        return ""

    # Otherwise, build the string
    meal = Meals().get_upcoming_meal(location)
    timestamp = datetime.datetime.now().strftime("%d %b %Y")

    if location is Location.MOULTON:
        location_name = "Moulton Union"
    else:
        location_name = "Thorne"

    output_string = f"{location_name} {meal.capitalize()} - {timestamp}:\n\n"
    for category, items in menu.items():
        if any(items):
            output_string += f"{category}:\n"
        for item in items:
            if item:
                output_string += f"- {item}\n"
        if any(items):
            output_string += "\n"

    return output_string


def send_message(text):
    """
    POSTs a message to the GroupMe bot.
    """
    data = {"text": text, "bot_id": botID}
    headers = {"Content-Type": "application/json"}

    response = requests.post(
        GROUPME_API, data=json.dumps(data), headers=headers, timeout=10
    )
    return response


if __name__ == "__main__":

    # 1. Request & parse menus
    thorne_data = request(Location.THORNE)
    moulton_data = request(Location.MOULTON)

    thorne_menu = parse_response(thorne_data) if thorne_data else None
    moulton_menu = parse_response(moulton_data) if moulton_data else None

    # 2. Convert each to a string, or empty if None/no items
    thorne_text = stringify(Location.THORNE, thorne_menu)
    moulton_text = stringify(Location.MOULTON, moulton_menu)

    # 3. Check if both are empty => Possibly send "closed" or do nothing
    if not thorne_text and not moulton_text:
        # Both are empty
        if not has_closed_message_already_been_sent():
            # Send "closed" message only if we haven't already
            send_message("The campus dining halls are closed.")
            set_closed_message_sent()
        else:
            # We have already announced it's closed, do nothing
            pass
    else:
        # At least one menu is present
        # Clear closed state so that if it happens in a future cycle again,
        # we can re-send the "closed" message
        clear_closed_message_state()

        # 4. Send whichever texts are non-empty
        if thorne_text and len(thorne_text) < 1000:
            send_message(thorne_text)
        elif thorne_text:  # If it is longer than 1000 or so, do something else
            print(thorne_text)

        if moulton_text and len(moulton_text) < 1000:
            send_message(moulton_text)
        elif moulton_text:
            print(moulton_text)
