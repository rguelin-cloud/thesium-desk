# nextones-diag-xlb-xli-excluded.py
# Comprend pourquoi XLB et XLI sont evalues mais exclus du snapshot
# - confirme N_BARS via instrument_id (schema reel)
# - cherche dans event_log / logs
# - inspecte universe_candidates pour ces tickers
# - regarde le code de l'agent pour trouver le filtre
# ASCII pur.

import sqlite3
import os
import sys
import re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
AGENT_FILE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"

if not os.path.exists(DB):
    print(f"DB introuvable: {DB}")
    sys.exit(1)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

TICKERS = ["XLB", "XLI", "XLE", "XLK", "HYPE", "SOL", "ZEC"]

# 1) Confirmer N_BARS via instrument_id (le bon schema)
print("=" * 70)
print("N_BARS via instrument_id (schema reel)")
print("=" * 70)
print(f"{'TICKER':<8} {'IID':>4} {'N_BARS':>8} {'FIRST':<12} {'LAST':<12} {'NULLS_CLOSE':>12}")
print("-" * 70)
for t in TICKERS:
    r_i = cur.execute("SELECT id FROM instruments WHERE ticker = ?", (t,)).fetchone()
    if not r_i:
        print(f"{t:<8} {'-':>4} {'absent':>8}")
        continue
    iid = r_i["id"]
    r = cur.execute(
        "SELECT COUNT(*) AS n, MIN(date) AS fd, MAX(date) AS ld, "
        "SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) AS nulls "
        "FROM prices WHERE instrument_id = ?",
        (iid,)
    ).fetchone()
    n = r["n"] or 0
    fd = r["fd"] or "-"
    ld = r["ld"] or "-"
    nulls = r["nulls"] or 0
    print(f"{t:<8} {iid:>4} {n:>8} {str(fd):<12} {str(ld):<12} {nulls:>12}")
print()

# 2) event_log : chercher exclusions explicites
print("=" * 70)
print("event_log derniers evenements (60 dernieres minutes)")
print("=" * 70)
try:
    cols = cur.execute("PRAGMA table_info(event_log)").fetchall()
    ev_cols = [c['name'] for c in cols]
    print(f"colonnes event_log: {ev_cols}")
    # Trouver une colonne temps
    tcol = None
    for c in ["ts", "created_at", "timestamp", "at"]:
        if c in ev_cols: tcol = c; break
    if tcol:
        rows = cur.execute(
            f"SELECT * FROM event_log WHERE {tcol} >= datetime('now', '-90 minutes') ORDER BY {tcol} DESC LIMIT 30"
        ).fetchall()
        for r in rows:
            d = dict(r)
            # Print compact
            s = " | ".join(f"{k}={str(v)[:40]}" for k, v in d.items() if v is not None)
            print(f"  {s}")
    else:
        print("  pas de colonne temps trouvee")
except sqlite3.OperationalError as e:
    print(f"  ERR: {e}")
print()

# 3) Filtrer event_log pour XLB / XLI
print("=" * 70)
print("event_log filtre sur XLB/XLI/XLE/XLK")
print("=" * 70)
try:
    rows = cur.execute(
        "SELECT * FROM event_log WHERE "
        "CAST(rowid AS TEXT) IS NOT NULL "
        "ORDER BY rowid DESC LIMIT 200"
    ).fetchall()
    hits = []
    for r in rows:
        d = dict(r)
        text = " ".join(str(v) for v in d.values() if v is not None)
        for tk in ["XLB", "XLI", "XLE", "XLK"]:
            if tk in text:
                hits.append((tk, d))
                break
    if hits:
        for (tk, d) in hits[:20]:
            s = " | ".join(f"{k}={str(v)[:60]}" for k, v in d.items() if v is not None)
            print(f"  [{tk}] {s}")
    else:
        print("  Aucun event mentionnant XLB/XLI/XLE/XLK dans les 200 derniers")
except sqlite3.OperationalError as e:
    print(f"  ERR: {e}")
print()

# 4) universe_candidates pour XLB/XLI/XLE/XLK
print("=" * 70)
print("universe_candidates pour XLB/XLI/XLE/XLK")
print("=" * 70)
for tk in ["XLB", "XLI", "XLE", "XLK"]:
    rows = cur.execute(
        "SELECT ticker, score, momentum_12m_minus_1m, realized_vol_90d, sharpe_90d, "
        "max_correl_existing, max_correl_with, suggested_cap_pct, status, reviewed_at "
        "FROM universe_candidates WHERE ticker = ? ORDER BY id DESC LIMIT 3",
        (tk,)
    ).fetchall()
    if rows:
        for r in rows:
            print(f"  {tk} score={r['score']} mom={r['momentum_12m_minus_1m']} vol90={r['realized_vol_90d']} "
                  f"sharpe={r['sharpe_90d']} corr_max={r['max_correl_existing']} (vs {r['max_correl_with']}) "
                  f"cap={r['suggested_cap_pct']} status={r['status']}")
    else:
        print(f"  {tk}: aucun candidat")
print()

# 5) Inspection du code de l'agent pour trouver le filtre top-N / score min
print("=" * 70)
print("CODE AGENT - patterns d'exclusion")
print("=" * 70)
if not os.path.exists(AGENT_FILE):
    # Essayer d'autres emplacements
    candidates = [
        r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\agents\portfolio_construction_agent.py",
        r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\src\portfolio_construction_agent.py",
    ]
    for c in candidates:
        if os.path.exists(c):
            AGENT_FILE = c
            break

if os.path.exists(AGENT_FILE):
    print(f"Fichier agent: {AGENT_FILE}")
    with open(AGENT_FILE, "r", encoding="utf-8-sig") as f:
        src = f.read()
    patterns = [
        (r"top.?n", "TOP_N"),
        (r"max.?per.?class", "MAX_PER_CLASS"),
        (r"max.?etf", "MAX_ETF"),
        (r"score.?min", "SCORE_MIN"),
        (r"min.?score", "MIN_SCORE"),
        (r"correl.?max", "CORREL_MAX"),
        (r"if .* < ", "THRESHOLD_LT"),
        (r"sorted\(.*key=.*score", "SORT_BY_SCORE"),
        (r"\[:[0-9]+\]", "SLICE"),
        (r"head\([0-9]+\)", "HEAD"),
    ]
    lines = src.splitlines()
    for pat, label in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        hits = [(i+1, l.strip()) for i, l in enumerate(lines) if rx.search(l)]
        if hits:
            print(f"--- {label} ({pat}) ---")
            for ln, txt in hits[:5]:
                if len(txt) < 200:
                    print(f"  L{ln}: {txt}")
    # Constantes connues
    print()
    print("--- Constantes max_* ---")
    for ln, l in enumerate(lines, 1):
        s = l.strip()
        if re.match(r"^[A-Z_]+\s*=\s*[0-9.]+", s) and ("MAX" in s or "MIN" in s or "TOP" in s or "CAP" in s):
            print(f"  L{ln}: {s}")
else:
    print(f"Fichier agent introuvable, essaye {AGENT_FILE}")
print()

# 6) target_construction_config
print("=" * 70)
print("target_construction_config (parametres agent)")
print("=" * 70)
try:
    rows = cur.execute("SELECT * FROM target_construction_config").fetchall()
    for r in rows:
        print(f"  {dict(r)}")
    if not rows:
        print("  (vide)")
except sqlite3.OperationalError as e:
    print(f"  ERR: {e}")
print()

con.close()
print("Done.")
