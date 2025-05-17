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
        now = datetime.datetime.now()
        h = now.hour  # Extract just the hour
        # Determine if today is a weekday (Mon–Fri) vs weekend (Sat/Sun)
        day_of_week_short = now.strftime("%a").lower()
        is_weekday = day_of_week_short not in ("sat", "sun")

        logger.debug(
            "Determining upcoming meal for location=`%s`, day=`%s`, hour=`%s`",
            location,
            day_of_week_short,
            h,
        )

        # schedule[location][is_weekday] is a list of tuples:
        # ( hour_check, special_check, special_meal, default_meal )
        #  - hour_check(h)      : returns True if the current hour falls in this block
        #  - special_check(day) : if provided and returns True, use special_meal
        #  - default_meal       : the meal to return if not a special day
        schedule = {
            Location.MOULTON: {
                True: [  # Weekday rules for Moulton
                    (
                        # Current day's breakfast (Mon-Fri before 10am)
                        lambda hour: 0 <= hour < 10,
                        None,  # No special day check needed, always breakfast
                        None,
                        Meals.BREAKFAST,
                    ),
                    (
                        # Next day's first meal (when checking Mon-Fri after 7pm dinner)
                        lambda hour: 19
                        <= hour
                        < 24,  # After Moulton's dinner (ends at 7pm)
                        lambda day: day == "fri",  # If it's Friday, next is Sat Brunch
                        Meals.BRUNCH,
                        Meals.BREAKFAST,  # Else (Mon-Thu), next is Breakfast
                    ),
                    # 10am–2pm is lunch
                    (lambda hour: 10 <= hour < 14, None, None, Meals.LUNCH),
                    # 2pm–7pm is dinner
                    (lambda hour: 14 <= hour < 19, None, None, Meals.DINNER),
                ],
                False: [  # Weekend rules for Moulton
                    (
                        # Brunch before 1pm, or next day's brunch if checking after 7pm dinner
                        lambda hour: 0 <= hour < 13 or 19 <= hour < 24,
                        None,
                        None,
                        Meals.BRUNCH,
                    ),
                    # 1pm–7pm is dinner
                    (lambda hour: 13 <= hour < 19, None, None, Meals.DINNER),
                ],
            },
            Location.THORNE: {
                True: [  # Weekday rules for Thorne
                    (
                        # Current day's breakfast (Mon-Fri before 10am)
                        lambda hour: 0 <= hour < 10,
                        None,  # No special day check needed, always breakfast
                        None,
                        Meals.BREAKFAST,
                    ),
                    (
                        # Next day's first meal (when checking Mon-Fri after 8pm dinner)
                        lambda hour: 20
                        <= hour
                        < 24,  # After Thorne's dinner (ends at 8pm)
                        lambda day: day == "fri",  # If it's Friday, next is Sat Brunch
                        Meals.BRUNCH,
                        Meals.BREAKFAST,  # Else (Mon-Thu), next is Breakfast
                    ),
                    # 10am–2pm is lunch
                    (lambda hour: 10 <= hour < 14, None, None, Meals.LUNCH),
                    # 2pm–8pm is dinner
                    (lambda hour: 14 <= hour < 20, None, None, Meals.DINNER),
                ],
                False: [  # Weekend rules for Thorne
                    (
                        # Brunch before 2pm, or next day's brunch if checking after 8pm dinner
                        lambda hour: 0 <= hour < 14 or 20 <= hour < 24,
                        None,
                        None,
                        Meals.BRUNCH,
                    ),
                    # 2pm–8pm is dinner
                    (lambda hour: 14 <= hour < 20, None, None, Meals.DINNER),
                ],
            },
        }

        # Pick the right rule‐set (weekday vs weekend) for this location
        rules = schedule[location][is_weekday]

        # Iterate through each rule in order
        for hour_check, special_check, special_meal, default_meal in rules:
            if hour_check(h):
                # If this rule has a special_check and it matches today, use that
                if special_check and special_check(day_of_week_short):
                    return special_meal
                # Otherwise fall back to the default meal for this block
                return default_meal

        # If nothing matched (shouldn't happen with comprehensive rules), default to breakfast
        logger.warning(
            "Meal not found in normal schedule for loc=`%s`, day=`%s`, hour=`%s`. Defaulting to "
            "BREAKFAST.",
            location,
            day_of_week_short,
            h,
        )
        return Meals.BREAKFAST
