"""
Models.
"""

import datetime
import logging

logger = logging.getLogger(__name__)


class Location:  # pylint: disable=too-few-public-methods
    """
    Menu ID for a physical location.
    """

    MOULTON = 48
    THORNE = 49


class Meals:  # pylint: disable=too-few-public-methods
    """
    Meal periods.
    """

    BREAKFAST = "breakfast"
    BRUNCH = "brunch"
    LUNCH = "lunch"
    DINNER = "dinner"

    def get_upcoming_meal(self, location: Location):
        """
        The next upcoming meal is set after the current meal expires.
        During a meal period, it is still 'upcoming'.
        Only handles whole hours, so 12:30 p.m. is rounded up to 1 p.m.
        """
        current_hour = datetime.datetime.now().time().hour
        current_day = datetime.datetime.now().strftime("%a").lower()
        logger.debug(
            "Determining upcoming meal for location=`%s`, day=`%s`, hour=`%s`",
            location,
            current_day,
            current_hour,
        )

        is_weekend = current_day in ["sat", "sun"]

        schedule = {
            Location.MOULTON: {
                "weekday": [
                    (
                        # Check if current hour is in breakfast or post-dinner range
                        lambda h: 0 <= h < 10 or 19 <= h < 24,
                        # On Fridays, post-dinner should return BRUNCH instead
                        lambda d: d == "fri",
                        Meals.BRUNCH,
                        Meals.BREAKFAST,
                    ),
                    (
                        # Check if current hour is in lunch range
                        lambda h: 10 <= h < 14,
                        None,
                        None,
                        Meals.LUNCH,
                    ),
                    (
                        # Check if current hour is in dinner range
                        lambda h: 14 <= h < 19,
                        None,
                        None,
                        Meals.DINNER,
                    ),
                ],
                "weekend": [
                    (
                        # Check if current hour is in brunch or post-dinner range
                        lambda h: 0 <= h < 11 or 19 <= h < 24,
                        # On Sundays, post-dinner returns BREAKFAST instead
                        lambda d: d == "sun",
                        Meals.BREAKFAST,
                        Meals.BRUNCH,
                    ),
                    (
                        lambda h: 11 <= h < 13,
                        None,
                        None,
                        Meals.LUNCH,
                    ),
                    (
                        lambda h: 13 <= h < 19,
                        None,
                        None,
                        Meals.DINNER,
                    ),
                ],
            },
            Location.THORNE: {
                "weekday": [
                    (
                        lambda h: 0 <= h < 10 or 20 <= h < 24,
                        lambda d: d == "fri",
                        Meals.BRUNCH,
                        Meals.BREAKFAST,
                    ),
                    (
                        lambda h: 10 <= h < 14,
                        None,
                        None,
                        Meals.LUNCH,
                    ),
                    (
                        lambda h: 14 <= h < 20,
                        None,
                        None,
                        Meals.DINNER,
                    ),
                ],
                "weekend": [
                    (
                        lambda h: 0 <= h < 14 or 20 <= h < 24,
                        lambda d: d == "sun",
                        Meals.BREAKFAST,
                        Meals.BRUNCH,
                    ),
                    (
                        lambda h: 14 <= h < 20,
                        None,
                        None,
                        Meals.DINNER,
                    ),
                ],
            },
        }

        rules = schedule[location]["weekend" if is_weekend else "weekday"]
        for hour_check, special_check, special_meal, default_meal in rules:
            if hour_check(current_hour):
                if special_check and special_check(current_day):
                    return special_meal
                return default_meal

        logger.debug("Meal not found in normal schedule, defaulting to BREAKFAST.")
        return Meals.BREAKFAST
