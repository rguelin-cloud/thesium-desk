# -*- coding: utf-8 -*-
"""
[DIAG_PRICES_PORTFOLIO_SCHEMA_V1]
Verifie le schema DB de :
- prices
- instruments
- portfolio (table actuelle des positions)
- portfolio_targets
Pour ecrire la bonne requete _existing_portfolio_returns.
Affiche aussi un echantillon de chaque table + la fonction fautive ligne ~109.
"""
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")

def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Liste toutes les tables
    section("1) Tables existantes")
    for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        print(f"  - {row[0]}")

    # Schema des tables qui nous interessent
    for tbl in ['prices', 'instruments', 'portfolio', 'portfolio_targets',
                'portfolio_history', 'positions', 'orders']:
        section(f"2) Schema '{tbl}'")
        try:
            for r in cur.execute(f"PRAGMA table_info({tbl})"):
                cid, name, typ, notnull, dflt, pk = r
                print(f"  {cid:2d}  {name:20s}  {typ:15s}  pk={pk}")
            # 3 lignes
            print("  -- echantillon --")
            for row in cur.execute(f"SELECT * FROM {tbl} LIMIT 3"):
                print(f"  {row}")
        except sqlite3.OperationalError as e:
            print(f"  [TABLE ABSENTE] {e}")

    # Fonction fautive : lignes 90..140 de universe_expansion_agent.py
    section("3) Fonction _existing_portfolio_returns (lignes 80..150)")
    txt = AGENT.read_text(encoding='utf-8-sig', errors='replace')
    lines = txt.splitlines()
    for i in range(80, min(155, len(lines))):
        marker = " >>>" if i == 109 else "    "
        print(f"{marker} L{i:4d}: {lines[i-1]}")

    con.close()

if __name__ == "__main__":
    main()
