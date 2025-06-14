"""
Formatter module for formatting menu data and metadata fields.
"""

import datetime
import logging

from config import METADATA_FILTER
from models import Location, Meals

logger = logging.getLogger(__name__)


def stringify(location_int: int, menu: dict) -> str:
    """
    Converts the menu dictionary into a formatted string. If there's no
    menu (None or empty), returns an empty string.
    """
    if not menu or not any(menu.values()):
        logger.debug("Menu dictionary is empty for location=`%s`.", location_int)
        return ""

    meal_name_str, _ = Meals().get_upcoming_meal(location_int)

    timestamp = datetime.datetime.now().strftime("%d %b %Y")

    # Compare location_int with the integer constants from the Location class
    loc_name = "🏠 Moulton Union" if location_int == Location.MOULTON else "🌲 Thorne"

    # Use the meal_name_str (which is a string) for capitalize()
    output_string = f"{loc_name} {meal_name_str.capitalize()} - {timestamp}:\n\n"

    for category, items in menu.items():
        # Drop `None``, empty string, whitespace-only
        real_items = [i for i in items if i and i.strip()]
        if not real_items:
            # Genuinely empty; skip entirely
            continue

        output_string += f"{category}:\n"
        for item in real_items:
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
