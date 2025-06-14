"""
Helper functions for making HTTP requests with retry logic.
"""

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
)
def make_post_request(url, data, headers=None, timeout=10):
    """
    Make a POST request with retry logic.
    """
    return requests.post(url, data=data, headers=headers, timeout=timeout)


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
)
def make_get_request(url, timeout=10):
    """
    Make a GET request with retry logic.
    """
    return requests.get(url, timeout=timeout)
