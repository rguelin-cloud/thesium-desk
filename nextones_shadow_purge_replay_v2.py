# -*- coding: utf-8 -*-
"""
nextones-shadow-purge-replay-v2.py
===================================
JALON 9 - Phase 9.7 - PURGE, REJEU ET VALIDATION

ROLE
----
Orchestre la remise a zero propre du sous-systeme shadow :

  1. AUDIT      inventorie les donnees corrompues (NAV <= 0, DD < -100%,
                notes 'mvp_*', recommandations sur donnees invalides)
  2. BACKUP     archive les tables shadow_* legacy avant toute purge
  3. PURGE      vide shadow_perf_rolling et shadow_cycle_snapshots legacy
  4. REJEU      relance le moteur NAV V2 puis le perf rolling V2
  5. VALIDATION verifie 12 invariants et refuse de conclure si un echoue

SECURITE
--------
  - Ne touche JAMAIS aux tables de production :
      portfolio_history, portfolio_state, portfolio_positions,
      orders, fills, theses, event_log
  - Backup obligatoire avant purge (tables *_legacy_YYYYMMDD)
  - --apply requis pour toute ecriture, dry-run par defaut
  - Rollback automatique sur exception

USAGE
-----
    py -3.13 nextones-shadow-purge-replay-v2.py --db thesium.db --audit
    py -3.13 nextones-shadow-purge-replay-v2.py --db thesium.db --dry-run
    py -3.13 nextones-shadow-purge-replay-v2.py --db thesium.db --apply
    py -3.13 nextones-shadow-purge-replay-v2.py --db thesium.db --validate-only

AUTEUR : audit Perplexity - 2026-09-03
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

MARKER = "SHADOW_PURGE_V2"

NAV_ENGINE = "nextones-shadow-nav-engine-v2.py"
PERF_ENGINE = "nextones-shadow-perf-rolling-v2.py"

# Tables de production : interdiction absolue de modification.
PROTECTED_TABLES = {
    "portfolio_history", "portfolio_state", "portfolio_positions",
    "orders", "fills", "theses", "event_log", "instruments", "prices",
    "ic_memos", "risk_config", "users", "convergence_snapshots",
    "portfolio_targets", "portfolio_targets_history",
}

# Tables shadow legacy a purger apres backup.
LEGACY_TABLES = [
    "shadow_perf_rolling",
    "shadow_cycle_snapshots",
]

MIN_NAV = 1.0
MAX_DD_FLOOR_PCT = -100.0
MAX_ABS_RETURN_PCT = 500.0


# ----------------------------------------------------------------------------
# UTILITAIRES
# ----------------------------------------------------------------------------

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def row_count(conn: sqlite3.Connection, name: str) -> int:
    if not table_exists(conn, name):
        return -1
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "{name}"')
    return int(cur.fetchone()[0])


def backup_db_file(db_path: str) -> str:
    """Copie physique de la base via l'API backup de SQLite."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = f"{db_path}.backup-{ts}"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


# ----------------------------------------------------------------------------
# 1. AUDIT
# ----------------------------------------------------------------------------

