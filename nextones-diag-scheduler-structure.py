# -*- coding: utf-8 -*-
"""
Diag du scheduler actuel pour preparer le nouveau job CoinGecko refresh.

  1. Trouve le fichier scheduler.py et son APScheduler config
  2. Affiche tous les jobs enregistres (prices, macro, sentiment, geo, universe)
  3. Affiche la signature de data_crypto.fetch_crypto_combined()
  4. Verifie comment data_crypto stocke les prix (pour confirmer qu'il ecrit en DB)
"""

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")


def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")


def main():
    # 1. Trouver le fichier scheduler
    section("1. Fichiers scheduler")
    candidates = []
    for p in ROOT.glob("*.py"):
        if "__pycache__" in str(p):
            continue
        try:
            txt = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        if "scheduler" in p.name.lower() or "APScheduler" in txt or "BackgroundScheduler" in txt:
            candidates.append(p)
    for c in candidates:
        print(f"  {c.relative_to(ROOT)}")

    # 2. Affiche le scheduler principal (chercher scheduler.py)
    sched = ROOT / "scheduler.py"
    if sched.exists():
        section("2. scheduler.py (contenu complet)")
        lines = sched.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        print(f"  Total lignes: {len(lines)}")
        for i, ln in enumerate(lines, 1):
            print(f"  {i:4d}: {ln}")
    else:
        section("2. scheduler.py introuvable - chercher dans api_server.py")
        api = ROOT / "api_server.py"
        if api.exists():
            lines = api.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            # Trouve les blocs scheduler
            pat = re.compile(r"(scheduler|add_job|cron|interval|@app\.on_event)", re.IGNORECASE)
            for i, ln in enumerate(lines, 1):
                if pat.search(ln) and ("scheduler" in ln.lower() or "add_job" in ln.lower()):
                    print(f"  L{i}: {ln.rstrip()[:140]}")

    # 3. Signature data_crypto.fetch_crypto_combined + qu'est-ce que ca renvoie
    section("3. data_crypto.fetch_crypto_combined / fetch_crypto_prices")
    dc = ROOT / "data_crypto.py"
    if dc.exists():
        lines = dc.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        # Affiche la fonction fetch_crypto_prices (L59) et fetch_crypto_combined (L143)
        for start_ln in (59, 143):
            print(f"\n  --- Fonction L{start_ln} ---")
            end_ln = min(len(lines), start_ln + 35)
            for i in range(start_ln - 1, end_ln):
                print(f"  {i+1:4d}: {lines[i]}")

    # 4. CG_MAP
    section("4. CG_MAP (mapping ticker -> coingecko id)")
    if dc.exists():
        lines = dc.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        for i, ln in enumerate(lines, 1):
            if 22 <= i <= 60 and ("CG_MAP" in ln or "{" in ln or "}" in ln or ":" in ln):
                print(f"  {i:4d}: {ln}")

    # 5. data_crypto ecrit-il en DB? Cherche INSERT/UPDATE prices
    section("5. data_crypto ecrit-il dans la table prices ?")
    if dc.exists():
        txt = dc.read_text(encoding="utf-8-sig", errors="replace")
        if "INSERT" in txt.upper() or "UPDATE prices" in txt or "REPLACE INTO" in txt.upper():
            print("  OUI - INSERT/UPDATE detecte")
            for i, ln in enumerate(txt.splitlines(), 1):
                if re.search(r"(INSERT|UPDATE\s+prices|REPLACE\s+INTO)", ln, re.IGNORECASE):
                    print(f"    L{i}: {ln.strip()[:140]}")
        else:
            print("  NON - data_crypto retourne juste de la data sans persistance")
            print("  -> il faudra wrapper l'appel avec upsert_prices() pour persister")


if __name__ == "__main__":
    sys.exit(main() or 0)
