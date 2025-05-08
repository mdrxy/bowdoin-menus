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

logger = logging.getLogger(__name__)


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
    logger.info(
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
    logger.info("Sending POST request to the menu API for location=`%s`", location)
    try:
        response = make_post_request(MENU_API, data)
        if response.status_code == 200:
            logger.debug("Received a 200 OK from menu API.")
            return response.content
        logger.error("Error calling menu API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logger.error("Failed to retrieve menu data: `%s`", e)
    return None


def extract_records(root: ET.Element) -> tuple:
    """
    Extracts course values and item names from the XML root. Returns a
    tuple: (course_values, item_names).

    Example:
    <record>
        <course>Main Course</course>
        <webLongName>Grilled Chicken</webLongName>
    </record>
    <record>
        <course>Desserts</course>
        <webLongName>Chocolate Cake</webLongName>
    </record>

    ->

    (
        ['Main Course', 'Desserts'],
        ['Grilled Chicken', 'Chocolate Cake']
    )
    """
    course_values = []
    item_names = []

    for record in root.findall(".//record"):

        # The course this item belongs to
        course_element = record.find("course")
        course_text = (
            course_element.text
            if course_element is not None
            else "Uncategorized Course"
        )

        # The name of the item
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

    # Initialize the menu dictionary with unique meal course values as
    # keys and empty lists as values (to be populated with item names)
    menu = {key: [] for key in set(course_values)}

    # Iterate over item names and their corresponding course values
    for idx, item in enumerate(item_names):
        if item:
            # Remove any consecutive spaces in item names
            # e.g. "Grilled  Chicken" -> "Grilled Chicken"
            item = re.sub(r"\s+", " ", item)

        # Append the cleaned item to the corresponding course in menu
        menu[course_values[idx]].append(item)

    # If any course has no items, remove it from the menu
    for key in list(menu.keys()):
        if not menu[key]:
            del menu[key]
    # If the menu is empty after removing empty courses, log a critical error
    if not menu:
        logger.critical("Menu is empty after building from records...")
        return None

    # Return the constructed menu dictionary
    return menu


def sort_and_emoji_menu(menu: dict) -> Union[dict, None]:
    """
    Sorts menu keys (categories) to a custom order, and add
    corresponding emoji prefixes.
    """
    custom_order = ["Main Course", "Desserts"]  # Desserts AFTER main
    sorted_menu = {key: menu[key] for key in custom_order if key in menu}
    for key in menu:
        if key not in sorted_menu:
            sorted_menu[key] = menu[key]
    if not any(sorted_menu.values()):
        logger.critical("Menu is empty after sorting...")
        return None

    # Add emojis to the menu keys
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
            # Substituting in the emoji'd version, removing the old key
            sorted_menu[emoji_map[key] + " " + key] = sorted_menu.pop(key)

    return sorted_menu


def parse_response(request_content: str) -> Union[dict, None]:
    """
    Parses the XML response from the menu API and returns a dictionary
    like:
    { '🍽️ Main Course': [...], '🍰 Desserts': [...], ... }.

    Returns None if no data or an error is encountered.
    """
    logger.debug("Parsing XML response from the menu API.")
    try:
        root = ET.fromstring(request_content)
    except ET.ParseError as e:
        logger.error("Failed to parse XML response: `%s`", e)
        return None

    if root.find(".//error") is not None:
        logger.info("No records found (or error) in the XML response.")
        return None

    course_values, item_names = extract_records(root)
    menu = build_menu(course_values, item_names)
    sorted_menu = sort_and_emoji_menu(menu)
    return sorted_menu