def audit(conn: sqlite3.Connection) -> dict:
    print("=" * 74)
    print("ETAPE 1 - AUDIT DES DONNEES SHADOW")
    print("=" * 74)

    findings: Dict[str, object] = {}
    cur = conn.cursor()

    # --- shadow_perf_rolling ---
    if table_exists(conn, "shadow_perf_rolling"):
        total = row_count(conn, "shadow_perf_rolling")
        cur.execute(
            "SELECT COUNT(*) FROM shadow_perf_rolling "
            "WHERE nav_variant <= 0 OR nav_prod <= 0"
        )
        neg_nav = int(cur.fetchone()[0])
        cur.execute(
            "SELECT COUNT(*) FROM shadow_perf_rolling "
            "WHERE max_dd_variant_pct < ? OR max_dd_prod_pct < ?",
            (MAX_DD_FLOOR_PCT, MAX_DD_FLOOR_PCT),
        )
        bad_dd = int(cur.fetchone()[0])
        cur.execute(
            "SELECT COUNT(*) FROM shadow_perf_rolling "
            "WHERE ABS(COALESCE(return_variant_pct,0)) > ?",
            (MAX_ABS_RETURN_PCT,),
        )
        bad_ret = int(cur.fetchone()[0])
        cur.execute(
            "SELECT COUNT(*) FROM shadow_perf_rolling "
            "WHERE recommendation IS NOT NULL "
            "AND (nav_variant <= 0 OR nav_prod <= 0)"
        )
        bad_reco = int(cur.fetchone()[0])

        print(f"\nshadow_perf_rolling : {total} lignes")
        print(f"  NAV <= 0                         : {neg_nav}")
        print(f"  max_dd < -100%                   : {bad_dd}")
        print(f"  |rendement| > {MAX_ABS_RETURN_PCT:.0f}%             : {bad_ret}")
        print(f"  recommandation sur NAV negative  : {bad_reco}  <-- CRITIQUE")

        cur.execute(
            "SELECT variant_id, as_of_day, nav_variant, return_variant_pct, "
            "max_dd_variant_pct, recommendation FROM shadow_perf_rolling "
            "WHERE nav_variant <= 0 ORDER BY as_of_day DESC LIMIT 5"
        )
        rows = cur.fetchall()
        if rows:
            print("\n  Exemples de lignes corrompues :")
            for r in rows:
                print(f"    v{r[0]} {r[1]}  nav={r[2]:>14,.0f}  "
                      f"ret={r[3]:>9.2f}%  dd={r[4]:>9.2f}%  reco={r[5]}")

        findings["perf_rolling"] = {
            "total": total, "neg_nav": neg_nav, "bad_dd": bad_dd,
            "bad_ret": bad_ret, "bad_reco": bad_reco,
        }

    # --- shadow_cycle_snapshots ---
    if table_exists(conn, "shadow_cycle_snapshots"):
        total = row_count(conn, "shadow_cycle_snapshots")
        cur.execute(
            "SELECT COUNT(*) FROM shadow_cycle_snapshots "
            "WHERE notes LIKE 'mvp%' OR notes LIKE '%no_fills%'"
        )
        placeholders = int(cur.fetchone()[0])
        cur.execute(
            "SELECT COUNT(*) FROM shadow_cycle_snapshots "
            "WHERE nav = 1000000.0 AND cash = 1000000.0"
        )
        frozen = int(cur.fetchone()[0])
        cur.execute(
            "SELECT COUNT(*) FROM shadow_cycle_snapshots "
            "WHERE n_positions = 0 AND invested_pct = 0"
        )
        empty = int(cur.fetchone()[0])

        print(f"\nshadow_cycle_snapshots : {total} lignes")
        print(f"  notes 'mvp_*' / 'no_fills'       : {placeholders}")
        print(f"  NAV = cash = 1 000 000 exact     : {frozen}  <-- PLACEHOLDER")
        print(f"  n_positions = 0 et investi = 0   : {empty}")

        findings["snapshots"] = {
            "total": total, "placeholders": placeholders,
            "frozen": frozen, "empty": empty,
        }

    # --- production : controle de non-contamination ---
    print("\nCONTROLE PRODUCTION (doit rester saine)")
    if table_exists(conn, "portfolio_history"):
        cur.execute(
            "SELECT COUNT(*), MIN(total_value), MAX(total_value) "
            "FROM portfolio_history"
        )
        n, mn, mx = cur.fetchone()
        neg = 0
        cur.execute("SELECT COUNT(*) FROM portfolio_history WHERE total_value <= 0")
        neg = int(cur.fetchone()[0])
        print(f"  portfolio_history : {n} lignes, "
              f"NAV entre {mn:,.0f} et {mx:,.0f}")
        print(f"  NAV <= 0 en production : {neg} "
              f"{'-> OK' if neg == 0 else '-> ANOMALIE'}")
        findings["prod_healthy"] = (neg == 0)

    # --- verdict ---
    pr = findings.get("perf_rolling", {})
    sn = findings.get("snapshots", {})
    corrupted = (
        int(pr.get("neg_nav", 0)) + int(pr.get("bad_dd", 0))
        + int(sn.get("frozen", 0))
    )
    findings["needs_purge"] = corrupted > 0

    print("\n" + "-" * 74)
    if corrupted > 0:
        print(f"VERDICT : {corrupted} anomalies detectees -> PURGE ET REJEU REQUIS")
    else:
        print("VERDICT : aucune anomalie detectee")
    print("-" * 74)

    return findings


