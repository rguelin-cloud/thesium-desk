# -*- coding: utf-8 -*-
"""
nextones-fix-reject-reasons-v1.py
==================================
CORRECTIF 2/4 - Tracabilite des rejets + anti-reessai

PROBLEMES CORRIGES
------------------

A) rejection_reason inutilisable
   Diagnostic du 2026-09-03 sur 246 ordres rejetes :

       162  by=(null)     reason=(null)      <-- rejets AUTOMATIQUES
        26  by=rguelin    reason=xxxxx       <-- saisies manuelles de test
        23  by=rguelin    reason=x
         8  by=rguelin    reason=xxxxxx
       ...
         2  by=rguelin    reason=week end

   Les 162 rejets automatiques n'ont AUCUN motif. Impossible de
   diagnostiquer sans script externe. Le motif reel etait la saturation
   sectorielle Technology (250 628 USD / limite 249 827 USD), mais rien
   ne le tracait.

B) Contradiction dans risk_check_result
   Les ordres rejetes portent {"approved": true, "action": "approved"}.
   Le champ 'reasons' liste les limites APPLICABLES, pas les violations.
   Aucun moyen de distinguer une limite informative d'un blocage.

C) Reessais en boucle
   ARM : 87 rejets sur 91 tentatives, dont 6 le seul 2026-07-02
   (cycles 070105, 102228, 115659, 121926, 132851, 143826), toujours
   pour 54-58 titres. Le systeme regenere un ordre structurellement
   impossible a chaque cycle.

CE MODULE
---------
1. Backfill : reconstruit les motifs des 162 rejets historiques
2. Schema  : ajoute reject_code, reject_detail, reject_source
3. Anti-reessai : table order_suppression + fonction de garde
4. Vue SQL : v_reject_analysis pour le dashboard

SECURITE
--------
  - Ne modifie QUE orders.rejection_reason (si null) et les colonnes ajoutees
  - N'altere aucun statut, quantite, prix ou decision
  - Backup obligatoire avant --apply
  - dry-run par defaut

USAGE
-----
    py -3.13 nextones-fix-reject-reasons-v1.py --self-test
    py -3.13 nextones-fix-reject-reasons-v1.py --db thesium.db --dry-run
    py -3.13 nextones-fix-reject-reasons-v1.py --db thesium.db --apply

AUTEUR : audit Perplexity - 2026-09-03
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

MARKER = "REJECT_REASONS_V1"

# ----------------------------------------------------------------------------
# TAXONOMIE DES CODES DE REJET
# ----------------------------------------------------------------------------

REJECT_CODES = {
    "SECTOR_LIMIT":      "Limite sectorielle atteinte",
    "SINGLE_NAME_LIMIT": "Limite par nom atteinte",
    "POSITION_LIMIT":    "Limite de taille de position atteinte",
    "VAR_LIMIT":         "Budget de VaR depasse",
    "CASH_INSUFFICIENT": "Cash disponible insuffisant",
    "STOP_LOSS":         "Stop-loss declenche",
    "MANUAL_REJECT":     "Rejet manuel operateur",
    "DUPLICATE":         "Ordre duplique",
    "MARKET_CLOSED":     "Marche ferme",
    "NO_PRICE":          "Prix indisponible",
    "REGIME_BLOCK":      "Bloque par le regime de marche",
    "SUPPRESSED":        "Supprime par anti-reessai",
    "UNKNOWN":           "Motif indetermine",
}

# Motifs manuels reconnus comme du bruit de test.
NOISE_PATTERNS = ("x", "xx", "xxx", "xxxx", "xxxxx", "xxxxxx",
                  "xxxxxxx", "xxxxxxxx", "xxxxxxxxx", "test", "aaa")

# Fenetre de suppression apres rejet structurel (heures).
SUPPRESSION_HOURS = 24

# Nombre de rejets consecutifs avant suppression.
SUPPRESSION_THRESHOLD = 3


# ----------------------------------------------------------------------------
# CLASSIFICATION
# ----------------------------------------------------------------------------

def classify_manual_reason(raw: Optional[str]) -> Tuple[str, str]:
    """Classe un motif saisi a la main. Retourne (code, detail)."""
    if raw is None or not str(raw).strip():
        return ("UNKNOWN", "")
    s = str(raw).strip()
    low = s.lower()
    if low in NOISE_PATTERNS or (set(low) <= {"x"} and len(low) <= 12):
        return ("MANUAL_REJECT", "saisie de test: " + s)
    if "week" in low or "weekend" in low or "ferme" in low:
        return ("MARKET_CLOSED", s)
    if "cash" in low or "liquid" in low:
        return ("CASH_INSUFFICIENT", s)
    if "sector" in low or "secteur" in low:
        return ("SECTOR_LIMIT", s)
    if "var" in low:
        return ("VAR_LIMIT", s)
    if "stop" in low:
        return ("STOP_LOSS", s)
    if "duplic" in low:
        return ("DUPLICATE", s)
    return ("MANUAL_REJECT", s)


def infer_auto_reject(
    order: sqlite3.Row,
    sector_exposure_at_time: Optional[float],
    sector_limit_usd: Optional[float],
    sector_name: Optional[str],
) -> Tuple[str, str]:
    """
    Reconstruit le motif d'un rejet automatique a partir du contexte.

    Priorite d'inference :
      1. risk_check_result contient un blocage explicite
      2. saturation sectorielle connue
      3. limite par nom
      4. UNKNOWN
    """
    rcr = order["risk_check_result"] if "risk_check_result" in order.keys() else None
    metrics: Dict[str, float] = {}
    reasons: List[str] = []

    if rcr:
        try:
            d = json.loads(rcr)
            if isinstance(d, dict):
                metrics = d.get("metrics") or {}
                reasons = d.get("reasons") or []
                if d.get("approved") is False:
                    joined = " | ".join(str(x) for x in reasons)
                    for code in ("SECTOR_LIMIT", "SINGLE_NAME_LIMIT",
                                 "VAR_LIMIT", "CASH_INSUFFICIENT"):
                        token = code.split("_")[0].lower()
                        if token in joined.lower():
                            return (code, joined[:200])
                    return ("UNKNOWN", joined[:200])
        except Exception:
            pass

    # Saturation sectorielle : le cas dominant du diagnostic.
    if (sector_exposure_at_time is not None
            and sector_limit_usd is not None
            and sector_exposure_at_time >= sector_limit_usd):
        detail = "{}: {:.0f} USD / limite {:.0f} USD".format(
            sector_name or "?", sector_exposure_at_time, sector_limit_usd)
        return ("SECTOR_LIMIT", detail)

    # Limite par nom.
    pos_pct = metrics.get("position_size_pct")
    if pos_pct is not None:
        try:
            if float(pos_pct) >= 10.0:
                return ("SINGLE_NAME_LIMIT",
                        "position_size_pct={:.2f}".format(float(pos_pct)))
        except Exception:
            pass

    # Cash.
    cash_after = metrics.get("cash_after_trade")
    if cash_after is not None:
        try:
            if float(cash_after) < 0:
                return ("CASH_INSUFFICIENT",
                        "cash_after_trade={:.0f}".format(float(cash_after)))
        except Exception:
            pass

    if reasons:
        return ("UNKNOWN", " | ".join(str(x) for x in reasons)[:200])
    return ("UNKNOWN", "aucun contexte disponible")


# ----------------------------------------------------------------------------
# SCHEMA
# ----------------------------------------------------------------------------

NEW_COLUMNS = [
    ("reject_code",   "TEXT"),
    ("reject_detail", "TEXT"),
    ("reject_source", "TEXT"),
]

SUPPRESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS order_suppression (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT    NOT NULL,
    side            TEXT    NOT NULL,
    reject_code     TEXT    NOT NULL,
    n_consecutive   INTEGER NOT NULL DEFAULT 1,
    first_reject_at TEXT    NOT NULL,
    last_reject_at  TEXT    NOT NULL,
    suppressed_until TEXT   NOT NULL,
    detail          TEXT,
    engine_version  TEXT    NOT NULL DEFAULT 'REJECT_REASONS_V1',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(ticker, side, reject_code)
)
"""

