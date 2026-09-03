# -*- coding: utf-8 -*-
# [NEXTONES-MARKET-CALENDAR-V1]
# Calendrier NYSE/NASDAQ avec garde-fou pour le pipeline Thesium.
#
# Public API :
#   is_us_market_open(dt=None)          -> bool
#   is_us_holiday(date_obj)             -> bool
#   is_us_early_close(date_obj)         -> bool
#   next_us_open(dt=None)               -> datetime (UTC)
#   seconds_until_next_open(dt=None)    -> int
#   guard_or_skip(force=False, dt=None) -> (allowed, reason)
#
# Note : pas de dependance externe (pandas_market_calendars non requis).
# Calendrier NYSE 2026-2030 hardcode (jours feries fixes + Good Friday calcule).
#
# Heures NYSE :
#   Regular open  : 09:30 ET (13:30 UTC hiver / 14:30 UTC ete)
#   Regular close : 16:00 ET (20:00 UTC hiver / 21:00 UTC ete)
#   Early close   : 13:00 ET (17:00 UTC hiver / 18:00 UTC ete)
#
# Pour simplifier on dit "marche ouvert" = jour ouvre US (peu importe l'heure
# dans la journee). Le pipeline Thesium peut tourner avant/apres heures
# regulieres si besoin (extended hours), mais PAS samedi/dimanche/feries.

from __future__ import annotations

import datetime as _dt
from typing import Optional, Tuple


# ---------------------------------------------------------------------
# Calendrier feries NYSE 2026-2030
# Source : https://www.nyse.com/markets/hours-calendars
# Format : (date_iso, label, early_close?)
# Early close = jour ouvre mais ferme tot (13:00 ET = 18:00 UTC en ete)
# ---------------------------------------------------------------------

_NYSE_HOLIDAYS_BASE = [
    # ---- 2026 ----
    ("2026-01-01", "New Year's Day", False),
    ("2026-01-19", "Martin Luther King Jr. Day", False),
    ("2026-02-16", "Presidents Day", False),
    ("2026-04-03", "Good Friday", False),
    ("2026-05-25", "Memorial Day", False),
    ("2026-06-19", "Juneteenth", False),
    ("2026-07-03", "Independence Day (observed)", False),
    ("2026-09-07", "Labor Day", False),
    ("2026-11-26", "Thanksgiving", False),
    ("2026-11-27", "Day after Thanksgiving", True),
    ("2026-12-24", "Christmas Eve", True),
    ("2026-12-25", "Christmas Day", False),
    # ---- 2027 ----
    ("2027-01-01", "New Year's Day", False),
    ("2027-01-18", "Martin Luther King Jr. Day", False),
    ("2027-02-15", "Presidents Day", False),
    ("2027-03-26", "Good Friday", False),
    ("2027-05-31", "Memorial Day", False),
    ("2027-06-18", "Juneteenth (observed)", False),
    ("2027-07-05", "Independence Day (observed)", False),
    ("2027-09-06", "Labor Day", False),
    ("2027-11-25", "Thanksgiving", False),
    ("2027-11-26", "Day after Thanksgiving", True),
    ("2027-12-24", "Christmas Eve", True),
    # ---- 2028 ----
    ("2028-01-17", "Martin Luther King Jr. Day", False),
    ("2028-02-21", "Presidents Day", False),
    ("2028-04-14", "Good Friday", False),
    ("2028-05-29", "Memorial Day", False),
    ("2028-06-19", "Juneteenth", False),
    ("2028-07-04", "Independence Day", False),
    ("2028-09-04", "Labor Day", False),
    ("2028-11-23", "Thanksgiving", False),
    ("2028-11-24", "Day after Thanksgiving", True),
    ("2028-12-25", "Christmas Day", False),
    # ---- 2029 ----
    ("2029-01-01", "New Year's Day", False),
    ("2029-01-15", "Martin Luther King Jr. Day", False),
    ("2029-02-19", "Presidents Day", False),
    ("2029-03-30", "Good Friday", False),
    ("2029-05-28", "Memorial Day", False),
    ("2029-06-19", "Juneteenth", False),
    ("2029-07-04", "Independence Day", False),
    ("2029-09-03", "Labor Day", False),
    ("2029-11-22", "Thanksgiving", False),
    ("2029-11-23", "Day after Thanksgiving", True),
    ("2029-12-24", "Christmas Eve", True),
    ("2029-12-25", "Christmas Day", False),
    # ---- 2030 ----
    ("2030-01-01", "New Year's Day", False),
    ("2030-01-21", "Martin Luther King Jr. Day", False),
    ("2030-02-18", "Presidents Day", False),
    ("2030-04-19", "Good Friday", False),
    ("2030-05-27", "Memorial Day", False),
    ("2030-06-19", "Juneteenth", False),
    ("2030-07-04", "Independence Day", False),
    ("2030-09-02", "Labor Day", False),
    ("2030-11-28", "Thanksgiving", False),
    ("2030-11-29", "Day after Thanksgiving", True),
    ("2030-12-24", "Christmas Eve", True),
    ("2030-12-25", "Christmas Day", False),
]

# Index pour lookup O(1)
_HOLIDAY_MAP = {d: (label, early) for (d, label, early) in _NYSE_HOLIDAYS_BASE}
_FULL_HOLIDAYS = {d for (d, label, early) in _NYSE_HOLIDAYS_BASE if not early}
_EARLY_CLOSES = {d for (d, label, early) in _NYSE_HOLIDAYS_BASE if early}


# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------

def _to_date(dt) -> _dt.date:
    if isinstance(dt, _dt.datetime):
        return dt.date()
    if isinstance(dt, _dt.date):
        return dt
    if dt is None:
        return _dt.datetime.now(_dt.timezone.utc).date()
    raise TypeError(f"Type non supporte : {type(dt)}")


def is_us_holiday(date_obj=None) -> bool:
    """True si la date est un jour ferie NYSE (full holiday only)."""
    d = _to_date(date_obj)
    return d.isoformat() in _FULL_HOLIDAYS


def is_us_early_close(date_obj=None) -> bool:
    """True si la date est un jour de fermeture anticipee (13:00 ET)."""
    d = _to_date(date_obj)
    return d.isoformat() in _EARLY_CLOSES


def is_weekend(date_obj=None) -> bool:
    """True si samedi ou dimanche."""
    d = _to_date(date_obj)
    return d.weekday() >= 5  # 5=samedi, 6=dimanche


def is_us_market_open(dt=None) -> bool:
    """True si le marche US est ouvert ce jour-la (sans considerer l'heure).
    Renvoie False pour : samedi, dimanche, jour ferie NYSE.
    Renvoie True pour : jour ouvre + jour de fermeture anticipee.
    """
    d = _to_date(dt)
    if is_weekend(d):
        return False
    if is_us_holiday(d):
        return False
    return True


def get_holiday_label(date_obj=None) -> Optional[str]:
    d = _to_date(date_obj)
    info = _HOLIDAY_MAP.get(d.isoformat())
    return info[0] if info else None


def next_us_open(dt=None) -> _dt.datetime:
    """Retourne le prochain jour ouvre US (datetime UTC a 14:00, ~09:30 ET ete)."""
    if dt is None:
        dt = _dt.datetime.now(_dt.timezone.utc)
    d = dt.date()
    for _ in range(20):  # max ~3 semaines de feries cumules
        d = d + _dt.timedelta(days=1)
        if is_us_market_open(d):
            return _dt.datetime(d.year, d.month, d.day, 14, 0, 0,
                                tzinfo=_dt.timezone.utc)
    raise RuntimeError("Aucun jour ouvre trouve sur 20 jours")


def seconds_until_next_open(dt=None) -> int:
    """Secondes avant le prochain open US."""
    if dt is None:
        dt = _dt.datetime.now(_dt.timezone.utc)
    nxt = next_us_open(dt)
    return int((nxt - dt).total_seconds())


def guard_or_skip(force: bool = False, dt=None
                  ) -> Tuple[bool, str]:
    """Garde-fou principal pour execute_cycle().
    Retourne (allowed, reason).
      - allowed=True  : on peut continuer
      - allowed=False : on doit skip (reason explique pourquoi)
    Si force=True : retourne toujours allowed=True avec reason='forced'.
    """
    if force:
        return True, "forced"
    d = _to_date(dt)
    if is_weekend(d):
        day_name = d.strftime("%A")
        return False, f"weekend_skip ({day_name} {d.isoformat()})"
    if is_us_holiday(d):
        label = get_holiday_label(d) or "unknown"
        return False, f"us_holiday_skip ({label} {d.isoformat()})"
    if is_us_early_close(d):
        label = get_holiday_label(d) or "early_close"
        return True, f"early_close_warning ({label} {d.isoformat()})"
    return True, "open"


# ---------------------------------------------------------------------
# CLI (test manuel + scheduler helper)
# ---------------------------------------------------------------------

def _main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="ISO date YYYY-MM-DD (defaut: aujourd'hui UTC)")
    ap.add_argument("--check", action="store_true", help="affiche statut")
    ap.add_argument("--next", action="store_true", help="affiche prochain open")
    ap.add_argument("--list-2026", action="store_true",
                    help="liste les feries 2026")
    ap.add_argument("--list-2027", action="store_true",
                    help="liste les feries 2027")
    args = ap.parse_args()

    if args.date:
        d = _dt.date.fromisoformat(args.date)
    else:
        d = _dt.datetime.now(_dt.timezone.utc).date()

    if args.list_2026 or args.list_2027:
        year = "2026" if args.list_2026 else "2027"
        print(f"Feries NYSE {year} :")
        for (iso, label, early) in _NYSE_HOLIDAYS_BASE:
            if iso.startswith(year):
                tag = "[EARLY]" if early else "[CLOSED]"
                print(f"  {iso}  {tag:9s} {label}")
        return

    if args.next:
        nxt = next_us_open()
        sec = seconds_until_next_open()
        h = sec // 3600
        print(f"Prochain open US : {nxt.isoformat()}")
        print(f"Dans {h}h ({sec}s)")
        return

    # default : --check
    allowed, reason = guard_or_skip(dt=d)
    print(f"Date          : {d.isoformat()} ({d.strftime('%A')})")
    print(f"is_weekend    : {is_weekend(d)}")
    print(f"is_us_holiday : {is_us_holiday(d)}")
    print(f"early_close   : {is_us_early_close(d)}")
    print(f"market_open   : {is_us_market_open(d)}")
    print(f"label         : {get_holiday_label(d)}")
    print(f"GUARD         : allowed={allowed} reason='{reason}'")


if __name__ == "__main__":
    _main()
