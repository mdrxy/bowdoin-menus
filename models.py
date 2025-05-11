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
        is_weekday = now.strftime("%a").lower() not in ("sat", "sun")

        logger.debug(
            "Determining upcoming meal for location=`%s`, day=`%s`, hour=`%s`",
            location,
            now.strftime("%a").lower(),
            h,
        )

        # schedule[location][is_weekday] is a list of tuples:
        # ( hour_check, special_check, special_meal, default_meal )
        #  - hour_check(h)      : returns True if the current hour falls in this block
        #  - special_check(day) : if provided and returns True, use special_meal
        #  - default_meal       : the meal to return if not a special day
        schedule = {
            Location.MOULTON: {
                True: [
                    # Weekday rules for Moulton
                    (
                        # Before 10am or after 7pm
                        lambda h: 0 <= h < 10 or 19 <= h < 24,
                        # On Fridays after dinner, we flip breakfast to brunch
                        lambda d: d == "fri",
                        Meals.BRUNCH,
                        Meals.BREAKFAST,
                    ),
                    # 10am–2pm is lunch
                    (lambda h: 10 <= h < 14, None, None, Meals.LUNCH),
                    # 2pm–7pm is dinner
                    (lambda h: 14 <= h < 19, None, None, Meals.DINNER),
                ],
                False: [
                    # Weekend rules for Moulton
                    # Before 11am or after 7pm is always brunch on Sat/Sun
                    (lambda h: 0 <= h < 11 or 19 <= h < 24, None, None, Meals.BRUNCH),
                    # 1pm–7pm is dinner
                    (lambda h: 13 <= h < 19, None, None, Meals.DINNER),
                ],
            },
            Location.THORNE: {
                True: [
                    # Weekday rules for Thorne
                    (
                        # Before 10am or after 8pm
                        lambda h: 0 <= h < 10 or 20 <= h < 24,
                        # On Fridays after dinner, flip breakfast to brunch
                        lambda d: d == "fri",
                        Meals.BRUNCH,
                        Meals.BREAKFAST,
                    ),
                    # 10am–2pm is lunch
                    (lambda h: 10 <= h < 14, None, None, Meals.LUNCH),
                    # 2pm–8pm is dinner
                    (lambda h: 14 <= h < 20, None, None, Meals.DINNER),
                ],
                False: [
                    # Weekend rules for Thorne
                    # Before 2pm or after 8pm is always brunch on Sat/Sun
                    (lambda h: 0 <= h < 14 or 20 <= h < 24, None, None, Meals.BRUNCH),
                    # 2pm–8pm is dinner
                    (lambda h: 14 <= h < 20, None, None, Meals.DINNER),
                ],
            },
        }

        # Pick the right rule‐set (weekday vs weekend) for this location
        rules = schedule[location][is_weekday]

        # Iterate through each rule in order
        for hour_check, special_check, special_meal, default_meal in rules:
            if hour_check(h):
                # If this rule has a special_check and it matches today, use that
                if special_check and special_check(now.strftime("%a").lower()):
                    return special_meal
                # Otherwise fall back to the default meal for this block
                return default_meal

        # If nothing matched (shouldn't happen), default to breakfast
        logger.debug("Meal not found in normal schedule, defaulting to BREAKFAST.")
        return Meals.BREAKFAST
