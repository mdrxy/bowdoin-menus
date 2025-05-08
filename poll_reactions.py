"""
Monitor a GroupMe message for new likes and trigger a callback function.
"""

import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

BOT_ID = os.getenv("BOT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
if not BOT_ID or not ACCESS_TOKEN or not GROUP_ID:
    raise ValueError(
        "Please set the BOT_ID, ACCESS_TOKEN, and GROUP_ID environment variables."
    )

logger.basicConfig(
    level=logger.DEBUG,
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d: %(message)s",
)
logger = logger.getLogger(__name__)


def like_callback(message, new_like_count, old_like_count):
    """
    Callback function to handle new likes on a message.
    """
    logger.info(
        "Message `%s` has new likes: now %d (was %d)",
        message.get("id"),
        new_like_count,
        old_like_count,
    )


def poll_message_for_likes(group_id, message_id, callback, poll_interval=30):
    """
    Polls the specified message in the group to detect new likes.

    Parameters:
    - group_id: the GroupMe group ID.
    - message_id: the ID of the message to watch.
    - callback: a function to call when new likes are detected.
    - poll_interval: time in seconds between polls.
    """
    last_like_count = 0
    base_url = (
        f"https://api.groupme.com/v3/groups/{group_id}/messages?token={ACCESS_TOKEN}"
    )

    while True:
        try:
            response = requests.get(base_url, timeout=10)
            if response.status_code != 200:
                logger.error("Error fetching messages: `%s`", response.status_code)
            else:
                data = response.json()
                messages = data.get("response", {}).get("messages", [])
                logger.debug("Fetched %d messages", len(messages))
                # Look for the specific message by ID
                for msg in messages:
                    if msg.get("id") == message_id:
                        current_like_count = len(msg.get("favorited_by", []))
                        if current_like_count > last_like_count:
                            callback(msg, current_like_count, last_like_count)
                            last_like_count = current_like_count
                        break
                else:
                    logger.warning(
                        "Message ID `%s` not found in the latest fetch.", message_id
                    )
        except requests.exceptions.RequestException as e:
            logger.error("Exception during polling: `%s`", e)

        time.sleep(poll_interval)


if __name__ == "__main__":
    MSG_ID = "174399734092226471"

    poll_message_for_likes(GROUP_ID, MSG_ID, like_callback, poll_interval=3)
