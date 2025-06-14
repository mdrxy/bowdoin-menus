"""
Models.
"""

import datetime
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class Location:  # pylint: disable=too-few-public-methods
    """
    Menu ID for a physical location. These are integer IDs.
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

    def get_upcoming_meal(self, location: int) -> Tuple[str, int]:
        """
        The next upcoming meal is set after the current meal expires.
        During a meal period, it is still 'upcoming'.
        Only handles whole hours, so 12:30 p.m. is rounded up to 1 p.m.
        Returns a tuple: (meal_type: str, date_offset_days: int)
        date_offset_days is 0 if the meal is for the current calendar
        day, 1 if it's for the next calendar day.
        """
        now = datetime.datetime.now()
        h = now.hour
        day_of_week_short = now.strftime("%a").lower()
        is_weekday = day_of_week_short not in ("sat", "sun")

        logger.debug(
            "Determining upcoming meal for location=`%s`, day=`%s`, hour=`%s`",
            location,
            day_of_week_short,
            h,
        )

        # schedule[location][is_weekday] is a list of tuples:
        # (hour_check, special_day_check, special_meal_tuple, default_meal_tuple)
        # Each meal_tuple is (meal_name: str, date_offset: int)
        schedule = {
            Location.MOULTON: {  # Using Location.MOULTON (which is 48) as key
                True: [  # Weekday rules for Moulton
                    # Current day's breakfast (Mon-Fri before 10am)
                    (lambda hour: 0 <= hour < 10, None, None, (Meals.BREAKFAST, 0)),
                    # Next day's first meal (when checking Mon-Fri after 7pm dinner)
                    (
                        lambda hour: 19 <= hour < 24,
                        lambda day: day == "fri",
                        (Meals.BRUNCH, 1),
                        (Meals.BREAKFAST, 1),
                    ),
                    # 10am–2pm is lunch
                    (lambda hour: 10 <= hour < 14, None, None, (Meals.LUNCH, 0)),
                    # 2pm–7pm is dinner
                    (lambda hour: 14 <= hour < 19, None, None, (Meals.DINNER, 0)),
                ],
                False: [  # Weekend rules for Moulton
                    # Current day brunch (morning to early afternoon)
                    (lambda hour: 0 <= hour < 13, None, None, (Meals.BRUNCH, 0)),
                    # Next day's brunch (when checking after dinner)
                    (lambda hour: 19 <= hour < 24, None, None, (Meals.BRUNCH, 1)),
                    # Current day dinner
                    (lambda hour: 13 <= hour < 19, None, None, (Meals.DINNER, 0)),
                ],
            },
            Location.THORNE: {  # Using Location.THORNE (which is 49) as key
                True: [  # Weekday rules for Thorne
                    # Current day's breakfast (Mon-Fri before 10am)
                    (lambda hour: 0 <= hour < 10, None, None, (Meals.BREAKFAST, 0)),
                    # Next day's first meal (when checking Mon-Fri after 8pm dinner)
                    (
                        lambda hour: 20 <= hour < 24,
                        lambda day: day == "fri",
                        (Meals.BRUNCH, 1),
                        (Meals.BREAKFAST, 1),
                    ),
                    # 10am–2pm is lunch
                    (lambda hour: 10 <= hour < 14, None, None, (Meals.LUNCH, 0)),
                    # 2pm–8pm is dinner
                    (lambda hour: 14 <= hour < 20, None, None, (Meals.DINNER, 0)),
                ],
                False: [  # Weekend rules for Thorne
                    # Current day brunch (morning to early afternoon)
                    (lambda hour: 0 <= hour < 14, None, None, (Meals.BRUNCH, 0)),
                    # Next day's brunch (when checking after dinner)
                    (lambda hour: 20 <= hour < 24, None, None, (Meals.BRUNCH, 1)),
                    # Current day dinner
                    (lambda hour: 14 <= hour < 20, None, None, (Meals.DINNER, 0)),
                ],
            },
        }

        # 'location' is an int (48 or 49), matching the keys in 'schedule'
        rules = schedule[location][is_weekday]

        for (
            hour_check,
            special_check,
            special_meal_offset_tuple,
            default_meal_offset_tuple,
        ) in rules:
            if hour_check(h):
                if special_check and special_check(day_of_week_short):
                    return special_meal_offset_tuple
                return default_meal_offset_tuple

        logger.warning(
            "Meal not found in normal schedule for loc=`%s`, day=`%s`, hour=`%s`. Defaulting to "
            "BREAKFAST, current day.",
            location,
            day_of_week_short,
            h,
        )
        return Meals.BREAKFAST, 0