# ----------------------------------------------------------------------------
# 2. BACKUP DES TABLES
# ----------------------------------------------------------------------------

def backup_tables(conn: sqlite3.Connection, apply: bool) -> List[str]:
    print("\n" + "=" * 74)
    print("ETAPE 2 - BACKUP DES TABLES SHADOW LEGACY")
    print("=" * 74)

    ts = datetime.now().strftime("%Y%m%d")
    created: List[str] = []
    cur = conn.cursor()

    for t in LEGACY_TABLES:
        if t in PROTECTED_TABLES:
            print(f"  REFUS : {t} est une table protegee")
            continue
        if not table_exists(conn, t):
            print(f"  {t:32s} absente, ignoree")
            continue

        legacy = f"{t}_legacy_{ts}"
        n = row_count(conn, t)

        if table_exists(conn, legacy):
            print(f"  {legacy:32s} existe deja, conservee")
            created.append(legacy)
            continue

        if apply:
            cur.execute(f'CREATE TABLE "{legacy}" AS SELECT * FROM "{t}"')
            print(f"  {t:32s} -> {legacy}  ({n} lignes)")
            created.append(legacy)
        else:
            print(f"  [DRY-RUN] {t:24s} -> {legacy}  ({n} lignes)")

    return created


# ----------------------------------------------------------------------------
# 3. PURGE
# ----------------------------------------------------------------------------

def purge(conn: sqlite3.Connection, apply: bool) -> Dict[str, int]:
    print("\n" + "=" * 74)
    print("ETAPE 3 - PURGE DES TABLES CORROMPUES")
    print("=" * 74)

    cur = conn.cursor()
    purged: Dict[str, int] = {}

    for t in LEGACY_TABLES:
        if t in PROTECTED_TABLES:
            print(f"  REFUS : {t} protegee")
            continue
        if not table_exists(conn, t):
            continue
        n = row_count(conn, t)
        if apply:
            cur.execute(f'DELETE FROM "{t}"')
            print(f"  {t:32s} {n} lignes supprimees")
        else:
            print(f"  [DRY-RUN] {t:24s} {n} lignes seraient supprimees")
        purged[t] = n

    # Tables V2 : reconstruites integralement au rejeu.
    for t in ("shadow_nav_series_v2", "shadow_perf_rolling_v2"):
        if table_exists(conn, t):
            n = row_count(conn, t)
            if apply:
                cur.execute(f'DELETE FROM "{t}"')
                print(f"  {t:32s} {n} lignes supprimees (reconstruction)")
            else:
                print(f"  [DRY-RUN] {t:24s} {n} lignes (reconstruction)")
            purged[t] = n

    return purged


# ----------------------------------------------------------------------------
# 4. REJEU
# ----------------------------------------------------------------------------

def run_engine(script: str, db: str, apply: bool,
               extra: Optional[List[str]] = None) -> Tuple[int, str]:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, script)
    if not os.path.exists(path):
        return (-1, f"script introuvable : {path}")

    cmd = [sys.executable, path, "--db", db]
    cmd.append("--apply" if apply else "--dry-run")
    if extra:
        cmd.extend(extra)

    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=900, encoding="utf-8", errors="replace")
        return (r.returncode, (r.stdout or "") + (r.stderr or ""))
    except subprocess.TimeoutExpired:
        return (-2, "TIMEOUT 900s")
    except Exception as exc:
        return (-3, f"exception : {exc}")


def replay(db: str, apply: bool, verbose: bool) -> bool:
    print("\n" + "=" * 74)
    print("ETAPE 4 - REJEU AVEC LES MOTEURS V2")
    print("=" * 74)

    ok = True

    print(f"\n--- {NAV_ENGINE} ---")
    rc, out = run_engine(NAV_ENGINE, db, apply)
    if verbose:
        print(out)
    else:
        for line in out.splitlines():
            if any(k in line for k in ("NAV finale", "cycles", "Sharpe",
                                       "drawdown", "ERREUR", "INVALID",
                                       "persiste", "COMMIT")):
                print("   ", line.strip())
    if rc != 0:
        print(f"    ECHEC (rc={rc})")
        ok = False
    else:
        print("    OK")

    print(f"\n--- {PERF_ENGINE} ---")
    rc2, out2 = run_engine(PERF_ENGINE, db, apply)
    if verbose:
        print(out2)
    else:
        for line in out2.splitlines():
            if any(k in line for k in ("champion", "reject", "neutral",
                                       "promising", "insufficient",
                                       "invalid_data", "ERREUR", "COMMIT",
                                       "lignes")):
                print("   ", line.strip())
    if rc2 != 0:
        print(f"    ECHEC (rc={rc2})")
        ok = False
    else:
        print("    OK")

    return ok


