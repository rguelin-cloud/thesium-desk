# -*- coding: utf-8 -*-
"""
NEXTONES - Jalon 4.1 - Patch UniverseExpansionAgent : source EQUITY (option B)
Marker idempotent: [EQUITY_EXPANSION_V1]

Objectif : injecter une 3eme source dans run_scan() :
  - Watchlist curatee S&P 500 + NASDAQ-100, ~55 tickers hors mega-caps
    deja en portefeuille (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA exclus).
  - asset_class = 'equity'
  - reutilise fetch_etf_history() (prix via table prices + fallback yfinance)
  - reutilise compute_features() et le scoring composite existant
  - cap variable applique automatiquement (CAP_HIGH/MID/LOW selon score)

Conformite aux regles utilisateur :
  - Script ASCII pur (pas d'accent, pas d'emoji)
  - Read utf-8-sig, write utf-8 sans BOM
  - Validation ast.parse + py_compile avant ecriture
  - Marker [EQUITY_EXPANSION_V1] pour idempotence
  - Pas de heredoc

Deploiement :
    py -3.13 nextones-universe-expansion-equity-v1.py
    (en runtime Windows, met a jour agents/universe_expansion_agent.py)

Apres deploiement :
    POST /api/universe/scan via UI ou run_scan() pour declencher un scan
    incluant les equity candidates.
"""
from __future__ import annotations

import ast
import py_compile
import shutil
import sys
from datetime import datetime
from pathlib import Path

MARKER = "[EQUITY_EXPANSION_V1]"

# Chemin runtime cote Windows (fichier a la racine du projet, pas dans agents/)
AGENT_PATH = Path(
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py"
)

