# -*- coding: utf-8 -*-
"""
Diag pipeline crypto :
  1. data_crypto.py : signature + callers
  2. data_ingestion.run_ingestion : code complet (boucle sur instruments)
  3. Pour chaque crypto (BTC, ETH, LINK, SOL, HYPE, ZEC) : derniere date + amplitude OHLC
     (pour identifier qui passe par Yahoo et qui par CG)
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"


def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")


def main():
    # 1. data_crypto.py
    section("1. data_crypto.py")
    dc = ROOT / "data_crypto.py"
    if dc.exists():
        txt = dc.read_text(encoding="utf-8-sig", errors="replace")
        lines = txt.splitlines()
        print(f"  Total lignes: {len(lines)}")
        # Signatures (def ...)
        defs = [(i+1, ln) for i, ln in enumerate(lines) if ln.strip().startswith("def ")]
        print(f"  Fonctions:")
        for i, ln in defs:
            print(f"    L{i}: {ln.strip()}")
        # Mapping ticker -> coingecko id ?
        cg_map_pat = re.compile(r"(coin_gecko_ids?|CG_IDS?|CRYPTO_TICKERS?|coingecko_map|CG_MAP)")
        for i, ln in enumerate(lines, 1):
            if cg_map_pat.search(ln):
                print(f"    L{i}: {ln.strip()[:140]}")
        # Recherche entries pour HYPE
        for i, ln in enumerate(lines, 1):
            if "hype" in ln.lower() or "hyperliquid" in ln.lower():
                print(f"    L{i} [HYPE]: {ln.strip()[:140]}")
    else:
        print(f"  FAIL: {dc} introuvable")

    # 2. data_ingestion.run_ingestion (lignes 72+)
    section("2. data_ingestion.run_ingestion (boucle complete)")
    di = ROOT / "data_ingestion.py"
    if di.exists():
        lines = di.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        # Affiche de la ligne 72 a la fin
        for i in range(72, min(len(lines), 130)):
            print(f"  {i+1:4d}: {lines[i]}")

    # 3. Callers data_crypto
    section("3. Qui appelle data_crypto ?")
    pat = re.compile(r"(from\s+data_crypto|import\s+data_crypto|data_crypto\.)")
    for p in ROOT.rglob("*.py"):
        if "__pycache__" in str(p) or "_backup" in str(p).lower():
            continue
        try:
            txt = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        matches = [(i, ln.strip()) for i, ln in enumerate(txt.splitlines(), 1) if pat.search(ln)]
        if matches:
            print(f"\n  {p.relative_to(ROOT)}:")
            for i, ln in matches[:6]:
                print(f"    L{i}: {ln[:140]}")

    # 4. Etat actuel de chaque crypto en DB
    section("4. Etat des 6 crypto (derniere date + amplitude OHLC)")
    if DB.exists():
        conn = sqlite3.connect(str(DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cryptos = cur.execute(
            "SELECT id, ticker FROM instruments WHERE asset_class='crypto' ORDER BY id"
        ).fetchall()
        print(f"  {'TICKER':<6} {'COUNT':>6} {'DERNIERE':<12} {'OHLC_DERNIER':<40} {'IDENTITE_OHLC':<5}")
        print(f"  {'-'*6} {'-'*6} {'-'*12} {'-'*40} {'-'*5}")
        for r in cryptos:
            inst_id = r["id"]
            tk = r["ticker"]
            cnt = cur.execute("SELECT COUNT(*) FROM prices WHERE instrument_id=?", (inst_id,)).fetchone()[0]
            last = cur.execute(
                "SELECT date, open, high, low, close, volume FROM prices "
                "WHERE instrument_id=? ORDER BY date DESC LIMIT 1", (inst_id,)
            ).fetchone()
            if last:
                d = dict(last)
                ohlc = f"O={d['open']:.2f} H={d['high']:.2f} L={d['low']:.2f} C={d['close']:.2f}"
                same = d['open'] == d['high'] == d['low'] == d['close']
                # Si O=H=L=C -> probablement CoinGecko (daily close only)
                # Si O<>H/L/C -> Yahoo (vrai OHLC)
                identity = "YES" if same else "no"
                source = "CG" if same else "YF"
                print(f"  {tk:<6} {cnt:>6} {d['date']:<12} {ohlc:<40} {identity} ({source})")
            else:
                print(f"  {tk:<6} {cnt:>6} {'(aucun)':<12}")
        conn.close()

    print("\n" + "=" * 70)
    print("  Diag pipeline crypto termine")
    print("=" * 70)


if __name__ == "__main__":
    sys.exit(main() or 0)
