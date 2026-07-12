from __future__ import annotations

import re
from typing import Any


WIKIDATA_PRECISION = {
    11: "day",
    10: "month",
    9: "year",
    8: "decade",
    7: "century",
}


def normalize_wikidata_time(value: dict[str, Any]) -> dict[str, Any]:
    raw_time = str(value.get("time", ""))
    match = re.fullmatch(r"([+-])(\d{1,16})-(\d{2})-(\d{2})T00:00:00Z", raw_time)
    display = raw_time
    precision_number = int(value.get("precision", 0)) if isinstance(value.get("precision"), int) else 0
    if match:
        sign, year, month, day = match.groups()
        normalized_year = f"{'-' if sign == '-' else ''}{int(year):04d}"
        if precision_number == 9:
            display = normalized_year
        elif precision_number == 10:
            display = f"{normalized_year}-{month}"
        elif precision_number == 11:
            display = f"{normalized_year}-{month}-{day}"
        elif precision_number == 8:
            display = f"{normalized_year[:-1]}0s"
        else:
            display = normalized_year
    before = value.get("before", 0)
    after = value.get("after", 0)
    uncertainty = (before if isinstance(before, int) else 0) or (after if isinstance(after, int) else 0)
    return {
        "display_text": display,
        "precision": WIKIDATA_PRECISION.get(precision_number, "uncertain"),
        "range": {"before": before, "after": after} if uncertainty else None,
        "circa": False,
        "uncertain": precision_number not in WIKIDATA_PRECISION or bool(uncertainty),
        "calendar": value.get("calendarmodel"),
    }


def incompatible_life_dates(birth: dict[str, Any] | None, death: dict[str, Any] | None) -> bool:
    if not birth or not death:
        return False
    birth_year = _year(birth.get("display_text"))
    death_year = _year(death.get("display_text"))
    return birth_year is not None and death_year is not None and birth_year > death_year


def _year(value: object) -> int | None:
    match = re.match(r"^(-?)(\d{1,6})", str(value or ""))
    if not match:
        return None
    year = int(match.group(2))
    return -year if match.group(1) else year