# ---------------------------------------------------------------------------
# Watchlist curatee : ~55 tickers S&P 500 + NASDAQ-100
# Excluded (deja en portefeuille) : AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA
# Choix : leaders sectoriels + momentum candidates raisonnables
# ---------------------------------------------------------------------------
EQUITY_BLOCK = '''
# -------------------------------------------------------------------- [EQUITY_EXPANSION_V1] BEGIN
# Watchlist S&P 500 + NASDAQ-100 curatee, hors mega-caps deja en portefeuille
# (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA exclus). 55 tickers.
# Source : leaders sectoriels US, profil liquide, market cap > 50G$ majoritairement.
EQUITY_WATCHLIST_V1: list[dict[str, str]] = [
    # Technology / Semiconductors
    {"ticker": "AVGO", "name": "Broadcom Inc.",              "sector": "Technology"},
    {"ticker": "AMD",  "name": "Advanced Micro Devices",     "sector": "Technology"},
    {"ticker": "QCOM", "name": "Qualcomm Inc.",              "sector": "Technology"},
    {"ticker": "ORCL", "name": "Oracle Corporation",         "sector": "Technology"},
    {"ticker": "CRM",  "name": "Salesforce Inc.",            "sector": "Technology"},
    {"ticker": "ADBE", "name": "Adobe Inc.",                 "sector": "Technology"},
    {"ticker": "CSCO", "name": "Cisco Systems",              "sector": "Technology"},
    {"ticker": "TXN",  "name": "Texas Instruments",          "sector": "Technology"},
    {"ticker": "INTU", "name": "Intuit Inc.",                "sector": "Technology"},
    {"ticker": "NOW",  "name": "ServiceNow Inc.",            "sector": "Technology"},
    {"ticker": "PLTR", "name": "Palantir Technologies",      "sector": "Technology"},
    {"ticker": "ARM",  "name": "Arm Holdings",               "sector": "Technology"},
    # Communication Services / Media
    {"ticker": "NFLX", "name": "Netflix Inc.",               "sector": "Communication"},
    {"ticker": "DIS",  "name": "Walt Disney Company",        "sector": "Communication"},
    {"ticker": "TMUS", "name": "T-Mobile US",                "sector": "Communication"},
    {"ticker": "CMCSA","name": "Comcast Corporation",        "sector": "Communication"},
    # Consumer Discretionary
    {"ticker": "HD",   "name": "Home Depot",                 "sector": "ConsumerDiscretionary"},
    {"ticker": "MCD",  "name": "McDonald's Corporation",     "sector": "ConsumerDiscretionary"},
    {"ticker": "NKE",  "name": "Nike Inc.",                  "sector": "ConsumerDiscretionary"},
    {"ticker": "SBUX", "name": "Starbucks Corporation",      "sector": "ConsumerDiscretionary"},
    {"ticker": "BKNG", "name": "Booking Holdings",           "sector": "ConsumerDiscretionary"},
    {"ticker": "LOW",  "name": "Lowe's Companies",           "sector": "ConsumerDiscretionary"},
    # Consumer Staples
    {"ticker": "COST", "name": "Costco Wholesale",           "sector": "ConsumerStaples"},
    {"ticker": "WMT",  "name": "Walmart Inc.",               "sector": "ConsumerStaples"},
    {"ticker": "PG",   "name": "Procter & Gamble",           "sector": "ConsumerStaples"},
    {"ticker": "KO",   "name": "Coca-Cola Company",          "sector": "ConsumerStaples"},
    {"ticker": "PEP",  "name": "PepsiCo Inc.",               "sector": "ConsumerStaples"},
    # Financials
    {"ticker": "JPM",  "name": "JPMorgan Chase",             "sector": "Financials"},
    {"ticker": "V",    "name": "Visa Inc.",                  "sector": "Financials"},
    {"ticker": "MA",   "name": "Mastercard Inc.",            "sector": "Financials"},
    {"ticker": "BAC",  "name": "Bank of America",            "sector": "Financials"},
    {"ticker": "WFC",  "name": "Wells Fargo & Co.",          "sector": "Financials"},
    {"ticker": "GS",   "name": "Goldman Sachs Group",        "sector": "Financials"},
    {"ticker": "MS",   "name": "Morgan Stanley",             "sector": "Financials"},
    {"ticker": "AXP",  "name": "American Express",           "sector": "Financials"},
    {"ticker": "BRK-B","name": "Berkshire Hathaway B",       "sector": "Financials"},
    # Healthcare
    {"ticker": "LLY",  "name": "Eli Lilly and Company",      "sector": "Healthcare"},
    {"ticker": "UNH",  "name": "UnitedHealth Group",         "sector": "Healthcare"},
    {"ticker": "JNJ",  "name": "Johnson & Johnson",          "sector": "Healthcare"},
    {"ticker": "ABBV", "name": "AbbVie Inc.",                "sector": "Healthcare"},
    {"ticker": "MRK",  "name": "Merck & Co.",                "sector": "Healthcare"},
    {"ticker": "PFE",  "name": "Pfizer Inc.",                "sector": "Healthcare"},
    {"ticker": "TMO",  "name": "Thermo Fisher Scientific",   "sector": "Healthcare"},
    {"ticker": "ISRG", "name": "Intuitive Surgical",         "sector": "Healthcare"},
    # Industrials
    {"ticker": "CAT",  "name": "Caterpillar Inc.",           "sector": "Industrials"},
    {"ticker": "BA",   "name": "Boeing Company",             "sector": "Industrials"},
    {"ticker": "GE",   "name": "General Electric",           "sector": "Industrials"},
    {"ticker": "RTX",  "name": "RTX Corporation",            "sector": "Industrials"},
    {"ticker": "HON",  "name": "Honeywell International",    "sector": "Industrials"},
    {"ticker": "UNP",  "name": "Union Pacific Corporation",  "sector": "Industrials"},
    # Energy
    {"ticker": "XOM",  "name": "Exxon Mobil Corporation",    "sector": "Energy"},
    {"ticker": "CVX",  "name": "Chevron Corporation",        "sector": "Energy"},
    {"ticker": "COP",  "name": "ConocoPhillips",             "sector": "Energy"},
    # Materials / RealEstate / Utilities (representants)
    {"ticker": "LIN",  "name": "Linde plc",                  "sector": "Materials"},
    {"ticker": "PLD",  "name": "Prologis Inc.",              "sector": "RealEstate"},
    {"ticker": "NEE",  "name": "NextEra Energy",             "sector": "Utilities"},
    {"ticker": "SO",   "name": "Southern Company",           "sector": "Utilities"},
]
# -------------------------------------------------------------------- [EQUITY_EXPANSION_V1] END
'''.lstrip("\n")


