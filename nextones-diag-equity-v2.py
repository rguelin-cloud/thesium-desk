# -*- coding: utf-8 -*-
# [DIAG_EQUITY_V2]
# Diag complet sans import du module (qui plante a cause des dataclass)
# - Lit le fichier source en texte brut
# - Verifie marker, watchlist, boucle d'injection
# - Inspecte le endpoint /api/universe/scan dans api_server_with_static.py
# - Verifie la presence du module dans sys.modules via un test indirect
import os
import re
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
AGENT = os.path.join(ROOT, "universe_expansion_agent.py")
API = os.path.join(ROOT, "api_server_with_static.py")


def header(t):
    print()
    print("=" * 72)
    print("  " + t)
    print("=" * 72)


def step1_source():
    header("1. Source universe_expansion_agent.py")
    if not os.path.isfile(AGENT):
        print("  [KO] fichier absent : " + AGENT)
        return None
    with open(AGENT, "r", encoding="utf-8-sig") as f:
        src = f.read()
    print("  taille = {} chars, {} lignes".format(len(src), src.count("\n") + 1))
    begin = src.count("# [EQUITY_EXPANSION_V1] BEGIN")
    end = src.count("# [EQUITY_EXPANSION_V1] END")
    print("  marker BEGIN x{}, END x{}".format(begin, end))
    has_wl = "EQUITY_WATCHLIST_V1" in src
    has_loop = re.search(r"for\s+eq\s+in\s+EQUITY_WATCHLIST_V1", src) is not None
    print("  EQUITY_WATCHLIST_V1 declare : {}".format(has_wl))
    print("  boucle for eq in EQUITY_WATCHLIST_V1 : {}".format(has_loop))
    # Extraire la boucle d'injection pour voir le contexte
    m = re.search(
        r"# \[EQUITY_EXPANSION_V1\] BEGIN.*?# \[EQUITY_EXPANSION_V1\] END",
        src,
        flags=re.DOTALL,
    )
    if m:
        bloc = m.group(0)
        nlines = bloc.count("\n") + 1
        print("  bloc EQUITY_EXPANSION_V1 = {} lignes".format(nlines))
        # Cherche les indices d'injection
        if "universe_candidates" in bloc or "INSERT INTO" in bloc:
            print("  [OK] bloc contient un INSERT vers universe_candidates")
        else:
            print("  [!!] bloc NE CONTIENT PAS d'INSERT visible")
        # Print premieres et dernieres lignes du bloc
        print("  --- 20 premieres lignes du bloc ---")
        for i, ln in enumerate(bloc.split("\n")[:20], 1):
            print("    {:3d}: {}".format(i, ln[:120]))
        print("  --- 10 dernieres lignes du bloc ---")
        last = bloc.split("\n")[-10:]
        for i, ln in enumerate(last, 1):
            print("    {}".format(ln[:120]))
    return src


def step2_api_scan_endpoint():
    header("2. Endpoint /api/universe/scan dans api_server_with_static.py")
    if not os.path.isfile(API):
        print("  [KO] fichier absent : " + API)
        return
    with open(API, "r", encoding="utf-8-sig") as f:
        src = f.read()
    # Cherche le router de /api/universe/scan
    pat = re.compile(
        r"(@app\.(?:post|get).*?[\"']/api/universe/scan[\"'].*?)(?=@app\.|^def |^async def |\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(src)
    if not m:
        # Cherche plus simplement
        idx = src.find("/api/universe/scan")
        if idx < 0:
            print("  [KO] endpoint /api/universe/scan introuvable")
            return
        # Print 40 lignes autour
        start = src.rfind("\n", 0, idx)
        block = src[start : idx + 1500]
        print("  Contexte autour de l'endpoint :")
        for i, ln in enumerate(block.split("\n")[:40], 1):
            print("    {:3d}: {}".format(i, ln[:130]))
        return
    block = m.group(1)
    print("  Endpoint trouve, {} lignes :".format(block.count("\n") + 1))
    for i, ln in enumerate(block.split("\n")[:40], 1):
        print("    {:3d}: {}".format(i, ln[:130]))


def step3_instruments_overlap():
    header("3. Tickers EQUITY_WATCHLIST deja dans instruments")
    import sqlite3

    wl = [
        "AVGO","AMD","QCOM","ORCL","CRM","ADBE","CSCO","TXN","INTU","NOW","PLTR","ARM",
        "NFLX","DIS","TMUS","CMCSA","HD","MCD","NKE","SBUX","BKNG","LOW","COST","WMT",
        "PG","KO","PEP","JPM","V","MA","BAC","WFC","GS","MS","AXP","BRK-B","LLY","UNH",
        "JNJ","ABBV","MRK","PFE","TMO","ISRG","CAT","BA","GE","RTX","HON","UNP","XOM",
        "CVX","COP","LIN","PLD","NEE","SO",
    ]
    con = sqlite3.connect(os.path.join(ROOT, "thesium.db"))
    cur = con.cursor()
    placeholders = ",".join("?" * len(wl))
    rows = cur.execute(
        "SELECT ticker FROM instruments WHERE ticker IN ({})".format(placeholders),
        wl,
    ).fetchall()
    existing = sorted([r[0] for r in rows])
    print("  {} / {} tickers de la watchlist sont dans instruments :".format(len(existing), len(wl)))
    print("  " + ", ".join(existing) if existing else "  (aucun)")
    missing = sorted(set(wl) - set(existing))
    print("  {} tickers NOUVEAUX (candidats potentiels) :".format(len(missing)))
    # Affiche par groupe de 10
    for i in range(0, len(missing), 10):
        print("    " + ", ".join(missing[i : i + 10]))
    con.close()


def step4_pycache_state():
    header("4. Etat __pycache__")
    pcache = os.path.join(ROOT, "__pycache__")
    if not os.path.isdir(pcache):
        print("  (pas de __pycache__ a la racine)")
        return
    targets = ["universe_expansion_agent", "api_server_with_static"]
    for t in targets:
        for f in os.listdir(pcache):
            if f.startswith(t + ".") and f.endswith(".pyc"):
                full = os.path.join(pcache, f)
                mt = os.path.getmtime(full)
                import datetime
                print(
                    "  {} mtime={}".format(
                        f, datetime.datetime.fromtimestamp(mt).isoformat()
                    )
                )
    # mtime du source
    import datetime
    if os.path.isfile(AGENT):
        mt = os.path.getmtime(AGENT)
        print(
            "  source universe_expansion_agent.py mtime={}".format(
                datetime.datetime.fromtimestamp(mt).isoformat()
            )
        )


def main():
    print("NEXTONES diag equity v2")
    print("Python:", sys.version.split()[0])
    step1_source()
    step2_api_scan_endpoint()
    step3_instruments_overlap()
    step4_pycache_state()
    print()
    print("=" * 72)
    print("  Lance ce diag puis colle la sortie complete")
    print("=" * 72)


if __name__ == "__main__":
    main()
