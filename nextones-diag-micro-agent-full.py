# nextones-diag-micro-agent-full.py
# Affiche le code complet de MicrostructureAgent (L375-510) + cherche
# pourquoi XLE/XLK ne generent pas de theses malgre le SELECT sans filtre.
# ASCII pur.

import os
import sqlite3
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
AGENTS = os.path.join(ROOT, "agents.py")
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

# 1) Code de MicrostructureAgent complet
print("=" * 70)
print("CODE MicrostructureAgent (L375 -> L510)")
print("=" * 70)
with open(AGENTS, "r", encoding="utf-8-sig") as f:
    lines = f.read().splitlines()
for i in range(374, min(510, len(lines))):
    print(f"L{i+1:>4}: {lines[i]}")
print()

# 2) Definition de _get_prices et MIN_BARS
print("=" * 70)
print("FONCTION _get_prices")
print("=" * 70)
for i, l in enumerate(lines, 1):
    if "_get_prices" in l and ("def " in l or "lambda" in l):
        # Imprime 15 lignes
        for j in range(i - 1, min(i + 25, len(lines))):
            print(f"L{j+1:>4}: {lines[j]}")
        print()
        break

# 3) Constante MIN_BARS / minimum lookback / continue
print("=" * 70)
print("Skips / continue / min length dans MicrostructureAgent (L380-490)")
print("=" * 70)
for i in range(379, 490):
    if i < len(lines):
        l = lines[i]
        if re.search(r"\b(continue|skip|return|if.*<|MIN_|if not |if len\()", l):
            print(f"L{i+1:>4}: {l.strip()}")
print()

# 4) Verifier nombre de barres XLE/XLK/XLI/XLB en DB
print("=" * 70)
print("Verification N_BARS XLE/XLK/XLI/XLB/MSFT")
print("=" * 70)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
for tk in ["XLE", "XLK", "XLI", "XLB", "MSFT", "ZEC", "HYPE"]:
    r_i = cur.execute("SELECT id FROM instruments WHERE ticker = ?", (tk,)).fetchone()
    if not r_i:
        print(f"  {tk:<8} pas dans instruments")
        continue
    iid = r_i["id"]
    r = cur.execute(
        "SELECT COUNT(*) AS n, MIN(date) AS fd, MAX(date) AS ld "
        "FROM prices WHERE instrument_id = ?", (iid,)
    ).fetchone()
    print(f"  {tk:<8} iid={iid} n={r['n']} {r['fd']} -> {r['ld']}")
print()

# 5) Verifier les theses de XLE/XLK depuis 1 heure (cycle de 16:02)
print("=" * 70)
print("Theses generes par MicrostructureAgent depuis 1h pour XLE/XLK/XLI/XLB/QQQ/SPY")
print("=" * 70)
for tk in ["XLE", "XLK", "XLI", "XLB", "QQQ", "SPY"]:
    r_i = cur.execute("SELECT id FROM instruments WHERE ticker = ?", (tk,)).fetchone()
    if not r_i:
        print(f"  {tk:<8} pas dans instruments"); continue
    iid = r_i["id"]
    r = cur.execute(
        "SELECT COUNT(*) AS n FROM theses "
        "WHERE instrument_id = ? AND agent_type = 'MicrostructureAgent' "
        "AND created_at >= datetime('now', '-2 hours')",
        (iid,)
    ).fetchone()
    print(f"  {tk:<8} {r['n']} theses Micro depuis 2h")
print()

# 6) Liste complete des is_active = 1 et leur asset_class
print("=" * 70)
print("target_universe is_active=1 et leurs barres prices")
print("=" * 70)
rows = cur.execute(
    "SELECT tu.ticker, tu.asset_class, i.id AS iid, "
    "(SELECT COUNT(*) FROM prices p WHERE p.instrument_id = i.id) AS n_bars "
    "FROM target_universe tu LEFT JOIN instruments i ON i.ticker = tu.ticker "
    "WHERE tu.is_active = 1 ORDER BY tu.asset_class, tu.ticker"
).fetchall()
for r in rows:
    print(f"  {r['ticker']:<8} class={r['asset_class']:<10} iid={r['iid']} n_bars={r['n_bars']}")
print()

con.close()
print("Done.")