# Injection dans run_scan() : bloc ajoute apres la boucle ETF SPDR
RUN_SCAN_INJECTION = '''
        # ---------------------------------------------------------------- [EQUITY_EXPANSION_V1] BEGIN
        # Equities : watchlist S&P 500 + NASDAQ-100 curatee
        equity_added = 0
        for eq in EQUITY_WATCHLIST_V1:
            if eq["ticker"].upper() in existing:
                continue
            candidates_meta.append({
                "id": None,
                "ticker": eq["ticker"],
                "name": eq["name"],
                "asset_class": "equity",
                "sector": eq["sector"],
                "current_price": None,
                "market_cap": None,
                "total_volume_24h": None,
            })
            equity_added += 1
        log.info("%s equity candidates injectes: %d", MARKER, equity_added)
        # ---------------------------------------------------------------- [EQUITY_EXPANSION_V1] END
'''


# ---------------------------------------------------------------------------
# Routine du patch (idempotent)
# ---------------------------------------------------------------------------
def main() -> int:
    if not AGENT_PATH.exists():
        print(f"[ERR] Fichier introuvable: {AGENT_PATH}", file=sys.stderr)
        return 2

    # Lire en utf-8-sig (tolerant BOM), ecrire en utf-8 sans BOM
    src = AGENT_PATH.read_text(encoding="utf-8-sig")

    if MARKER in src:
        print(f"[OK] Marker {MARKER} deja present, rien a faire (idempotent).")
        return 0

    # 1. Inserer le bloc EQUITY_WATCHLIST_V1 apres la liste ETF_SPDR_SECTORIELS
    anchor_block = "]\n\n# Cryptos"
    if anchor_block not in src:
        # Fallback : juste apres la fermeture de ETF_SPDR_SECTORIELS
        anchor_block = "]\n# Cryptos"
        if anchor_block not in src:
            print("[ERR] Ancre 'ETF_SPDR_SECTORIELS ... # Cryptos' non trouvee", file=sys.stderr)
            return 3

    new_src = src.replace(anchor_block, "]\n\n" + EQUITY_BLOCK + "\n# Cryptos", 1)

    # 2. Inserer l'injection dans run_scan() apres la boucle ETFs SPDR
    anchor_scan = "        log.info(\"Candidats post-filtre-univers : %d\", len(candidates_meta))"
    if anchor_scan not in new_src:
        print("[ERR] Ancre run_scan() non trouvee", file=sys.stderr)
        return 4

    new_src = new_src.replace(
        anchor_scan,
        RUN_SCAN_INJECTION + "\n" + anchor_scan,
        1,
    )

    # 3. Validation stricte : ast.parse + py_compile sur fichier temporaire
    try:
        ast.parse(new_src)
    except SyntaxError as exc:
        print(f"[ERR] ast.parse a echoue: {exc}", file=sys.stderr)
        return 5

    tmp_path = AGENT_PATH.with_suffix(".py.tmp")
    tmp_path.write_text(new_src, encoding="utf-8", newline="\n")
    try:
        py_compile.compile(str(tmp_path), doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[ERR] py_compile a echoue: {exc}", file=sys.stderr)
        tmp_path.unlink(missing_ok=True)
        return 6

    # 4. Backup + ecriture finale
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    backup = AGENT_PATH.with_suffix(f".py.bak.{ts}")
    shutil.copy2(AGENT_PATH, backup)

    AGENT_PATH.write_text(new_src, encoding="utf-8", newline="\n")
    tmp_path.unlink(missing_ok=True)

    print(f"[OK] Patch {MARKER} applique.")
    print(f"     Backup : {backup}")
    print(f"     Cible  : {AGENT_PATH}")
    print(f"     +{src.count(chr(10)) - new_src.count(chr(10)) and '?' or ''} "
          f"net lines added : {new_src.count(chr(10)) - src.count(chr(10))}")
    print("")
    print("Prochaine etape :")
    print("  1. Redemarrer l'API (kill uvicorn + py -3.13 -m uvicorn ...)")
    print("  2. Declencher un scan : POST /api/universe/scan via UI")
    print("  3. Verifier que des candidats asset_class='equity' apparaissent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