SUPPRESSION_INDEX = """
CREATE INDEX IF NOT EXISTS idx_order_suppression_active
    ON order_suppression(ticker, side, suppressed_until)
"""

ANALYSIS_VIEW = """
CREATE VIEW IF NOT EXISTS v_reject_analysis AS
SELECT
    i.ticker,
    i.sector,
    o.side,
    COALESCE(o.reject_code, 'UNCLASSIFIED') AS reject_code,
    COALESCE(o.reject_source, 'unknown')    AS reject_source,
    COUNT(*)                                AS n_rejects,
    MIN(o.created_at)                       AS first_at,
    MAX(o.created_at)                       AS last_at,
    ROUND(AVG(o.quantity), 2)               AS avg_qty
FROM orders o
JOIN instruments i ON i.id = o.instrument_id
WHERE o.status = 'rejected'
GROUP BY i.ticker, i.sector, o.side, o.reject_code, o.reject_source
"""


def column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.cursor()
    cur.execute('PRAGMA table_info("{}")'.format(table))
    return any(r[1] == col for r in cur.fetchall())


def ensure_schema(conn: sqlite3.Connection, apply: bool) -> List[str]:
    """Ajoute les colonnes et objets manquants."""
    cur = conn.cursor()
    added: List[str] = []

    for col, typ in NEW_COLUMNS:
        if column_exists(conn, "orders", col):
            print("  colonne orders.{:16s} existe deja".format(col))
            continue
        if apply:
            cur.execute('ALTER TABLE orders ADD COLUMN "{}" {}'.format(col, typ))
            print("  colonne orders.{:16s} AJOUTEE".format(col))
            added.append(col)
        else:
            print("  [DRY-RUN] colonne orders.{:16s} serait ajoutee".format(col))

    if apply:
        cur.execute(SUPPRESSION_SCHEMA)
        cur.execute(SUPPRESSION_INDEX)
        print("  table order_suppression        OK")
        cur.execute("DROP VIEW IF EXISTS v_reject_analysis")
        cur.execute(ANALYSIS_VIEW)
        print("  vue v_reject_analysis          OK")
    else:
        print("  [DRY-RUN] table order_suppression et vue v_reject_analysis")

    return added


