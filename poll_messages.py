import datetime
import logging
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

BOT_ID = os.getenv("BOT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
if not BOT_ID or not ACCESS_TOKEN or not GROUP_ID:
    raise ValueError(
        "Please set the BOT_ID, ACCESS_TOKEN, and GROUP_ID environment variables."
    )

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def fetch_previous_messages(api_url):
    """
    Fetch the previous 20 messages from the GroupMe messages endpoint.

    Logs the messages in chronological order (oldest first).
    """
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            logging.error("Error fetching messages: %s", response.status_code)
            return
        data = response.json()
        messages = data.get("response", {}).get("messages", [])
        if messages:
            # Process messages in chronological order (oldest first)
            for msg in reversed(messages):
                msg_id = msg.get("id")
                sender = msg.get("name", "Unknown Sender")
                text = msg.get("text", "")
                created = datetime.datetime.fromtimestamp(msg.get("created_at", 0))
                logging.info(
                    "Message `%s` from %s at %s: %s", msg_id, sender, created, text
                )
        else:
            logging.info("No messages returned from API.")
    except Exception as e:
        logging.error("Exception during request: %s", e)


if __name__ == "__main__":
    API_URL = f"https://api.groupme.com/v3/groups/{GROUP_ID}/messages?token={ACCESS_TOKEN}&limit=20"
    fetch_previous_messages(API_URL)
