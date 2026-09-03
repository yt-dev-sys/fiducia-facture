"""
Formatting helpers for the Moroccan Dirham (DH) price display used across the app.

Requested display format uses '.' as the thousands separator AND as the separator
before the 2-digit decimal part, e.g.:
    6000       -> "6.000.00"
    23500433.5 -> "23.500.433.50"
"""


def format_price_dh(value) -> str:
    """Format a number into the '6.000.00' / '23.500.433.00' style, with ' DH' suffix."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0

    negative = value < 0
    value = abs(value)

    int_part = int(value)
    decimal_part = round((value - int_part) * 100)
    if decimal_part == 100:
        int_part += 1
        decimal_part = 0

    grouped = f"{int_part:,}".replace(",", ".")
    result = f"{grouped}.{decimal_part:02d}"
    if negative:
        result = f"-{result}"
    return f"{result} DH"


def parse_price(text: str) -> float:
    """Parse user-entered price text into a float.

    Accepts plain numbers ("23500433.5"), comma decimals ("23500433,5"),
    or the display format itself ("23.500.433.00") - in the latter case,
    only the final '.' is treated as the decimal separator.
    """
    if text is None:
        return 0.0
    text = text.strip().replace(" ", "").replace("DH", "").replace("dh", "")
    if not text:
        return 0.0

    text = text.replace(",", ".")
    if text.count(".") > 1:
        parts = text.split(".")
        text = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(text)
    except ValueError:
        raise ValueError("Le prix doit être un nombre valide (ex: 6000 ou 23500433.50).")


# ---------------- Amount in words (French) ----------------

_UNITS = ["", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
          "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
          "dix-sept", "dix-huit", "dix-neuf"]
_TENS = ["", "", "vingt", "trente", "quarante", "cinquante", "soixante", "soixante-dix",
         "quatre-vingt", "quatre-vingt-dix"]


def _two_digits_to_words(n: int) -> str:
    if n < 20:
        return _UNITS[n]
    tens, unit = divmod(n, 10)
    if tens in (7, 9):  # soixante-dix / quatre-vingt-dix use the 1x pattern
        tens -= 1
        unit += 10
    word = _TENS[tens]
    if unit == 0:
        return word
    if tens == 8 and unit == 0:
        return word + "s"
    sep = "-et-" if unit == 1 and tens not in (8,) else "-"
    return f"{word}{sep}{_UNITS[unit]}"


def _three_digits_to_words(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append("cent" if hundreds == 1 else f"{_UNITS[hundreds]}-cent")
        if hundreds > 1 and rest == 0:
            parts[-1] += "s"
    if rest:
        parts.append(_two_digits_to_words(rest))
    return " ".join(parts) if parts else ""


def number_to_french_words(n: int) -> str:
    """Converts a non-negative integer into French words, e.g. 900 -> 'neuf cent'."""
    n = int(n)
    if n == 0:
        return "zéro"

    groups = [
        (10**9, "milliard", "milliards"),
        (10**6, "million", "millions"),
        (10**3, "mille", "mille"),
    ]
    parts = []
    remainder = n
    for value, singular, plural in groups:
        count, remainder = divmod(remainder, value)
        if count:
            if value == 10**3 and count == 1:
                parts.append("mille")
            else:
                words = _three_digits_to_words(count)
                label = singular if count == 1 else plural
                parts.append(f"{words} {label}")
    if remainder:
        parts.append(_three_digits_to_words(remainder))

    return " ".join(parts)


def amount_to_french_words_dh(value) -> str:
    """e.g. 900.00 -> 'Neuf Cent Dirhams', 1250.50 -> 'Mille Deux Cent Cinquante Dirhams Et Cinquante Centimes'."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    whole = int(value)
    cents = round((value - whole) * 100)
    words = number_to_french_words(whole) + " dirhams"
    if cents:
        words += " et " + number_to_french_words(cents) + " centimes"
    return words.title()


import re
from datetime import date, timedelta


def compute_echeance_date(invoice_date_iso: str, deadline_text: str) -> str:
    """Derives the 'Échéance' date (ISO string) from the invoice date and the free-text
    Deadline field, e.g. 'Paiement à 30 jours' -> invoice_date + 30 days.
    If no number of days is found in the text (e.g. 'Immédiat'), returns the invoice date itself."""
    try:
        y, m, d = [int(p) for p in invoice_date_iso.split("-")]
        base = date(y, m, d)
    except (ValueError, AttributeError):
        base = date.today()

    match = re.search(r"(\d+)", deadline_text or "")
    days = int(match.group(1)) if match else 0
    return (base + timedelta(days=days)).isoformat()


MONTHS_FR = [
    "01 - Janvier", "02 - Février", "03 - Mars", "04 - Avril", "05 - Mai", "06 - Juin",
    "07 - Juillet", "08 - Août", "09 - Septembre", "10 - Octobre", "11 - Novembre", "12 - Décembre",
]


def format_date_fr(iso_date: str) -> str:
    """Converts 'YYYY-MM-DD' to 'DD/MM/YYYY'. Returns the input unchanged if it doesn't parse."""
    if not iso_date:
        return ""
    try:
        y, m, d = iso_date.split("-")
        return f"{d}/{m}/{y}"
    except ValueError:
        return iso_date
