"""
App config values and constants.
"""

import logging
import os

from dotenv import load_dotenv
from music_metadata_filter.filters import make_amazon_filter

# Load environment variables
load_dotenv()

BOT_ID = os.getenv("BOT_ID")
if not BOT_ID:
    raise ValueError("BOT_ID environment variable is missing or empty!")

SPINITRON_PROXY_BASE = os.getenv("SPINITRON_PROXY_BASE", "https://api-1.wbor.org/api")

MENU_API = os.getenv("MENU_API", "https://apps.bowdoin.edu/orestes/api.jsp")
GROUPME_API = os.getenv("GROUPME_API", "https://api.groupme.com/v3/bots/post")

METADATA_FILTER = make_amazon_filter()

# Closed state file
CLOSED_STATE_FILE = "closed_state.txt"

logging.basicConfig(
    filename="./bowdoin_menus.log",
    # filename="/home/wbor/bowdoin-menus/bowdoin_menus.log",  # for production
    filemode="a",  # change to "w" if desired
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
