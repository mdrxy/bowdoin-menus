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
        # Extract 'course' and 'formal_name' values from each 'record' element
        course_element = record.find("course")
        course = course_element.text if course_element is not None else "Uncategorized"
        web_long_name_element = record.find("webLongName")
        web_long_name = (
            web_long_name_element.text if web_long_name_element is not None else None
        )

        # Append the values to the respective lists
        course_values.append(course)
        item_names.append(web_long_name)

    menu = {key: [] for key in set(course_values)}

    i = 0
    for item in item_names:
        if item:  # Sometimes a NoneType item would be returned
            # Remove consecutive spaces from Strings
            item = re.sub(r"\s+", " ", item)
        menu[course_values[i]].append(item)
        i += 1

    custom_order = ["Main Course", "Desserts"]
    sorted_menu = {key: menu[key] for key in custom_order if key in menu}
    sorted_menu.update({key: menu[key] for key in menu if key not in sorted_menu})

    return sorted_menu


def stringify(location, menu):
    """
    Converts the menu dictionary into a formatted string.

    Parameters:
    - location: The location of the menu (Moulton or Thorne).
    - menu: The menu dictionary to be converted.
    """
    if menu is None:
        location_name = "Moulton Union" if location == Location.MOULTON else "Thorne"
        return f"No menu data available for {location_name}, sad :()"

    # Ensure the menu has at least one item
    if not any(menu.values()):
        return ""  # Return an empty string if the menu is empty

    meal = Meals().get_upcoming_meal(location)

    # Note that this is the timestamp from when the script is called
    # (not the date the menu is being served)
    timestamp = datetime.datetime.now().strftime("%d %b %Y")

    output_string = ""
    if location is Location.MOULTON:
        output_string += f"Moulton Union {meal.capitalize()} - {timestamp}:"
    if location is Location.THORNE:
        output_string += f"Thorne {meal.capitalize()} - {timestamp}:"
    output_string += "\n\n"

    for category, items in menu.items():
        if any(menu[category]):
            output_string += f"{category}:\n"
        for item in items:
            if item is not None:
                output_string += f"- {item}\n"
        if any(menu[category]):
            output_string += "\n"

    return output_string


def send_message(text):
    """
    POSTs a message to the GroupMe bot.

    Parameters:
    - text: The message to be sent.
    """
    data = {"text": text, "bot_id": botID}

    headers = {"Content-Type": "application/json"}

    response = requests.post(
        GROUPME_API, data=json.dumps(data), headers=headers, timeout=10
    )
    return response


if __name__ == "__main__":
    thorne = request(Location.THORNE)
    print("Thorne content:", thorne)
    thorneMenu = parse_response(thorne)

    moulton = request(Location.MOULTON)
    print("Moulton content:", moulton)
    moultonMenu = parse_response(moulton)

    # Handle Thorne Menu
    thorneText = stringify(Location.THORNE, thorneMenu)
    if thorneText and len(thorneText) < 1000:
        send_message(thorneText)
    else:
        print(thorneText)

    # Handle Moulton Menu
    moultonText = stringify(Location.MOULTON, moultonMenu)
    if moultonText and len(moultonText) < 1000:
        send_message(moultonText)
    else:
        print(moultonText)