# ----------------------------------------------------------------------------
# BACKFILL
# ----------------------------------------------------------------------------

def get_sector_limit_usd(conn: sqlite3.Connection) -> Tuple[float, float]:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT total_value FROM portfolio_state WHERE id = 1"
    ).fetchone()
    nav = float(row[0] or 0.0)
    row2 = cur.execute(
        "SELECT max_sector_pct FROM risk_config WHERE id = 1"
    ).fetchone()
    pct = float(row2[0]) if row2 and row2[0] is not None else 25.0
    return nav, nav * pct / 100.0


def current_sector_exposure(conn: sqlite3.Connection) -> Dict[str, float]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT i.sector, SUM(pp.quantity * pp.current_price) mv
        FROM portfolio_positions pp
        JOIN instruments i ON i.id = pp.instrument_id
        GROUP BY i.sector
        """
    )
    return {(r[0] or "n/a"): float(r[1] or 0.0) for r in cur.fetchall()}


def backfill_reasons(conn: sqlite3.Connection, apply: bool) -> Dict[str, int]:
    """Reconstruit les motifs de tous les ordres rejetes."""
    cur = conn.cursor()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    nav, sector_limit = get_sector_limit_usd(conn)
    exposure = current_sector_exposure(conn)

    cur.execute(
        """
        SELECT o.id, o.instrument_id, o.side, o.quantity, o.created_at,
               o.validated_by, o.rejection_reason, o.risk_check_result,
               i.ticker, i.sector
        FROM orders o
        JOIN instruments i ON i.id = o.instrument_id
        WHERE o.status = 'rejected'
        ORDER BY o.id
        """
    )
    rows = cur.fetchall()

    counts: Dict[str, int] = {}
    updates: List[Tuple[int, str, str, str, str]] = []

    for r in rows:
        manual = r["validated_by"] is not None
        if manual:
            code, detail = classify_manual_reason(r["rejection_reason"])
            source = "manual:" + str(r["validated_by"])
        else:
            sector = r["sector"]
            exp = exposure.get(sector or "n/a")
            code, detail = infer_auto_reject(r, exp, sector_limit, sector)
            source = "auto:risk_engine"

        counts[code] = counts.get(code, 0) + 1

        new_reason = "{}: {}".format(code, detail) if detail else code
        updates.append((r["id"], code, detail[:500], source, new_reason[:500]))

    print()
    print("  {:22s} {:>7s}  {}".format("CODE", "N", "LIBELLE"))
    print("  " + "-" * 68)
    for code in sorted(counts, key=lambda k: -counts[k]):
        print("  {:22s} {:>7d}  {}".format(
            code, counts[code], REJECT_CODES.get(code, "?")))
    print("  " + "-" * 68)
    print("  {:22s} {:>7d}".format("TOTAL", sum(counts.values())))

    if apply:
        for oid, code, detail, source, reason in updates:
            cur.execute(
                """
                UPDATE orders
                SET reject_code = ?, reject_detail = ?, reject_source = ?,
                    rejection_reason = CASE
                        WHEN rejection_reason IS NULL
                          OR TRIM(rejection_reason) = ''
                        THEN ? ELSE rejection_reason END
                WHERE id = ?
                """,
                (code, detail, source, reason, oid),
            )
        print()
        print("  {} ordres enrichis.".format(len(updates)))
    else:
        print()
        print("  [DRY-RUN] {} ordres seraient enrichis.".format(len(updates)))

    return counts


# ----------------------------------------------------------------------------
# ANTI-REESSAI
# ----------------------------------------------------------------------------

def build_suppression_list(
    conn: sqlite3.Connection, apply: bool
) -> List[Tuple[str, str, str, int]]:
    """
    Detecte les couples (ticker, side) rejetes en boucle pour un motif
    structurel, et les inscrit dans order_suppression.

    Cas ARM : 87 rejets consecutifs pour SECTOR_LIMIT -> suppression.
    """
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT i.ticker, o.side,
               COALESCE(o.reject_code, 'UNKNOWN') AS code,
               COUNT(*) AS n,
               MIN(o.created_at) AS first_at,
               MAX(o.created_at) AS last_at
        FROM orders o
        JOIN instruments i ON i.id = o.instrument_id
        WHERE o.status = 'rejected'
        GROUP BY i.ticker, o.side, code
        HAVING n >= ?
        ORDER BY n DESC
        """,
        (SUPPRESSION_THRESHOLD,),
    )
    rows = cur.fetchall()

    structural = {"SECTOR_LIMIT", "SINGLE_NAME_LIMIT", "POSITION_LIMIT",
                  "VAR_LIMIT"}
    out: List[Tuple[str, str, str, int]] = []

    print()
    print("  {:10s} {:6s} {:20s} {:>6s}  {}".format(
        "TICKER", "SIDE", "CODE", "N", "ACTION"))
    print("  " + "-" * 68)

    for r in rows:
        code = r["code"]
        act = "supprime" if code in structural else "surveille"
        print("  {:10s} {:6s} {:20s} {:>6d}  {}".format(
            str(r["ticker"])[:10], str(r["side"])[:6], code[:20],
            r["n"], act))

        if code not in structural:
            continue

        out.append((r["ticker"], r["side"], code, r["n"]))

        if apply:
            until = datetime.now().isoformat(timespec="seconds")
            cur.execute(
                """
                INSERT INTO order_suppression
                  (ticker, side, reject_code, n_consecutive,
                   first_reject_at, last_reject_at, suppressed_until, detail)
                VALUES (?,?,?,?,?,?,
                        datetime('now', '+{} hours'), ?)
                ON CONFLICT(ticker, side, reject_code) DO UPDATE SET
                  n_consecutive = excluded.n_consecutive,
                  last_reject_at = excluded.last_reject_at,
                  suppressed_until = datetime('now', '+{} hours')
                """.format(SUPPRESSION_HOURS, SUPPRESSION_HOURS),
                (r["ticker"], r["side"], code, r["n"],
                 r["first_at"], r["last_at"],
                 "{} rejets consecutifs".format(r["n"])),
            )

    if apply and out:
        print()
        print("  {} couples (ticker, side) inscrits en suppression "
              "pour {}h.".format(len(out), SUPPRESSION_HOURS))
    elif out:
        print()
        print("  [DRY-RUN] {} couples seraient supprimes.".format(len(out)))

    return out


