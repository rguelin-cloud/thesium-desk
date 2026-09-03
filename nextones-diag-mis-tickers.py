# nextones-diag-mis-tickers.py
# Diagnostique pourquoi HYPE, XLB, XLE, XLI, XLK sont absents du snapshot
# - decouvre le schema reel de la table prices
# - compte l'historique disponible pour chaque ticker MIS + benchmarks
# - verifie la presence dans instruments + target_universe
# ASCII pur. Read utf-8-sig, write utf-8 sans BOM.

import sqlite3
import os
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

if not os.path.exists(DB):
    print(f"DB introuvable: {DB}")
    sys.exit(1)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

MIS = ["HYPE", "XLB", "XLE", "XLI", "XLK"]
BENCH = ["SOL", "ZEC", "BTC", "AAPL", "META"]
ALL_T = MIS + BENCH

# 1) Schema de prices
print("=" * 70)
print("SCHEMA TABLE prices")
print("=" * 70)
cols = cur.execute("PRAGMA table_info(prices)").fetchall()
col_names = []
for c in cols:
    print(f"  {c['cid']:>2} {c['name']:<20} {c['type']:<15} pk={c['pk']}")
    col_names.append(c['name'])
print()

# Identifier la colonne ticker et la colonne date
ticker_col = None
for cand in ["ticker", "symbol", "instrument", "asset"]:
    if cand in col_names:
        ticker_col = cand
        break

date_col = None
for cand in ["date", "ts", "timestamp", "dt", "datetime"]:
    if cand in col_names:
        date_col = cand
        break

# Peut etre que la table indexe par instrument_id et pas par ticker
instr_id_col = None
for cand in ["instrument_id", "iid"]:
    if cand in col_names:
        instr_id_col = cand
        break

print(f"col ticker detectee     : {ticker_col}")
print(f"col date detectee       : {date_col}")
print(f"col instrument_id       : {instr_id_col}")
print()

# 2) Schema instruments
print("=" * 70)
print("SCHEMA TABLE instruments")
print("=" * 70)
cols_i = cur.execute("PRAGMA table_info(instruments)").fetchall()
icol_names = []
for c in cols_i:
    print(f"  {c['cid']:>2} {c['name']:<20} {c['type']:<15} pk={c['pk']}")
    icol_names.append(c['name'])
print()

# 3) Lookup instruments pour tous les tickers
print("=" * 70)
print("instruments LOOKUP")
print("=" * 70)
print(f"{'TICKER':<10} {'ID':>5} {'NAME':<30} {'ASSET_CLASS':<15}")
print("-" * 70)
ticker_to_id = {}
# detecter colonnes
icol_ticker = "ticker" if "ticker" in icol_names else ("symbol" if "symbol" in icol_names else None)
icol_id = "id" if "id" in icol_names else None
icol_name = "name" if "name" in icol_names else None
icol_class = "asset_class" if "asset_class" in icol_names else None

for t in ALL_T:
    try:
        sel_cols = []
        if icol_id: sel_cols.append(icol_id)
        if icol_name: sel_cols.append(icol_name)
        if icol_class: sel_cols.append(icol_class)
        sql = f"SELECT {', '.join(sel_cols)} FROM instruments WHERE {icol_ticker} = ?"
        r = cur.execute(sql, (t,)).fetchone()
        if r:
            iid = r[icol_id] if icol_id else "?"
            nm = (r[icol_name] if icol_name else "?") or ""
            ac = (r[icol_class] if icol_class else "?") or ""
            ticker_to_id[t] = iid
            print(f"{t:<10} {iid:>5} {nm[:28]:<30} {ac:<15}")
        else:
            print(f"{t:<10} {'-':>5} {'<absent>':<30} {'-':<15}")
    except sqlite3.OperationalError as e:
        print(f"{t:<10} ERR: {e}")
print()

# 4) target_universe lookup
print("=" * 70)
print("target_universe LOOKUP")
print("=" * 70)
tu_cols = cur.execute("PRAGMA table_info(target_universe)").fetchall()
tu_col_names = [c['name'] for c in tu_cols]
print(f"colonnes : {tu_col_names}")
print()

for t in ALL_T:
    try:
        r = cur.execute(
            "SELECT * FROM target_universe WHERE ticker = ?", (t,)
        ).fetchone()
        if r:
            print(f"  {t:<8} OK -> {dict(r)}")
        else:
            print(f"  {t:<8} ABSENT")
    except sqlite3.OperationalError as e:
        print(f"  {t:<8} ERR: {e}")
print()

# 5) Compter l'historique prices avec le bon schema
print("=" * 70)
print(f"HISTORIQUE prices (col ticker={ticker_col}, col date={date_col}, instr_id={instr_id_col})")
print("=" * 70)
print(f"{'TICKER':<10} {'N_BARS':>8} {'FIRST':<22} {'LAST':<22}")
print("-" * 70)

for t in ALL_T:
    n = 0
    fd = "-"
    ld = "-"
    try:
        if ticker_col:
            sql = f"SELECT COUNT(*) AS n, MIN({date_col}) AS fd, MAX({date_col}) AS ld FROM prices WHERE {ticker_col} = ?"
            r = cur.execute(sql, (t,)).fetchone()
            if r:
                n = r["n"] or 0
                fd = r["fd"] or "-"
                ld = r["ld"] or "-"
        elif instr_id_col and t in ticker_to_id:
            iid = ticker_to_id[t]
            sql = f"SELECT COUNT(*) AS n, MIN({date_col}) AS fd, MAX({date_col}) AS ld FROM prices WHERE {instr_id_col} = ?"
            r = cur.execute(sql, (iid,)).fetchone()
            if r:
                n = r["n"] or 0
                fd = r["fd"] or "-"
                ld = r["ld"] or "-"
        marker = " <- MIS" if t in MIS else ""
        print(f"{t:<10} {n:>8} {str(fd)[:20]:<22} {str(ld)[:20]:<22}{marker}")
    except sqlite3.OperationalError as e:
        print(f"{t:<10} ERR: {e}")
print()

# 6) Verifier crypto_context pour HYPE
print("=" * 70)
print("crypto_context pour HYPE (eventuel)")
print("=" * 70)
try:
    cc_cols = cur.execute("PRAGMA table_info(crypto_context)").fetchall()
    print("colonnes crypto_context :", [c['name'] for c in cc_cols])
    r = cur.execute("SELECT * FROM crypto_context WHERE ticker = ? OR symbol = ?", ("HYPE", "HYPE")).fetchone()
    if r:
        print(f"HYPE present : {dict(r)}")
    else:
        print("HYPE absent de crypto_context")
except sqlite3.OperationalError as e:
    print(f"  ERR: {e}")
print()

# 7) Resume
print("=" * 70)
print("DIAGNOSTIC")
print("=" * 70)
print(f"Tickers MIS : {MIS}")
print("Si N_BARS < ~60-90 pour un ticker MIS -> il faut fetch l'historique.")
print("Si N_BARS OK mais MIS -> blocage dans l'agent (correlations, vol, etc).")

con.close()
print()
print("Done.")
