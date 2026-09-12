// Equinoxes, solstices and new moons at day precision (UTC), after Jean Meeus, *Astronomical
// Algorithms* (2nd ed.), chapters 27 (equinoxes and solstices) and 49 (phases of the Moon).
//
// Mirrored exactly by scripts/fk_core/astronomy.py — keep both in sync. Parity rules: same operation
// order, explicit products (no powers), angles reduced with `angle - 360 * floor(angle / 360)` (never
// `%`), Math.floor only, UTC only. Terrestrial Time -> Universal Time uses the Espenak/Meeus 2005-2050
// polynomial for every year (a documented approximation; day precision is what the season rules need).

const DEGREES_TO_RADIANS = Math.PI / 180;
const JULIAN_DAY_2000_01_01 = 2451544.5; // 2000-01-01 00:00 UT
const MILLISECONDS_2000_01_01 = Date.UTC(2000, 0, 1);
const MILLISECONDS_PER_DAY = 86400000;
const SECONDS_PER_DAY = 86400;

export const SOLAR_TERM_ORDER = ["spring-equinox", "summer-solstice", "autumn-equinox", "winter-solstice"];

// Meeus table 27.B (years 1000-3000): JDE0 = a + b Y + c Y^2 + d Y^3 + e Y^4, Y = (year - 2000) / 1000.
const SOLAR_TERM_POLYNOMIALS = {
  "spring-equinox": [2451623.80984, 365242.37404, 0.05169, -0.00411, -0.00057],
  "summer-solstice": [2451716.56767, 365241.62603, 0.00325, 0.00888, -0.00030],
  "autumn-equinox": [2451810.21715, 365242.01767, -0.11575, 0.00337, 0.00078],
  "winter-solstice": [2451900.05952, 365242.74049, -0.06223, -0.00823, 0.00032],
};

// Meeus table 27.C: [A, B degrees, C degrees per Julian century].
const SOLAR_TERM_PERIODIC_TERMS = [
  [485, 324.96, 1934.136], [203, 337.23, 32964.467], [199, 342.08, 20.186], [182, 27.85, 445267.112],
  [156, 73.14, 45036.886], [136, 171.52, 22518.443], [77, 222.54, 65928.934], [74, 296.72, 3034.906],
  [70, 243.58, 9037.513], [58, 119.81, 33718.147], [52, 297.17, 150.678], [50, 21.02, 2281.226],
  [45, 247.54, 29929.562], [44, 325.15, 31555.956], [29, 60.93, 4443.417], [18, 155.12, 67555.328],
  [17, 288.79, 4562.452], [16, 198.04, 62894.029], [14, 199.76, 31436.921], [12, 95.39, 14577.848],
  [12, 287.11, 31931.756], [12, 320.81, 34777.259], [9, 227.73, 1222.114], [8, 15.45, 16859.074],
];

// Meeus chapter 49, planetary arguments for the new moon: [coefficient in days, A degrees, B degrees per k, C degrees per T^2].
const NEW_MOON_PLANETARY_TERMS = [
  [0.000325, 299.77, 0.107408, -0.009173], [0.000165, 251.88, 0.016321, 0], [0.000164, 251.83, 26.651886, 0],
  [0.000126, 349.42, 36.412478, 0], [0.000110, 84.66, 18.206239, 0], [0.000062, 141.74, 53.303771, 0],
  [0.000060, 207.14, 2.453732, 0], [0.000056, 154.84, 7.306860, 0], [0.000047, 34.52, 27.261239, 0],
  [0.000042, 207.19, 0.121824, 0], [0.000040, 291.34, 1.844379, 0], [0.000037, 161.72, 24.198154, 0],
  [0.000035, 239.56, 25.513099, 0], [0.000023, 331.55, 3.592518, 0],
];

export function reduceDegrees(angle) {
  return angle - 360 * Math.floor(angle / 360);
}

function sineOfDegrees(angle) {
  return Math.sin(reduceDegrees(angle) * DEGREES_TO_RADIANS);
}

function cosineOfDegrees(angle) {
  return Math.cos(reduceDegrees(angle) * DEGREES_TO_RADIANS);
}

/** Terrestrial Time minus Universal Time (Espenak/Meeus polynomial for 2005-2050, used for every year). */
export function deltaTSeconds(year) {
  const t = year - 2000;
  return 62.92 + 0.32217 * t + 0.005589 * t * t;
}

/** Universal-Time Julian Day -> calendar date (UTC midnight Date). */
export function julianDayToDate(julianDay) {
  return new Date(MILLISECONDS_2000_01_01 + Math.floor(julianDay - JULIAN_DAY_2000_01_01) * MILLISECONDS_PER_DAY);
}

export function solarTermJulianEphemerisDay(term, year) {
  const [a, b, c, d, e] = SOLAR_TERM_POLYNOMIALS[term];
  const y = (year - 2000) / 1000;
  const mean = a + b * y + c * y * y + d * y * y * y + e * y * y * y * y;
  const t = (mean - 2451545.0) / 36525;
  const w = 35999.373 * t - 2.47;
  const deltaLambda = 1 + 0.0334 * cosineOfDegrees(w) + 0.0007 * cosineOfDegrees(2 * w);
  let total = 0;
  for (const [amplitude, phase, rate] of SOLAR_TERM_PERIODIC_TERMS) {
    total += amplitude * cosineOfDegrees(phase + rate * t);
  }
  return mean + (0.00001 * total) / deltaLambda;
}