GUARD_SNIPPET = '''
# ---------------------------------------------------------------------------
# ANTI-REESSAI  -  a coller dans execution_engine.py
# Marqueur d'idempotence : REJECT_REASONS_V1_GUARD
# ---------------------------------------------------------------------------

def is_order_suppressed(conn, ticker, side):
    """
    Retourne (True, detail) si ce couple (ticker, side) est en periode
    de suppression apres rejets structurels repetes.

    A appeler AVANT de creer un ordre, dans la boucle de generation.
    Evite les 87 rejets ARM du diagnostic 2026-09-03.
    """
    try:
        row = conn.execute(
            """
            SELECT reject_code, n_consecutive, suppressed_until, detail
            FROM order_suppression
            WHERE ticker = ? AND side = ?
              AND suppressed_until > datetime('now')
            ORDER BY n_consecutive DESC LIMIT 1
            """,
            (ticker, side),
        ).fetchone()
    except Exception:
        return (False, None)
    if not row:
        return (False, None)
    return (True, "{}: {} rejets, supprime jusqu'a {}".format(
        row[0], row[1], row[2]))


def clear_suppression(conn, ticker, side=None):
    """Libere manuellement une suppression (apres correction de la cause)."""
    if side:
        conn.execute(
            "DELETE FROM order_suppression WHERE ticker = ? AND side = ?",
            (ticker, side))
    else:
        conn.execute(
            "DELETE FROM order_suppression WHERE ticker = ?", (ticker,))
    conn.commit()


# --- Integration dans la boucle de generation d'ordres ---
#
#   suppressed, detail = is_order_suppressed(conn, ticker, side)
#   if suppressed:
#       log("[SUPPRESSED] {} {} -> {}".format(ticker, side, detail))
#       continue
#
# --- Et lors d'un rejet, toujours renseigner le motif ---
#
#   cur.execute(
#       "UPDATE orders SET status='rejected', reject_code=?, "
#       "reject_detail=?, reject_source='auto:risk_engine', "
#       "rejection_reason=? WHERE id=?",
#       (code, detail, code + ": " + detail, order_id))
# ---------------------------------------------------------------------------
'''


