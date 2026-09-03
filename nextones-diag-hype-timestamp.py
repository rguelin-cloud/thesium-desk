# -*- coding: utf-8 -*-
"""
Diag du Parse error HYPE-USD: 'timestamp'.

  1. Localise le code data_ingestion qui logue ce message
  2. Affiche le bloc de code (parser yfinance)
  3. Appelle yfinance directement sur HYPE-USD pour voir ce que retourne l'API
  4. Compare avec un ticker qui marche (BTC-USD) pour identifier la difference
  5. Verifie l'etat actuel de HYPE dans la table prices (dernieres lignes)
"""

import sys
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"


def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")


def main():
    # 1. Localiser le code qui logue "Parse error for"
    section("1. Recherche du code qui logue le Parse error")
    candidates = list(ROOT.glob("data_ingestion*.py")) + list(ROOT.glob("**/data_ingestion*.py"))
    candidates = [c for c in candidates if "__pycache__" not in str(c)]
    print(f"  Fichiers data_ingestion trouves: {len(candidates)}")
    for c in candidates:
        print(f"    {c.relative_to(ROOT)}")

    # Search the error string everywhere
    err_re = re.compile(r"Parse error for")
    py_files = [p for p in ROOT.rglob("*.py") if "__pycache__" not in str(p)]
    hits = []
    for p in py_files:
        try:
            txt = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        for i, ln in enumerate(txt.splitlines(), 1):
            if err_re.search(ln):
                hits.append((p, i, ln))
    print(f"  Occurrences 'Parse error for': {len(hits)}")
    for p, ln, txt in hits:
        print(f"    {p.relative_to(ROOT)}:{ln}  {txt.strip()[:120]}")

    # 2. Afficher le bloc de code autour
    section("2. Code autour du log")
    if hits:
        p, ln, _ = hits[0]
        lines = p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        start = max(0, ln - 30)
        end = min(len(lines), ln + 5)
        for i in range(start, end):
            marker = " <--" if i + 1 == ln else ""
            print(f"  {i+1:5d}: {lines[i]}{marker}")

    # 3. Verifier ce que retourne yfinance pour HYPE-USD vs BTC-USD
    section("3. yfinance HYPE-USD vs BTC-USD (test direct)")
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance non importe - skip")
    else:
        for tk in ("HYPE-USD", "BTC-USD"):
            print(f"\n  --- {tk} ---")
            try:
                t = yf.Ticker(tk)
                # Essai 1 : history
                hist = t.history(period="5d")
                print(f"  history shape: {hist.shape}, cols: {list(hist.columns)}")
                if not hist.empty:
                    print(f"  index name: {hist.index.name}, last date: {hist.index[-1]}")
                    print(f"  last row: Close={hist['Close'].iloc[-1]:.2f}")
                else:
                    print(f"  history VIDE !")
                # Essai 2 : info / fast_info
                try:
                    fi = t.fast_info
                    print(f"  fast_info dispo: last_price={getattr(fi, 'last_price', None)}")
                except Exception as e:
                    print(f"  fast_info erreur: {e}")
            except Exception as e:
                print(f"  ERREUR yfinance: {type(e).__name__}: {e}")

    # 4. Etat HYPE dans la DB
    section("4. HYPE dans table prices (DB)")
    if DB.exists():
        conn = sqlite3.connect(str(DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Trouve l'id HYPE
        inst = cur.execute("SELECT id, ticker FROM instruments WHERE ticker LIKE 'HYPE%'").fetchall()
        for r in inst:
            d = dict(r)
            print(f"  Instrument: id={d['id']} ticker={d['ticker']}")
            cnt = cur.execute("SELECT COUNT(*) FROM prices WHERE instrument_id=?", (d["id"],)).fetchone()[0]
            print(f"    prices count: {cnt}")
            last = cur.execute(
                """SELECT * FROM prices WHERE instrument_id=?
                   ORDER BY COALESCE(date, timestamp, id) DESC LIMIT 5""", (d["id"],)
            ).fetchall()
            cols = [c[1] for c in cur.execute("PRAGMA table_info(prices)").fetchall()]
            print(f"    prices cols: {cols}")
            for row in last:
                print(f"    {dict(row)}")
        conn.close()
    else:
        print(f"  DB introuvable {DB}")

    print("\n" + "=" * 70)
    print("  Diag termine - colle la sortie pour preparer le fix")
    print("=" * 70)


if __name__ == "__main__":
    sys.exit(main() or 0)