/** UTC date of an equinox or solstice (SOLAR_TERM_ORDER) in `year`. */
export function solarTermDate(term, year) {
  const julianEphemerisDay = solarTermJulianEphemerisDay(term, year);
  return julianDayToDate(julianEphemerisDay - deltaTSeconds(year) / SECONDS_PER_DAY);
}

/** Meeus 49.1-49.7 for an integer lunation number k (k = 0 -> the new moon of 2000-01-06). */
export function newMoonJulianEphemerisDay(k) {
  const t = k / 1236.85;
  const julianEphemerisDay = 2451550.09766 + 29.530588861 * k + 0.00015437 * t * t
    - 0.000000150 * t * t * t + 0.00000000073 * t * t * t * t;
  const e = 1 - 0.002516 * t - 0.0000074 * t * t;
  const sunAnomaly = 2.5534 + 29.10535670 * k - 0.0000014 * t * t - 0.00000011 * t * t * t;
  const moonAnomaly = 201.5643 + 385.81693528 * k + 0.0107582 * t * t + 0.00001238 * t * t * t
    - 0.000000058 * t * t * t * t;
  const moonArgument = 160.7108 + 390.67050284 * k - 0.0016118 * t * t - 0.00000227 * t * t * t
    + 0.000000011 * t * t * t * t;
  const ascendingNode = 124.7746 - 1.56375588 * k + 0.0020672 * t * t + 0.00000215 * t * t * t;
  let correction = 0;
  correction += -0.40720 * sineOfDegrees(moonAnomaly);
  correction += 0.17241 * e * sineOfDegrees(sunAnomaly);
  correction += 0.01608 * sineOfDegrees(2 * moonAnomaly);
  correction += 0.01039 * sineOfDegrees(2 * moonArgument);
  correction += 0.00739 * e * sineOfDegrees(moonAnomaly - sunAnomaly);
  correction += -0.00514 * e * sineOfDegrees(moonAnomaly + sunAnomaly);
  correction += 0.00208 * e * e * sineOfDegrees(2 * sunAnomaly);
  correction += -0.00111 * sineOfDegrees(moonAnomaly - 2 * moonArgument);
  correction += -0.00057 * sineOfDegrees(moonAnomaly + 2 * moonArgument);
  correction += 0.00056 * e * sineOfDegrees(2 * moonAnomaly + sunAnomaly);
  correction += -0.00042 * sineOfDegrees(3 * moonAnomaly);
  correction += 0.00042 * e * sineOfDegrees(sunAnomaly + 2 * moonArgument);
  correction += 0.00038 * e * sineOfDegrees(sunAnomaly - 2 * moonArgument);
  correction += -0.00024 * e * sineOfDegrees(2 * moonAnomaly - sunAnomaly);
  correction += -0.00017 * sineOfDegrees(ascendingNode);
  correction += -0.00007 * sineOfDegrees(moonAnomaly + 2 * sunAnomaly);
  correction += 0.00004 * sineOfDegrees(2 * moonAnomaly - 2 * moonArgument);
  correction += 0.00004 * sineOfDegrees(3 * sunAnomaly);
  correction += 0.00003 * sineOfDegrees(moonAnomaly + sunAnomaly - 2 * moonArgument);
  correction += 0.00003 * sineOfDegrees(2 * moonAnomaly + 2 * moonArgument);
  correction += -0.00003 * sineOfDegrees(moonAnomaly + sunAnomaly + 2 * moonArgument);
  correction += 0.00003 * sineOfDegrees(moonAnomaly - sunAnomaly + 2 * moonArgument);
  correction += -0.00002 * sineOfDegrees(moonAnomaly - sunAnomaly - 2 * moonArgument);
  correction += -0.00002 * sineOfDegrees(3 * moonAnomaly + sunAnomaly);
  correction += 0.00002 * sineOfDegrees(4 * moonAnomaly);
  for (const [coefficient, a, b, c] of NEW_MOON_PLANETARY_TERMS) {
    correction += coefficient * sineOfDegrees(a + b * k + c * t * t);
  }
  return julianEphemerisDay + correction;
}

/** UTC date of the new moon with lunation number k. */
export function newMoonDate(k) {
  const julianEphemerisDay = newMoonJulianEphemerisDay(k);
  const approximateYear = 2000 + k / 12.3685;
  return julianDayToDate(julianEphemerisDay - deltaTSeconds(approximateYear) / SECONDS_PER_DAY);
}

/** The 12 or 13 new moons (UTC midnight Dates) of a calendar year, in order. */
export function newMoonDatesInYear(year) {
  let k = Math.floor((year - 2000) * 12.3685) - 2;
  const dates = [];
  for (;;) {
    const date = newMoonDate(k);
    if (date.getUTCFullYear() > year) break;
    if (date.getUTCFullYear() === year) dates.push(date);
    k += 1;
  }
  return dates;
}
