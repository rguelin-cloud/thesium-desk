# [DIAG_GEO_CHARGE_V1]
# Diagnostic : pourquoi le panel RISQUE GEOPOLITIQUE affiche "CHARGEMENT..."
#
# Verifie 3 niveaux :
#   1) DB    : pplx_geo_context contient-il des lignes recentes ?
#   2) Cache : pplx_cache contient-il l'entree geo_context valide ?
#   3) API   : /api/pplx/geo renvoie-t-il available=True ?
#
# Usage : py -3.13 diag_geo_charge_pas.py

import sqlite3
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
API = "http://localhost:8000/api/pplx/geo"


def section(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def diag_db():
    section("[1/3] DB : pplx_geo_context")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pplx_geo_context'"
    ).fetchone()
    if not row:
        print("  TABLE ABSENTE -> agent jamais execute avec succes")
        con.close()
        return
    n = cur.execute("SELECT COUNT(*) FROM pplx_geo_context").fetchone()[0]
    print(f"  Nombre de lignes : {n}")
    if n == 0:
        print("  TABLE VIDE -> aucun snapshot dispo cote DB")
        con.close()
        return
    rows = cur.execute(
        "SELECT risk_id, title, severity, generated_at, model, global_score, regime "
        "FROM pplx_geo_context ORDER BY severity DESC"
    ).fetchall()
    now = int(time.time())
    for i, r in enumerate(rows, 1):
        try:
            gen = int(r["generated_at"]) if r["generated_at"] else 0
        except Exception:
            gen = 0
        age_h = (now - gen) / 3600.0 if gen else -1
        print(f"  R{i} sev={r['severity']:>3} score={r['global_score']} regime={r['regime']:<10} "
              f"age={age_h:>5.1f}h model={r['model']} | {r['title'][:50]}")
    con.close()


def diag_cache():
    section("[2/3] Cache pplx_cache : geo_context")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT key, ts, length(data) AS sz FROM pplx_cache WHERE key LIKE 'pplx_geo_context_%' ORDER BY ts DESC LIMIT 5"
    ).fetchall()
    if not rows:
        print("  Aucune entree cache geo_context")
    else:
        now = int(time.time())
        for k, ts, sz in rows:
            age_s = now - ts
            print(f"  key={k[:50]:50} age={age_s/3600:5.1f}h size={sz}B")
    con.close()


def diag_api():
    section("[3/3] API /api/pplx/geo (live)")
    try:
        req = urllib.request.Request(API)
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        print(f"  HTTP 200 OK, {len(body)} bytes")
        print(f"  available = {data.get('available')}")
        if data.get("available") is False:
            print(f"  reason    = {data.get('reason')}")
            print(f"  error     = {data.get('error')}")
        else:
            h = data.get("header") or {}
            print(f"  header.global_score = {h.get('global_score')}")
            print(f"  header.regime       = {h.get('regime')}")
            print(f"  header.model        = {h.get('model')}")
            print(f"  header.generated_at = {h.get('generated_at')}")
            print(f"  risks               = {len(data.get('risks') or [])}")
            print(f"  book_exposure       = {len(data.get('book_exposure') or [])}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP ERROR {e.code} : {e.reason}")
    except Exception as e:
        print(f"  ERREUR : {type(e).__name__} : {e}")


if __name__ == "__main__":
    diag_db()
    diag_cache()
    diag_api()
    print("\n[FIN]")