# ----------------------------------------------------------------------------
# 5. VALIDATION
# ----------------------------------------------------------------------------

def validate(conn: sqlite3.Connection) -> bool:
    print("\n" + "=" * 74)
    print("ETAPE 5 - VALIDATION DES INVARIANTS")
    print("=" * 74)

    cur = conn.cursor()
    results: List[Tuple[str, bool, str]] = []

    def add(label: str, cond: bool, detail: str = "") -> None:
        results.append((label, cond, detail))

    # --- production intacte ---
    if table_exists(conn, "portfolio_history"):
        cur.execute("SELECT COUNT(*) FROM portfolio_history WHERE total_value <= 0")
        add("production : aucune NAV <= 0", int(cur.fetchone()[0]) == 0)
        cur.execute("SELECT COUNT(*) FROM portfolio_history")
        n = int(cur.fetchone()[0])
        add("production : historique preserve", n > 0, f"{n} lignes")

    for t in ("orders", "fills", "theses"):
        if table_exists(conn, t):
            n = row_count(conn, t)
            add(f"production : {t} preservee", n > 0, f"{n} lignes")

    # --- serie NAV V2 ---
    if table_exists(conn, "shadow_nav_series_v2"):
        n = row_count(conn, "shadow_nav_series_v2")
        add("shadow_nav_series_v2 peuplee", n > 0, f"{n} lignes")

        cur.execute("SELECT COUNT(*) FROM shadow_nav_series_v2 WHERE nav <= 0")
        add("V2 : aucune NAV <= 0", int(cur.fetchone()[0]) == 0)

        cur.execute("SELECT COUNT(*) FROM shadow_nav_series_v2 WHERE cash < -0.01")
        add("V2 : aucun cash negatif", int(cur.fetchone()[0]) == 0)

        cur.execute(
            "SELECT COUNT(*) FROM shadow_nav_series_v2 "
            "WHERE nav = 1000000.0 AND cash = 1000000.0"
        )
        add("V2 : plus de placeholder 1M/1M", int(cur.fetchone()[0]) == 0)

        cur.execute("SELECT COUNT(*) FROM shadow_nav_series_v2 WHERE valid = 0")
        n_inv = int(cur.fetchone()[0])
        add("V2 : cycles invalides tracés", True, f"{n_inv} marqués valid=0")
    else:
        add("shadow_nav_series_v2 existe", False, "table absente")

    # --- perf rolling V2 ---
    if table_exists(conn, "shadow_perf_rolling_v2"):
        n = row_count(conn, "shadow_perf_rolling_v2")
        add("shadow_perf_rolling_v2 peuplee", n > 0, f"{n} lignes")

        cur.execute(
            "SELECT COUNT(*) FROM shadow_perf_rolling_v2 "
            "WHERE max_dd_variant_pct < ?", (MAX_DD_FLOOR_PCT,)
        )
        add("V2 : aucun drawdown < -100%", int(cur.fetchone()[0]) == 0)

        cur.execute(
            "SELECT COUNT(*) FROM shadow_perf_rolling_v2 "
            "WHERE recommendation = 'champion' "
            "AND (data_quality != 'OK' OR nav_variant <= 0 OR nav_prod <= 0)"
        )
        add("V2 : aucun champion sur donnees invalides",
            int(cur.fetchone()[0]) == 0)

        cur.execute(
            "SELECT COUNT(*) FROM shadow_perf_rolling_v2 "
            "WHERE recommendation = 'champion' AND n_cycles < 60"
        )
        add("V2 : aucun champion sous 60 cycles",
            int(cur.fetchone()[0]) == 0)

        cur.execute(
            "SELECT recommendation, data_quality, COUNT(*) "
            "FROM shadow_perf_rolling_v2 "
            "GROUP BY recommendation, data_quality ORDER BY 3 DESC"
        )
        dist = cur.fetchall()
        if dist:
            print("\n  Distribution des recommandations V2 :")
            for reco, q, c in dist:
                print(f"    {reco:<14s} {q:<9s} {c:>4d}")
    else:
        add("shadow_perf_rolling_v2 existe", False, "table absente")

    # --- legacy purgee ---
    if table_exists(conn, "shadow_perf_rolling"):
        n = row_count(conn, "shadow_perf_rolling")
        add("legacy shadow_perf_rolling videe", n == 0, f"{n} lignes")

    print()
    all_ok = True
    for label, cond, detail in results:
        if not cond:
            all_ok = False
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}"
              f"{('  -> ' + detail) if detail else ''}")

    print("\n" + "=" * 74)
    print("VALIDATION :", "TOUS LES INVARIANTS PASSENT" if all_ok
          else "ECHEC - NE PAS EXPLOITER LES RESULTATS")
    print("=" * 74)
    return all_ok


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Purge, rejeu et validation du sous-systeme shadow"
    )
    p.add_argument("--db", default="thesium.db")
    p.add_argument("--apply", action="store_true", help="execute les ecritures")
    p.add_argument("--dry-run", action="store_true", help="simulation")
    p.add_argument("--audit", action="store_true", help="audit seul")
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--skip-backup", action="store_true",
                   help="DANGEREUX : pas de backup fichier")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if not os.path.exists(args.db):
        print(f"ERREUR : base introuvable : {os.path.abspath(args.db)}")
        return 1

    if not any([args.apply, args.dry_run, args.audit, args.validate_only]):
        args.dry_run = True

    print("=" * 74)
    print("NEXTONES SHADOW - PURGE / REJEU / VALIDATION  (V2)")
    print(f"DB   : {os.path.abspath(args.db)}")
    print(f"Mode : {'APPLY' if args.apply else 'DRY-RUN / LECTURE'}")
    print(f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 74)

    conn = sqlite3.connect(args.db, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")

    try:
        if args.validate_only:
            return 0 if validate(conn) else 1

        findings = audit(conn)

        if args.audit:
            print("\nAudit termine. Pour corriger :")
            print(f"  py -3.13 {os.path.basename(__file__)} "
                  f"--db {args.db} --dry-run")
            return 0

        if not findings.get("needs_purge"):
            print("\nAucune purge necessaire. Rejeu V2 quand meme conseille.")

        # Backup fichier avant toute ecriture.
        if args.apply and not args.skip_backup:
            print("\n" + "=" * 74)
            print("BACKUP FICHIER DE LA BASE")
            print("=" * 74)
            conn.commit()
            dest = backup_db_file(args.db)
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            print(f"  {dest}  ({size_mb:.1f} Mo)")

        backup_tables(conn, args.apply)
        purge(conn, args.apply)

        if args.apply:
            conn.commit()
            print("\nCOMMIT purge effectue.")
        else:
            conn.rollback()

        conn.close()

        replay_ok = replay(args.db, args.apply, args.verbose)

        conn = sqlite3.connect(args.db, timeout=60.0)
        conn.row_factory = sqlite3.Row
        valid_ok = validate(conn)

        print("\n" + "=" * 74)
        print("SYNTHESE")
        print("=" * 74)
        print(f"  audit          : anomalies "
              f"{'detectees' if findings.get('needs_purge') else 'aucune'}")
        print(f"  purge / rejeu  : {'OK' if replay_ok else 'ECHEC'}")
        print(f"  validation     : {'OK' if valid_ok else 'ECHEC'}")

        if args.dry_run:
            print("\nDRY-RUN : rien n'a ete ecrit.")
            print("Pour appliquer :")
            print(f"  py -3.13 {os.path.basename(__file__)} "
                  f"--db {args.db} --apply")
        elif replay_ok and valid_ok:
            print("\nCorrection appliquee et validee.")
            print("Prochaine etape : mettre a jour l'UI et l'API pour lire")
            print("shadow_perf_rolling_v2 au lieu de shadow_perf_rolling,")
            print("et masquer toute ligne dont data_quality != 'OK'.")
        else:
            print("\nATTENTION : rejeu ou validation en echec.")
            print("Un backup fichier a ete cree avant modification.")

        print("=" * 74)
        return 0 if (replay_ok and valid_ok) else 1

    except Exception as exc:
        conn.rollback()
        print(f"\nERREUR : {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
