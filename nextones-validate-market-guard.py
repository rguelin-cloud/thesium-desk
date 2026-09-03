# -*- coding: utf-8 -*-
# [NEXTONES-VALIDATE-MARKET-GUARD-V1]
# Validator complet du garde-fou marche US.
#
# Tests :
#   1. is_us_market_open : 12 feries NYSE 2026 + samedi/dimanche -> False
#   2. is_us_market_open : 10 jours ouvres -> True
#   3. guard_or_skip(force=True) : toujours allowed
#   4. next_us_open : depuis ven 22 mai -> mar 26 mai (Memorial Day lun 25)
#   5. seconds_until_next_open : > 0 et coherent
#   6. Import du module dans execution_engine (si marker present)
#
# Exit code 0 si tout OK, 1 sinon.

import datetime as dt
import importlib.util as ilu
import os
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MC_PATH = os.path.join(PROD, "nextones-market-calendar.py")
ENGINE = os.path.join(PROD, "execution_engine.py")

PASS = 0
FAIL = 0


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def check(label, cond, expected=None, got=None):
    global PASS, FAIL
    if cond:
        print(f"  [OK]   {label}")
        PASS += 1
    else:
        ex = f" expected={expected}" if expected is not None else ""
        gt = f" got={got}" if got is not None else ""
        print(f"  [FAIL] {label}{ex}{gt}")
        FAIL += 1


def main():
    banner("[1] Import nextones-market-calendar.py")
    if not os.path.exists(MC_PATH):
        print(f"[FATAL] introuvable : {MC_PATH}")
        sys.exit(2)
    spec = ilu.spec_from_file_location("mc", MC_PATH)
    mc = ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(mc)
        print("  import OK")
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(2)

    banner("[2] Feries NYSE 2026 (12 dates)")
    feries_2026 = [
        ("2026-01-01", "New Year"),
        ("2026-01-19", "MLK Day"),
        ("2026-02-16", "Presidents Day"),
        ("2026-04-03", "Good Friday"),
        ("2026-05-25", "Memorial Day"),
        ("2026-06-19", "Juneteenth"),
        ("2026-07-03", "Independence Day"),
        ("2026-09-07", "Labor Day"),
        ("2026-11-26", "Thanksgiving"),
        ("2026-12-25", "Christmas"),
    ]
    for (iso, label) in feries_2026:
        d = dt.date.fromisoformat(iso)
        check(f"{iso} ({label}) is_us_holiday=True",
              mc.is_us_holiday(d) is True)
        check(f"{iso} ({label}) is_us_market_open=False",
              mc.is_us_market_open(d) is False)
        allowed, reason = mc.guard_or_skip(dt=d)
        check(f"{iso} ({label}) guard.allowed=False",
              allowed is False, expected=False, got=allowed)

    banner("[3] Early close 2026 (Day after Thanksgiving + Christmas Eve)")
    for iso in ("2026-11-27", "2026-12-24"):
        d = dt.date.fromisoformat(iso)
        check(f"{iso} is_us_early_close=True",
              mc.is_us_early_close(d) is True)
        # Early close = jour ouvre quand meme
        check(f"{iso} is_us_market_open=True (early close mais ouvert)",
              mc.is_us_market_open(d) is True)
        allowed, reason = mc.guard_or_skip(dt=d)
        check(f"{iso} guard.allowed=True avec warning",
              allowed is True and "early_close" in reason,
              expected="allowed+early_close_warning", got=f"{allowed},{reason}")

    banner("[4] Weekends 2026 (4 samedis + 4 dimanches au hasard)")
    weekends = [
        "2026-01-03", "2026-03-14", "2026-06-06", "2026-09-19",  # samedis
        "2026-01-04", "2026-03-15", "2026-06-07", "2026-09-20",  # dimanches
    ]
    for iso in weekends:
        d = dt.date.fromisoformat(iso)
        check(f"{iso} is_weekend=True", mc.is_weekend(d) is True)
        check(f"{iso} is_us_market_open=False",
              mc.is_us_market_open(d) is False)

    banner("[5] Jours ouvres normaux 2026 (10 dates)")
    jours_ouvres = [
        "2026-01-05",  # lundi normal
        "2026-02-02",  # lundi normal
        "2026-03-10",  # mardi normal
        "2026-04-15",  # mercredi normal
        "2026-05-26",  # mardi (apres Memorial Day)
        "2026-06-22",  # lundi
        "2026-08-05",  # mercredi
        "2026-10-12",  # lundi
        "2026-11-30",  # lundi
        "2026-12-30",  # mercredi
    ]
    for iso in jours_ouvres:
        d = dt.date.fromisoformat(iso)
        check(f"{iso} is_us_market_open=True",
              mc.is_us_market_open(d) is True)
        allowed, reason = mc.guard_or_skip(dt=d)
        check(f"{iso} guard.allowed=True",
              allowed is True, expected=True, got=allowed)

    banner("[6] force=True bypass (weekend ET ferie)")
    for iso in ("2026-05-31", "2026-12-25", "2026-04-03"):
        d = dt.date.fromisoformat(iso)
        allowed, reason = mc.guard_or_skip(force=True, dt=d)
        check(f"force=True sur {iso} : allowed=True reason=forced",
              allowed is True and reason == "forced",
              expected="True,forced", got=f"{allowed},{reason}")

    banner("[7] next_us_open / seconds_until_next_open")
    # Depuis sam 30 mai 2026 12:00 UTC -> lun 1 juin
    base = dt.datetime(2026, 5, 30, 12, 0, 0, tzinfo=dt.timezone.utc)
    nxt = mc.next_us_open(base)
    check(f"next_us_open depuis sam 30/05 = lun 01/06",
          nxt.date() == dt.date(2026, 6, 1),
          expected="2026-06-01", got=nxt.date().isoformat())

    # Depuis ven 22 mai 22:00 UTC (lun 25 = Memorial Day) -> mar 26
    base = dt.datetime(2026, 5, 22, 22, 0, 0, tzinfo=dt.timezone.utc)
    nxt = mc.next_us_open(base)
    check(f"next_us_open depuis ven 22/05 22h (Memorial Day lun) = mar 26",
          nxt.date() == dt.date(2026, 5, 26),
          expected="2026-05-26", got=nxt.date().isoformat())

    # seconds_until_next_open > 0
    sec = mc.seconds_until_next_open(base)
    check(f"seconds_until_next_open > 0 (got {sec})",
          sec > 0, expected=">0", got=sec)

    banner("[8] Verification engine patche (si marker present)")
    if os.path.exists(ENGINE):
        with open(ENGINE, "r", encoding="utf-8-sig") as fh:
            engine_src = fh.read()
        has_marker = "[NEXTONES-MARKET-GUARD-V1]" in engine_src
        if has_marker:
            check("execution_engine.py contient le marker GUARD",
                  has_marker is True)
            # ast parse
            import ast as _ast
            try:
                _ast.parse(engine_src)
                check("execution_engine.py ast.parse OK", True)
            except SyntaxError as e:
                check("execution_engine.py ast.parse", False,
                      expected="OK", got=str(e))
        else:
            print("  [INFO] marker absent : engine pas encore patche")
    else:
        print(f"  [INFO] {ENGINE} introuvable")

    banner("RESUME")
    total = PASS + FAIL
    print(f"  PASS : {PASS} / {total}")
    print(f"  FAIL : {FAIL} / {total}")
    if FAIL == 0:
        print("  [OK] tous les tests passent")
        sys.exit(0)
    else:
        print(f"  [KO] {FAIL} test(s) en echec")
        sys.exit(1)


if __name__ == "__main__":
    main()
