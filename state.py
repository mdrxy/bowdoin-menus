"""
Track the state of whether we've sent the 'closed' message.
"""

import logging
import os
from pathlib import Path

from config import CLOSED_STATE_FILE


def has_closed_message_already_been_sent():
    """
    Returns True if a file exists indicating we've already sent the
    'The campus dining halls are closed.' message.
    """
    return os.path.isfile(CLOSED_STATE_FILE)


def set_closed_message_sent():
    """
    Creates a file to indicate that we have sent the 'closed' message.
    """
    logging.info("Setting closed-state file to mark 'closed' message as sent.")
    with open(CLOSED_STATE_FILE, "w", encoding="utf-8") as f:
        f.write("CLOSED")


def clear_closed_message_state():
    """
    Removes the file if it exists, signifying that we can send the
    closed message again in the future if needed.
    """
    if Path(CLOSED_STATE_FILE).exists():
        logging.info("Removing closed-state file to allow future 'closed' messages.")
        os.remove(CLOSED_STATE_FILE)