# ----------------------------------------------------------------------------
# SELF-TEST
# ----------------------------------------------------------------------------

def self_test() -> bool:
    print("=" * 74)
    print("SELF-TEST  nextones-fix-reject-reasons-v1")
    print("=" * 74)
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print("  [{}] {}{}".format(
            "PASS" if cond else "FAIL", label, "  " + detail if detail else ""))

    print("\n--- classification des motifs manuels observes ---")
    for raw, expected in [
        ("xxxxx", "MANUAL_REJECT"),
        ("x", "MANUAL_REJECT"),
        ("XXXX", "MANUAL_REJECT"),
        ("xxxxxxxxx", "MANUAL_REJECT"),
        ("week end", "MARKET_CLOSED"),
        (None, "UNKNOWN"),
        ("", "UNKNOWN"),
    ]:
        code, detail = classify_manual_reason(raw)
        check("'{}' -> {}".format(raw, expected), code == expected,
              "code={}".format(code))

    print("\n--- inference du rejet automatique ---")

    class FakeRow(dict):
        def keys(self):
            return list(super().keys())
        def __getitem__(self, k):
            return super().get(k)

    # Cas ARM : saturation Technology
    r = FakeRow(risk_check_result=json.dumps({
        "approved": True, "action": "approved", "approved_quantity": 57,
        "reasons": ["Single-name limit: $100,000 max for this ticker",
                    "Sector limit: $250,000 max for Technology sector"],
        "metrics": {"order_value_usd": 37225.86, "portfolio_var_pct": 0.0,
                    "position_size_pct": 3.72, "cash_after_trade": 962774.14},
    }))
    code, detail = infer_auto_reject(r, 250628.0, 249827.0, "Technology")
    check("ARM sature -> SECTOR_LIMIT", code == "SECTOR_LIMIT", detail)
    check("detail contient les montants",
          "250628" in detail.replace(" ", "") or "250628" in detail
          or "250,628" in detail or "250628" in detail.replace(",", ""),
          detail)

    # Secteur non sature
    code2, _ = infer_auto_reject(r, 100000.0, 249827.0, "Energy")
    check("secteur non sature -> pas SECTOR_LIMIT",
          code2 != "SECTOR_LIMIT", "code={}".format(code2))

    # Position trop grosse
    r2 = FakeRow(risk_check_result=json.dumps({
        "approved": True, "reasons": [],
        "metrics": {"position_size_pct": 12.5},
    }))
    code3, d3 = infer_auto_reject(r2, 10000.0, 249827.0, "Energy")
    check("position 12.5% -> SINGLE_NAME_LIMIT",
          code3 == "SINGLE_NAME_LIMIT", d3)

    # Cash negatif
    r3 = FakeRow(risk_check_result=json.dumps({
        "approved": True, "reasons": [],
        "metrics": {"cash_after_trade": -5000.0},
    }))
    code4, d4 = infer_auto_reject(r3, 10000.0, 249827.0, "Energy")
    check("cash negatif -> CASH_INSUFFICIENT",
          code4 == "CASH_INSUFFICIENT", d4)

    # Aucun contexte
    r4 = FakeRow(risk_check_result=None)
    code5, _ = infer_auto_reject(r4, None, None, None)
    check("aucun contexte -> UNKNOWN", code5 == "UNKNOWN")

    print("\n--- taxonomie ---")
    check("tous les codes ont un libelle",
          all(c in REJECT_CODES for c in
              ("SECTOR_LIMIT", "SINGLE_NAME_LIMIT", "VAR_LIMIT",
               "CASH_INSUFFICIENT", "MANUAL_REJECT", "MARKET_CLOSED",
               "UNKNOWN", "SUPPRESSED")))
    check("13 codes definis", len(REJECT_CODES) == 13,
          "{} codes".format(len(REJECT_CODES)))

    print("=" * 74)
    print("RESULTAT :", "TOUS LES TESTS PASSENT" if ok else "ECHEC")
    print("=" * 74)
    return ok


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def backup_db(db_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = "{}.backup-reject-{}".format(db_path, ts)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Tracabilite des rejets et anti-reessai"
    )
    p.add_argument("--db", default="thesium.db")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--skip-backup", action="store_true")
    p.add_argument("--emit-guard", action="store_true",
                   help="ecrit le snippet anti-reessai dans un fichier")
    args = p.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    if not os.path.exists(args.db):
        print("ERREUR : base introuvable : {}".format(os.path.abspath(args.db)))
        return 1

    if not args.apply and not args.dry_run:
        args.dry_run = True

    print("=" * 74)
    print("TRACABILITE DES REJETS + ANTI-REESSAI")
    print("DB   : {}".format(os.path.abspath(args.db)))
    print("Mode : {}".format("APPLY" if args.apply else "DRY-RUN"))
    print("=" * 74)

    conn = sqlite3.connect(args.db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")

    try:
        if args.apply and not args.skip_backup:
            conn.commit()
            dest = backup_db(args.db)
            print()
            print("Backup : {}  ({:.1f} Mo)".format(
                dest, os.path.getsize(dest) / (1024.0 * 1024.0)))

        print()
        print("ETAPE 1 - SCHEMA")
        print("-" * 70)
        ensure_schema(conn, args.apply)

        print()
        print("ETAPE 2 - BACKFILL DES MOTIFS")
        print("-" * 70)
        nav, limit = get_sector_limit_usd(args and conn)
        print("  NAV = {:,.0f}   limite sectorielle = {:,.0f} USD".format(
            nav, limit))
        counts = backfill_reasons(conn, args.apply)

        print()
        print("ETAPE 3 - ANTI-REESSAI")
        print("-" * 70)
        if args.apply or True:
            supp = build_suppression_list(conn, args.apply)

        if args.emit_guard:
            path = "execution_engine_guard_snippet.py"
            with open(path, "w", encoding="utf-8") as f:
                f.write(GUARD_SNIPPET)
            print()
            print("  Snippet ecrit : {}".format(os.path.abspath(path)))

        if args.apply:
            conn.commit()
            print()
            print("COMMIT effectue.")
        else:
            conn.rollback()
            print()
            print("DRY-RUN : aucune ecriture.")

        print()
        print("=" * 74)
        print("SYNTHESE")
        print("=" * 74)
        print("  motifs reconstruits : {}".format(sum(counts.values())))
        for code in sorted(counts, key=lambda k: -counts[k])[:5]:
            print("    {:22s} {:>5d}".format(code, counts[code]))
        print("  suppressions        : {}".format(len(supp)))
        print()
        if args.dry_run:
            print("  Pour appliquer :")
            print("    py -3.13 {} --db {} --apply --emit-guard".format(
                os.path.basename(__file__), args.db))
        else:
            print("  Etape suivante :")
            print("    1. coller le snippet dans execution_engine.py")
            print("    2. py -3.13 nextones-fix-regime-multipliers-v1.py "
                  "--db {} --dry-run".format(args.db))
        print("=" * 74)
        return 0

    except Exception as exc:
        conn.rollback()
        print()
        print("ERREUR : {}".format(exc))
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
