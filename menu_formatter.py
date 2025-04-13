"""
Formatter module for formatting menu data and metadata fields.
"""

import datetime
import logging

from config import METADATA_FILTER
from models import Location, Meals


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


def clean_metadata_field(field_type: str, value: str) -> str:
    """
    Cleans up a single metadata field (artist, track) using
    music-metadata-filter.
    """
    if field_type not in ("artist", "track"):
        raise ValueError(f"Unsupported field_type: {field_type}")
    return METADATA_FILTER.filter_field(field_type, value).strip()
