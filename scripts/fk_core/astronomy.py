"""Equinoxes, solstices and new moons at day precision (UTC), after Jean Meeus, *Astronomical
Algorithms* (2nd ed.), chapters 27 (equinoxes and solstices) and 49 (phases of the Moon).

Mirrored exactly by src/lib/shared/astronomy.js — keep both in sync. Parity rules: same operation order,
explicit products (no powers), angles reduced with `angle - 360 * floor(angle / 360)` (never `%`),
`math.floor` only, UTC only. Terrestrial Time -> Universal Time uses the Espenak/Meeus 2005-2050
polynomial for every year (a documented approximation; day precision is what the season rules need).
"""
import datetime
import math

DEGREES_TO_RADIANS = math.pi / 180
JULIAN_DAY_2000_01_01 = 2451544.5  # 2000-01-01 00:00 UT
DATE_2000_01_01 = datetime.date(2000, 1, 1)
SECONDS_PER_DAY = 86400

SOLAR_TERM_ORDER = ["spring-equinox", "summer-solstice", "autumn-equinox", "winter-solstice"]

# Meeus table 27.B (years 1000-3000): JDE0 = a + b Y + c Y^2 + d Y^3 + e Y^4, Y = (year - 2000) / 1000.
SOLAR_TERM_POLYNOMIALS = {
    "spring-equinox": (2451623.80984, 365242.37404, 0.05169, -0.00411, -0.00057),
    "summer-solstice": (2451716.56767, 365241.62603, 0.00325, 0.00888, -0.00030),
    "autumn-equinox": (2451810.21715, 365242.01767, -0.11575, 0.00337, 0.00078),
    "winter-solstice": (2451900.05952, 365242.74049, -0.06223, -0.00823, 0.00032),
}

# Meeus table 27.C: (A, B degrees, C degrees per Julian century).
SOLAR_TERM_PERIODIC_TERMS = [
    (485, 324.96, 1934.136), (203, 337.23, 32964.467), (199, 342.08, 20.186), (182, 27.85, 445267.112),
    (156, 73.14, 45036.886), (136, 171.52, 22518.443), (77, 222.54, 65928.934), (74, 296.72, 3034.906),
    (70, 243.58, 9037.513), (58, 119.81, 33718.147), (52, 297.17, 150.678), (50, 21.02, 2281.226),
    (45, 247.54, 29929.562), (44, 325.15, 31555.956), (29, 60.93, 4443.417), (18, 155.12, 67555.328),
    (17, 288.79, 4562.452), (16, 198.04, 62894.029), (14, 199.76, 31436.921), (12, 95.39, 14577.848),
    (12, 287.11, 31931.756), (12, 320.81, 34777.259), (9, 227.73, 1222.114), (8, 15.45, 16859.074),
]

# Meeus chapter 49, planetary arguments for the new moon: (coefficient in days, A degrees, B degrees per k, C degrees per T^2).
NEW_MOON_PLANETARY_TERMS = [
    (0.000325, 299.77, 0.107408, -0.009173), (0.000165, 251.88, 0.016321, 0), (0.000164, 251.83, 26.651886, 0),
    (0.000126, 349.42, 36.412478, 0), (0.000110, 84.66, 18.206239, 0), (0.000062, 141.74, 53.303771, 0),
    (0.000060, 207.14, 2.453732, 0), (0.000056, 154.84, 7.306860, 0), (0.000047, 34.52, 27.261239, 0),
    (0.000042, 207.19, 0.121824, 0), (0.000040, 291.34, 1.844379, 0), (0.000037, 161.72, 24.198154, 0),
    (0.000035, 239.56, 25.513099, 0), (0.000023, 331.55, 3.592518, 0),
]


def reduce_degrees(angle):
    return angle - 360 * math.floor(angle / 360)


def sine_of_degrees(angle):
    return math.sin(reduce_degrees(angle) * DEGREES_TO_RADIANS)


def cosine_of_degrees(angle):
    return math.cos(reduce_degrees(angle) * DEGREES_TO_RADIANS)


def delta_t_seconds(year):
    """Terrestrial Time minus Universal Time (Espenak/Meeus polynomial for 2005-2050, used for every year)."""
    t = year - 2000
    return 62.92 + 0.32217 * t + 0.005589 * t * t


def julian_day_to_date(julian_day):
    """Universal-Time Julian Day -> calendar date (UTC)."""
    return DATE_2000_01_01 + datetime.timedelta(days=math.floor(julian_day - JULIAN_DAY_2000_01_01))


def solar_term_julian_ephemeris_day(term, year):
    a, b, c, d, e = SOLAR_TERM_POLYNOMIALS[term]
    y = (year - 2000) / 1000
    mean = a + b * y + c * y * y + d * y * y * y + e * y * y * y * y
    t = (mean - 2451545.0) / 36525
    w = 35999.373 * t - 2.47
    delta_lambda = 1 + 0.0334 * cosine_of_degrees(w) + 0.0007 * cosine_of_degrees(2 * w)
    total = 0
    for amplitude, phase, rate in SOLAR_TERM_PERIODIC_TERMS:
        total += amplitude * cosine_of_degrees(phase + rate * t)
    return mean + (0.00001 * total) / delta_lambda


