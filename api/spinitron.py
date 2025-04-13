"""
Handles Spinitron API calls.
"""

import datetime
import json
import logging
from typing import Union

import requests

from config import SPINITRON_PROXY_BASE
from utils import make_get_request


def get_current_spin_details() -> Union[dict, None]:
    """
    Get the most recent spin from a Spinitron API proxy (WBOR's) with
    retry logic.
    """
    url = SPINITRON_PROXY_BASE + "/spins"
    logging.info("Retrieving currently playing song from `%s`", url)
    try:
        response = make_get_request(url)
        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logging.error("Failed to parse JSON from Spinitron: `%s`", e)
                return None
            spins = data.get("items", [])
            logging.debug("Received %d spins", len(spins))
            if not spins:
                logging.info("No spins found in response")
                return None
            current_spin = spins[0]
            song = current_spin.get("song")
            artist = current_spin.get("artist")
            if not current_spin or not song or not artist:
                logging.warning("Data missing from Spinitron response!")
                return None
            duration_s = current_spin.get("duration", 0)
            start = current_spin.get("start", 0)
            try:
                start_time = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError as e:
                logging.error("Error parsing start time `%s`: `%s`", start, e)
                return None
            elapsed_s = int(
                (
                    datetime.datetime.now(datetime.timezone.utc) - start_time
                ).total_seconds()
            )
            logging.debug(
                "Current spin - song: `%s`, artist: `%s`, duration: `%s`, elapsed: `%s`",
                song,
                artist,
                duration_s,
                elapsed_s,
            )
            return {
                "song": song,
                "artist": artist,
                "duration": duration_s,
                "elapsed": elapsed_s,
            }
        logging.error("Error calling WBOR API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Error calling WBOR API: `%s`", e)
    return None


def get_persona_name(p_id: int) -> Union[str, None]:
    """
    Get the persona name from an ID using a Spinitron API proxy (WBOR's)
    with retry logic.
    """
    if not isinstance(p_id, int):
        logging.warning("Invalid persona ID: `%s`", p_id)
        return None
    url = SPINITRON_PROXY_BASE + f"/personas/{p_id}"
    logging.info("Retrieving persona name from `%s`", url)
    try:
        response = make_get_request(url)
        if response.status_code == 200:
            data = response.json()
            name = data.get("name")
            if not name:
                logging.warning("Data missing from Spinitron response!")
                return None
            logging.debug("Retrieved persona name: `%s`", name)
            return name
        logging.error("Error calling WBOR API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Error calling WBOR API: `%s`", e)
    return None


def get_current_playlist_details() -> Union[dict, None]:
    """
    Get the most recent playlist from a Spinitron API proxy (WBOR's)
    with retry logic.
    """
    url = SPINITRON_PROXY_BASE + "/playlists"
    logging.info("Retrieving currently playing playlist from `%s`", url)
    try:
        response = make_get_request(url)
        if response.status_code == 200:
            data = response.json()
            playlists = data.get("items", [])
            logging.debug("Received %d playlists", len(playlists))
            if not playlists:
                logging.info("No playlists found in response")
                return None
            current_playlist = playlists[0]
            title = current_playlist.get("title")
            p_id = current_playlist.get("persona_id")
            is_automated = current_playlist.get("automation")
            if not current_playlist or not title or is_automated is None:
                logging.warning("Data missing from Spinitron response!")
                logging.debug(
                    "Current playlist - title: `%s`, persona_id: `%s`, automation: `%s`",
                    title,
                    p_id,
                    is_automated,
                )
                return None
            logging.debug(
                "Current playlist - title: `%s`, persona_id: `%s`, automation: `%s`",
                title,
                p_id,
                is_automated,
            )
            return {"title": title, "persona_id": p_id, "automation": is_automated}
        logging.error("Error calling WBOR API: `%s`", response.status_code)
    except requests.exceptions.RequestException as e:
        logging.error("Error calling WBOR API: `%s`", e)
    return None
