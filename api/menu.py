"""
Handles the menu API requests and responses.
"""

import datetime
import logging
import re
import xml.etree.ElementTree as ET
from typing import Union

import requests

from config import MENU_API
from models import Location, Meals
from utils import make_post_request


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
        "Building menu request for location=`%s`, date=`%s`, meal=`%s`",
        location,
        current_date,
        meal,
    )
    return request_data


def request(location: Location) -> Union[bytes, None]:
    """
    Makes a POST request to the menu API with retry logic.
    """
    data = build_request(location)
    logging.info("Sending POST request to the menu API for location=`%s`", location)
    try:
        response = make_post_request(MENU_API, data)
        if response.status_code == 200:
            logging.debug("Received a 200 OK from menu API.")
            return response.content
        logging.error("Error calling menu API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Failed to retrieve menu data: `%s`", e)
    return None


def extract_records(root: ET.Element) -> tuple:
    """
    Extracts course values and item names from the XML root. Returns a
    tuple: (course_values, item_names).
    """
    course_values = []
    item_names = []
    for record in root.findall(".//record"):
        course_element = record.find("course")
        course_text = (
            course_element.text if course_element is not None else "Uncategorized"
        )
        web_long_name_element = record.find("webLongName")
        item = web_long_name_element.text if web_long_name_element is not None else None
        course_values.append(course_text)
        item_names.append(item)
    return course_values, item_names


def build_menu(course_values: list, item_names: list) -> dict:
    """
    Builds a menu dictionary from course_values and item_names. Cleans
    up consecutive spaces in item names.
    """
    menu = {key: [] for key in set(course_values)}
    for idx, item in enumerate(item_names):
        if item:
            item = re.sub(r"\s+", " ", item)
        menu[course_values[idx]].append(item)
    return menu


def sort_and_emoji_menu(menu: dict) -> Union[dict, None]:
    """
    Sorts menu keys so that custom ordered categories come first, and
    adds corresponding emoji prefixes.
    """
    custom_order = ["Main Course", "Desserts"]
    sorted_menu = {key: menu[key] for key in custom_order if key in menu}
    for key in menu:
        if key not in sorted_menu:
            sorted_menu[key] = menu[key]
    if not any(sorted_menu.values()):
        logging.info("Menu is empty after sorting.")
        return None
    emoji_map = {
        "Main Course": "🍽️",
        "Desserts": "🍰",
        "Starches": "🍚",
        "Vegetables": "🥦",
        "Soup": "🍲",
        "Salads": "🥗",
        "Breads": "🍞",
        "Condiments": "🧂",
        "Vegan Entree": "🌱",
        "Deli": "🥪",
        "Express Meal": "🥡",
        "Display": "👀",
        "Other": "❓",
        "Passover": "🍷",
        "Appetizer/ Fruit/ Juices:": "🍏",
    }
    for key in list(sorted_menu.keys()):
        if key in emoji_map:
            sorted_menu[emoji_map[key] + " " + key] = sorted_menu.pop(key)
    return sorted_menu


def parse_response(request_content: str) -> Union[dict, None]:
    """
    Parses the XML response from the menu API and returns a dictionary
    like:
    { '🍽️ Main Course': [...], '🍰 Desserts': [...], ... }.

    Returns None if no data or an error is encountered.
    """
    logging.debug("Parsing XML response from the menu API.")
    try:
        root = ET.fromstring(request_content)
    except ET.ParseError as e:
        logging.error("Failed to parse XML response: `%s`", e)
        return None

    if root.find(".//error") is not None:
        logging.info("No records found (or error) in the XML response.")
        return None

    course_values, item_names = extract_records(root)
    menu = build_menu(course_values, item_names)
    sorted_menu = sort_and_emoji_menu(menu)
    return sorted_menu