def solar_term_date(term, year):
    """UTC date of an equinox or solstice (SOLAR_TERM_ORDER) in `year`."""
    julian_ephemeris_day = solar_term_julian_ephemeris_day(term, year)
    return julian_day_to_date(julian_ephemeris_day - delta_t_seconds(year) / SECONDS_PER_DAY)


def new_moon_julian_ephemeris_day(k):
    """Meeus 49.1-49.7 for an integer lunation number k (k = 0 -> the new moon of 2000-01-06)."""
    t = k / 1236.85
    julian_ephemeris_day = (2451550.09766 + 29.530588861 * k + 0.00015437 * t * t
                            - 0.000000150 * t * t * t + 0.00000000073 * t * t * t * t)
    e = 1 - 0.002516 * t - 0.0000074 * t * t
    sun_anomaly = 2.5534 + 29.10535670 * k - 0.0000014 * t * t - 0.00000011 * t * t * t
    moon_anomaly = (201.5643 + 385.81693528 * k + 0.0107582 * t * t + 0.00001238 * t * t * t
                    - 0.000000058 * t * t * t * t)
    moon_argument = (160.7108 + 390.67050284 * k - 0.0016118 * t * t - 0.00000227 * t * t * t
                     + 0.000000011 * t * t * t * t)
    ascending_node = 124.7746 - 1.56375588 * k + 0.0020672 * t * t + 0.00000215 * t * t * t
    correction = 0
    correction += -0.40720 * sine_of_degrees(moon_anomaly)
    correction += 0.17241 * e * sine_of_degrees(sun_anomaly)
    correction += 0.01608 * sine_of_degrees(2 * moon_anomaly)
    correction += 0.01039 * sine_of_degrees(2 * moon_argument)
    correction += 0.00739 * e * sine_of_degrees(moon_anomaly - sun_anomaly)
    correction += -0.00514 * e * sine_of_degrees(moon_anomaly + sun_anomaly)
    correction += 0.00208 * e * e * sine_of_degrees(2 * sun_anomaly)
    correction += -0.00111 * sine_of_degrees(moon_anomaly - 2 * moon_argument)
    correction += -0.00057 * sine_of_degrees(moon_anomaly + 2 * moon_argument)
    correction += 0.00056 * e * sine_of_degrees(2 * moon_anomaly + sun_anomaly)
    correction += -0.00042 * sine_of_degrees(3 * moon_anomaly)
    correction += 0.00042 * e * sine_of_degrees(sun_anomaly + 2 * moon_argument)
    correction += 0.00038 * e * sine_of_degrees(sun_anomaly - 2 * moon_argument)
    correction += -0.00024 * e * sine_of_degrees(2 * moon_anomaly - sun_anomaly)
    correction += -0.00017 * sine_of_degrees(ascending_node)
    correction += -0.00007 * sine_of_degrees(moon_anomaly + 2 * sun_anomaly)
    correction += 0.00004 * sine_of_degrees(2 * moon_anomaly - 2 * moon_argument)
    correction += 0.00004 * sine_of_degrees(3 * sun_anomaly)
    correction += 0.00003 * sine_of_degrees(moon_anomaly + sun_anomaly - 2 * moon_argument)
    correction += 0.00003 * sine_of_degrees(2 * moon_anomaly + 2 * moon_argument)
    correction += -0.00003 * sine_of_degrees(moon_anomaly + sun_anomaly + 2 * moon_argument)
    correction += 0.00003 * sine_of_degrees(moon_anomaly - sun_anomaly + 2 * moon_argument)
    correction += -0.00002 * sine_of_degrees(moon_anomaly - sun_anomaly - 2 * moon_argument)
    correction += -0.00002 * sine_of_degrees(3 * moon_anomaly + sun_anomaly)
    correction += 0.00002 * sine_of_degrees(4 * moon_anomaly)
    for coefficient, a, b, c in NEW_MOON_PLANETARY_TERMS:
        correction += coefficient * sine_of_degrees(a + b * k + c * t * t)
    return julian_ephemeris_day + correction


def new_moon_date(k):
    """UTC date of the new moon with lunation number k."""
    julian_ephemeris_day = new_moon_julian_ephemeris_day(k)
    approximate_year = 2000 + k / 12.3685
    return julian_day_to_date(julian_ephemeris_day - delta_t_seconds(approximate_year) / SECONDS_PER_DAY)


def new_moon_dates_in_year(year):
    """The 12 or 13 new moons (UTC dates) of a calendar year, in order."""
    k = math.floor((year - 2000) * 12.3685) - 2
    dates = []
    while True:
        date = new_moon_date(k)
        if date.year > year:
            break
        if date.year == year:
            dates.append(date)
        k += 1
    return dates
