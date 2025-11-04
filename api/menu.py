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
from models import Meals
from utils import make_post_request

logger = logging.getLogger(__name__)


def build_request(location_int: int) -> dict:
    """
    Builds the request data to be sent to the menu API.

    Parameters:
    - location (int): The location ID for the menu request.

    Returns:
    - dict: The request data containing the unit, date, and meal type.
    """
    now = datetime.datetime.now()

    # Correctly unpack the meal type string and the integer offset
    meal_name_str, date_offset_as_int = Meals().get_upcoming_meal(location_int)

    # Use the integer offset to calculate the target date
    target_date = now + datetime.timedelta(days=date_offset_as_int)
    request_date_str = target_date.strftime(
        "%Y%m%d"
    )  # This will now be the correct date

    request_data = {
        "unit": location_int,
        "date": request_date_str,  # Use the calculated, potentially future, date
        "meal": meal_name_str,  # Use only the meal name string here
    }
    logger.info(
        "Building menu request for location=`%s`, date=`%s`, meal=`%s`",
        location_int,
        request_date_str,  # Log the correct date
        meal_name_str,  # Log the meal name string
    )
    return request_data


def request(location_int: int) -> Union[bytes, None]:
    """
    Makes a POST request to the menu API with retry logic.

    Parameters:
    - location (Location): The location ID for the menu request.

    Returns:
    - bytes: The response content from the menu API, or None if an error
        occurs.
    """
    data = build_request(location_int)
    logger.info("Sending POST request to the menu API for location=`%s`", location_int)
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

    Parameters:
    - root (ET.Element): The root element of the XML response.

    Returns:
    - tuple: A tuple containing two lists:
        - course_values: A list of course names.
        - item_names: A list of item names.

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

    Parameters:
    - course_values (list): A list of course names.
    - item_names (list): A list of item names.

    Returns:
    - dict: A dictionary where keys are course names and values are
        lists of item names.
    """

    # Initialize the menu dictionary with unique meal course values as
    # keys and empty lists as values (to be populated with item names)
    menu: dict[str, list[str]] = {key: [] for key in set(course_values)}

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
    if not menu:
        logger.critical("Menu is empty after building from records...")
        return {}

    return menu


def sort_and_emoji_menu(menu: dict) -> Union[dict, None]:
    """
    Sorts menu keys (categories) to a custom order, and add
    corresponding emoji prefixes.

    Parameters:
    - menu (dict): The menu dictionary to be sorted and emoji'd.

    Returns:
    - dict: The sorted menu dictionary with emoji prefixes.
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
        "Beverages & Sides:": "➕",
        "Beverages": "🍻",
        "None": "⁉️",
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

    Parameters:
    - request_content (str): The XML response content from the menu API.

    Returns:
    - dict: The parsed menu dictionary with emoji prefixes, or None if
        an error occurs.
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
