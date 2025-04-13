"""
Handles sending messages to a GroupMe bot.
"""

import json
import logging
from typing import Union

import requests

from config import BOT_ID, GROUPME_API
from utils import make_post_request


def send_message(message_text: str) -> Union[requests.Response, None]:
    """
    Sends a message to GroupMe via POST with retry logic.
    """
    logging.info("Sending message to GroupMe bot.")
    data = {"text": message_text, "bot_id": BOT_ID}
    headers = {"Content-Type": "application/json"}
    try:
        response = make_post_request(GROUPME_API, json.dumps(data), headers=headers)
        if response.status_code != 202:
            logging.warning(
                "GroupMe API responded with status `%s`", response.status_code
            )
        return response
    except requests.exceptions.RequestException as e:
        logging.error("Error sending message to GroupMe: `%s`", e)
        return None
