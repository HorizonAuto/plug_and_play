import math
from datetime import datetime, timezone


def solar_elevation_degrees(lat: float, lon: float, when: datetime) -> float:
    """Approximate solar elevation angle (degrees above horizon) for a lat/lon at a UTC time.

    Uses the NOAA Solar Position Algorithm in its short form. Accurate to within
    a few tenths of a degree, which is plenty for "is the sun up?"-grade checks.
    """
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)

    day_of_year = when.timetuple().tm_yday
    fractional_year = (2 * math.pi / 365.0) * (day_of_year - 1 + (when.hour - 12) / 24.0)

    eqtime_minutes = 229.18 * (
        0.000075
        + 0.001868 * math.cos(fractional_year)
        - 0.032077 * math.sin(fractional_year)
        - 0.014615 * math.cos(2 * fractional_year)
        - 0.040849 * math.sin(2 * fractional_year)
    )

    declination = (
        0.006918
        - 0.399912 * math.cos(fractional_year)
        + 0.070257 * math.sin(fractional_year)
        - 0.006758 * math.cos(2 * fractional_year)
        + 0.000907 * math.sin(2 * fractional_year)
        - 0.002697 * math.cos(3 * fractional_year)
        + 0.00148 * math.sin(3 * fractional_year)
    )

    minutes_utc = when.hour * 60 + when.minute + when.second / 60.0
    true_solar_time = minutes_utc + eqtime_minutes + 4 * lon
    hour_angle = math.radians((true_solar_time / 4.0) - 180.0)

    lat_rad = math.radians(lat)
    sin_elev = (
        math.sin(lat_rad) * math.sin(declination)
        + math.cos(lat_rad) * math.cos(declination) * math.cos(hour_angle)
    )
    sin_elev = max(-1.0, min(1.0, sin_elev))
    return math.degrees(math.asin(sin_elev))
