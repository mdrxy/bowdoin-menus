"""
Module to retrieve and send the current menu for Moulton Union and
Thorne Hall.

Author: Mason Daugherty <@mdrxy>
Version: 1.1.1
Last Modified: 2025-04-06

Changelog:
    - 1.0.0 (2024-04-02): Initial release.
    - 1.1.0 (2024-04-06): Refactoring.
    - 1.1.1 (2025-04-07): Emoji support and WBOR song info.
    - 1.2.0 (2025-04-13): Refactoring
"""

import logging

import requests

from api.groupme import send_message
from api.menu import parse_response, request
from api.spinitron import (
    get_current_playlist_details,
    get_current_spin_details,
    get_persona_name,
)
from menu_formatter import clean_metadata_field, stringify
from models import Location
from state import (
    clear_closed_message_state,
    has_closed_message_already_been_sent,
    set_closed_message_sent,
)

# ----------------------------------------------------------------------


if __name__ == "__main__":
    logging.info("Starting the menu retrieval script...")

    thorne_xml = request(Location.THORNE)
    moulton_xml = request(Location.MOULTON)
    thorne_menu = parse_response(thorne_xml.decode("utf-8")) if thorne_xml else None
    moulton_menu = parse_response(moulton_xml.decode("utf-8")) if moulton_xml else None
    thorne_text = (
        stringify(Location.THORNE, thorne_menu) if thorne_menu is not None else ""
    )
    moulton_text = (
        stringify(Location.MOULTON, moulton_menu) if moulton_menu is not None else ""
    )

    # Check if both are empty => closed logic
    if not thorne_text and not moulton_text:
        if not has_closed_message_already_been_sent():
            logging.info("Both dining halls appear closed, sending closed message...")
            logging.debug("Full Thorne API response: %s", thorne_xml)
            logging.debug("Full Moulton API response: %s", moulton_xml)
            send_message("The campus dining halls seem to be closed.")
            set_closed_message_sent()
        else:
            logging.info(
                "Both dining halls still appear closed, but closed message has already been sent."
            )
    else:
        logging.info("At least one dining hall has data; clearing closed state...")
        clear_closed_message_state()

        try:
            now_playing = get_current_spin_details()
            playlist = get_current_playlist_details()
            CURRENTLY_AUTOMATED = bool(playlist.get("automation")) if playlist else None
            logging.debug("Currently playing automation: `%s`", CURRENTLY_AUTOMATED)
            PERSONA_ID = playlist.get("persona_id") if playlist else None
            PERSONA_NAME = get_persona_name(PERSONA_ID) if PERSONA_ID else None

            # Sanitize metadata using Amazon filter
            song_name = now_playing.get("song", "") if now_playing else ""
            artist_name = now_playing.get("artist", "") if now_playing else ""
            if song_name:
                song_name = clean_metadata_field("track", song_name)
            if artist_name:
                artist_name = clean_metadata_field("artist", artist_name)
            logging.debug(
                "Cleaned song name: `%s`, artist name: `%s`", song_name, artist_name
            )

            if playlist and CURRENTLY_AUTOMATED:
                logging.debug("Automation playlist detected; skipping song info.")
                SONG_INFO = ""
            elif now_playing and now_playing["elapsed"] <= 900:
                show_title = (
                    playlist["title"]
                    if playlist and "title" in playlist
                    else "Unknown Show"
                )
                SONG_INFO = (
                    "-------------------\n\n"
                    f"🎧 Now playing on WBOR(.org):\n\n"
                    f"🎤 {artist_name} - {song_name}\n\n"
                    f"▶️ on the show {show_title} with 👤 {PERSONA_NAME}"
                )
                logging.debug("Song info: `%s`", SONG_INFO)
            else:
                logging.debug("Some other condition; skipping song info.")
                SONG_INFO = ""
        except (
            KeyError,
            TypeError,
            ValueError,
            requests.exceptions.RequestException,
        ) as e:
            logging.error("Error retrieving or formatting WBOR song info: `%s`", e)
            SONG_INFO = ""
        except Exception as e:  # pylint: disable=broad-except
            logging.error("Unexpected error: `%s`", e)
            SONG_INFO = ""

        if SONG_INFO:
            logging.debug("Appending song info to menu text...")
            if thorne_text and moulton_text:
                logging.info(
                    "Both dining halls have menu data; appending song info to Moulton's menu."
                )
                moulton_text += SONG_INFO
            else:
                logging.info("Only one dining hall has menu data; appending song info.")
                if thorne_text:
                    thorne_text += SONG_INFO
                if moulton_text:
                    moulton_text += SONG_INFO

        for text, label in ((thorne_text, "Thorne"), (moulton_text, "Moulton")):
            if text:
                if len(text) < 1000:
                    if not send_message(text):
                        logging.error("Failed to send GroupMe message for `%s`", label)
                else:
                    logging.critical(
                        "`%s` text is too long to send (>1000 chars).",
                        label,
                    )
                    # Print so that we get an email from cron
                    print(f"{label} text is too long to send (>1000 chars).")
