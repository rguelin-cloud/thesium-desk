# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-SEED-UNIVERSE-V1]
# Seed la table broker_universe_activtrades avec les ~245 symboles
# observes dans le terminal MT5 ActivTrades (captures du 30/05/2026).
#
# Etape 1 : INSERT OR REPLACE des symboles statiques (constantes ci-dessous).
# Etape 2 (optionnelle, --enrich) : appel MetaAPI getSymbolSpecifications
#         pour enrichir contract_size / lot_step / tick_size / tick_value /
#         min_lots dans instrument_broker_mapping pour les symboles deja
#         mappes.
#
# Usage:
#   py -3.13 nextones-broker-seed-universe.py
#   py -3.13 nextones-broker-seed-universe.py --enrich
#
# Pre-requis: nextones-broker-mapping-schema.py a deja tourne.

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "THESIUM_DB",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db",
)


# ----------------------------------------------------------------------
# Univers ActivTrades observe (captures 30/05/2026, 12 images)
# Tuple: (broker_symbol, description, asset_class, underlying_ticker,
#         is_cfd, quote_ccy)
# underlying_ticker = symbole "standard" Thesium quand pertinent, sinon None.
# ----------------------------------------------------------------------

CRYPTOS = [
    ("BTCUSD", "Bitcoin vs US Dollar", "crypto", "BTC", 1, "USD"),
    ("ETHUSD", "Ethereum vs US Dollar", "crypto", "ETH", 1, "USD"),
    ("SOLUSD", "Solana vs US Dollar", "crypto", "SOL", 1, "USD"),
    ("LTCUSD", "Litecoin vs US Dollar", "crypto", "LTC", 1, "USD"),
    ("ADAUSD", "Cardano vs US Dollar", "crypto", "ADA", 1, "USD"),
    ("XRPUSD", "Ripple vs US Dollar", "crypto", "XRP", 1, "USD"),
    ("AVAXUSD", "Avalanche vs US Dollar", "crypto", "AVAX", 1, "USD"),
    ("BCHUSD", "Bitcoin Cash vs US Dollar", "crypto", "BCH", 1, "USD"),
    ("EOSUSD", "EOS vs US Dollar", "crypto", "EOS", 1, "USD"),
    ("XLMUSD", "Stellar vs US Dollar", "crypto", "XLM", 1, "USD"),
    ("DOTUSD", "Polkadot vs US Dollar", "crypto", "DOT", 1, "USD"),
    ("LINKUSD", "Chainlink vs US Dollar", "crypto", "LINK", 1, "USD"),
    ("NEOUSD", "Neo vs US Dollar", "crypto", "NEO", 1, "USD"),
    ("DOGEUSD", "Dogecoin vs US Dollar", "crypto", "DOGE", 1, "USD"),
    ("UNIUSD", "Uniswap vs US Dollar", "crypto", "UNI", 1, "USD"),
]

# US Stocks CFD format TICKER.US (echantillon non exhaustif issu des images
# 2..5 + AMD confirme separement). Description courte = nom societe.
US_STOCKS = [
    ("AAPL.US", "Apple Inc", "equity_us", "AAPL", 1, "USD"),
    ("ABBV.US", "AbbVie Inc", "equity_us", "ABBV", 1, "USD"),
    ("ABT.US", "Abbott Laboratories", "equity_us", "ABT", 1, "USD"),
    ("ACN.US", "Accenture", "equity_us", "ACN", 1, "USD"),
    ("ADBE.US", "Adobe Inc", "equity_us", "ADBE", 1, "USD"),
    ("ADI.US", "Analog Devices", "equity_us", "ADI", 1, "USD"),
    ("ADP.US", "ADP Inc", "equity_us", "ADP", 1, "USD"),
    ("AEP.US", "American Electric Power", "equity_us", "AEP", 1, "USD"),
    ("AIG.US", "AIG", "equity_us", "AIG", 1, "USD"),
    ("AMAT.US", "Applied Materials", "equity_us", "AMAT", 1, "USD"),
    ("AMD.US", "Advanced Micro Devices Inc", "equity_us", "AMD", 1, "USD"),
    ("AMGN.US", "Amgen", "equity_us", "AMGN", 1, "USD"),
    ("AMT.US", "American Tower", "equity_us", "AMT", 1, "USD"),
    ("AMZN.US", "Amazon", "equity_us", "AMZN", 1, "USD"),
    ("AVGO.US", "Broadcom", "equity_us", "AVGO", 1, "USD"),
    ("AXP.US", "American Express", "equity_us", "AXP", 1, "USD"),
    ("AZO.US", "AutoZone", "equity_us", "AZO", 1, "USD"),
    ("BA.US", "Boeing", "equity_us", "BA", 1, "USD"),
    ("BAC.US", "Bank of America", "equity_us", "BAC", 1, "USD"),
    ("BB.US", "BlackBerry", "equity_us", "BB", 1, "USD"),
    ("BBY.US", "Best Buy", "equity_us", "BBY", 1, "USD"),
    ("BDX.US", "Becton Dickinson", "equity_us", "BDX", 1, "USD"),
    ("BFB.US", "Brown-Forman", "equity_us", "BFB", 1, "USD"),
    ("BIDU.US", "Baidu", "equity_us", "BIDU", 1, "USD"),
    ("BIIB.US", "Biogen", "equity_us", "BIIB", 1, "USD"),
    ("BKNG.US", "Booking Holdings", "equity_us", "BKNG", 1, "USD"),
    ("BLK.US", "BlackRock", "equity_us", "BLK", 1, "USD"),
    ("BMY.US", "Bristol-Myers Squibb", "equity_us", "BMY", 1, "USD"),
    ("BRKB.US", "Berkshire Hathaway B", "equity_us", "BRKB", 1, "USD"),
    ("BSX.US", "Boston Scientific", "equity_us", "BSX", 1, "USD"),
    ("BURL.US", "Burlington Stores", "equity_us", "BURL", 1, "USD"),
    ("BX.US", "Blackstone", "equity_us", "BX", 1, "USD"),
    ("BYD.US", "Boyd Gaming", "equity_us", "BYD", 1, "USD"),
    ("C.US", "Citigroup", "equity_us", "C", 1, "USD"),
    ("CAT.US", "Caterpillar", "equity_us", "CAT", 1, "USD"),
    ("CB.US", "Chubb", "equity_us", "CB", 1, "USD"),
    ("CCI.US", "Crown Castle", "equity_us", "CCI", 1, "USD"),
    ("CHD.US", "Church & Dwight", "equity_us", "CHD", 1, "USD"),
    ("CLX.US", "Clorox", "equity_us", "CLX", 1, "USD"),
    ("CM.US", "Canadian Imperial Bank of Commerce", "equity_us", "CM", 1, "USD"),
    ("CMCSA.US", "Comcast", "equity_us", "CMCSA", 1, "USD"),
    ("CME.US", "CME Group", "equity_us", "CME", 1, "USD"),
    ("CMG.US", "Chipotle", "equity_us", "CMG", 1, "USD"),
    ("CNC.US", "Centene", "equity_us", "CNC", 1, "USD"),
    ("COP.US", "ConocoPhillips", "equity_us", "COP", 1, "USD"),
    ("COST.US", "Costco", "equity_us", "COST", 1, "USD"),
    ("CRM.US", "Salesforce", "equity_us", "CRM", 1, "USD"),
    ("CSCO.US", "Cisco Systems", "equity_us", "CSCO", 1, "USD"),
    ("CVS.US", "CVS Health", "equity_us", "CVS", 1, "USD"),
    ("CVX.US", "Chevron", "equity_us", "CVX", 1, "USD"),
    ("D.US", "Dominion Energy", "equity_us", "D", 1, "USD"),
    ("DAL.US", "Delta Air Lines", "equity_us", "DAL", 1, "USD"),
    ("DBX.US", "Dropbox", "equity_us", "DBX", 1, "USD"),
    ("DD.US", "DuPont", "equity_us", "DD", 1, "USD"),
    ("DE.US", "Deere", "equity_us", "DE", 1, "USD"),
    ("DELL.US", "Dell Technologies", "equity_us", "DELL", 1, "USD"),
    ("DG.US", "Dollar General", "equity_us", "DG", 1, "USD"),
    ("DHR.US", "Danaher", "equity_us", "DHR", 1, "USD"),
    # Suite (DHR -> LUV / LUV -> T / etc.) - tickers observes images 3..5
    ("MSFT.US", "Microsoft", "equity_us", "MSFT", 1, "USD"),
    ("MA.US", "Mastercard", "equity_us", "MA", 1, "USD"),
    ("META.US", "Meta Platforms", "equity_us", "META", 1, "USD"),
    ("MRK.US", "Merck", "equity_us", "MRK", 1, "USD"),
    ("NFLX.US", "Netflix", "equity_us", "NFLX", 1, "USD"),
    ("NKE.US", "Nike", "equity_us", "NKE", 1, "USD"),
    ("PFE.US", "Pfizer", "equity_us", "PFE", 1, "USD"),
    ("PLD.US", "Prologis", "equity_us", "PLD", 1, "USD"),
    ("PG.US", "Procter & Gamble", "equity_us", "PG", 1, "USD"),
    ("PYPL.US", "PayPal", "equity_us", "PYPL", 1, "USD"),
    ("QCOM.US", "Qualcomm", "equity_us", "QCOM", 1, "USD"),
    ("TXN.US", "Texas Instruments", "equity_us", "TXN", 1, "USD"),
    ("UNH.US", "UnitedHealth Group", "equity_us", "UNH", 1, "USD"),
    ("V.US", "Visa", "equity_us", "V", 1, "USD"),
    ("WMT.US", "Walmart", "equity_us", "WMT", 1, "USD"),
    ("XOM.US", "Exxon Mobil", "equity_us", "XOM", 1, "USD"),
    ("ZTS.US", "Zoetis", "equity_us", "ZTS", 1, "USD"),
    ("HPE.US", "Hewlett Packard Enterprise", "equity_us", "HPE", 1, "USD"),
    ("XYZ.US", "Block Inc", "equity_us", "XYZ", 1, "USD"),
    ("PSKY.US", "Paramount Skydance", "equity_us", "PSKY", 1, "USD"),
    ("CRH.US", "CRH Plc", "equity_us", "CRH", 1, "USD"),
    ("BNY.US", "Bank of New York Mellon", "equity_us", "BNY", 1, "USD"),
    ("MSCI.US", "MSCI Inc", "equity_us", "MSCI", 1, "USD"),
]

ETFS_US = [
    ("XLE.US", "SPDR Energy Select Sector ETF", "etf_us", "XLE", 1, "USD"),
    ("XLF.US", "SPDR Financial Select Sector ETF", "etf_us", "XLF", 1, "USD"),
    ("XLI.US", "SPDR Industrial Select Sector ETF", "etf_us", "XLI", 1, "USD"),
    ("XLK.US", "SPDR Technology Select Sector ETF", "etf_us", "XLK", 1, "USD"),
    ("XLP.US", "SPDR Consumer Staples Select Sector ETF", "etf_us", "XLP", 1, "USD"),
    ("XLV.US", "SPDR Health Care Select Sector ETF", "etf_us", "XLV", 1, "USD"),
    ("XLY.US", "SPDR Consumer Discretionary Select Sector ETF", "etf_us", "XLY", 1, "USD"),
    ("XLU.US", "SPDR Utilities Select Sector ETF", "etf_us", "XLU", 1, "USD"),
    ("SPY.US", "SPDR S&P 500 ETF Trust", "etf_us", "SPY", 1, "USD"),
    ("QQQ.US", "Invesco QQQ Trust", "etf_us", "QQQ", 1, "USD"),
    ("QQQM.US", "Invesco Nasdaq 100 ETF", "etf_us", "QQQM", 1, "USD"),
    ("DIA.US", "SPDR Dow Jones ETF Trust", "etf_us", "DIA", 1, "USD"),
    ("RSP.US", "Invesco S&P 500 Equal Weight ETF", "etf_us", "RSP", 1, "USD"),
    ("IWM.US", "iShares Russell 2000 ETF", "etf_us", "IWM", 1, "USD"),
    ("IJR.US", "iShares Core S&P Small-Cap ETF", "etf_us", "IJR", 1, "USD"),
    ("EFA.US", "iShares MSCI EAFE ETF", "etf_us", "EFA", 1, "USD"),
    ("EEM.US", "iShares MSCI Emerging Markets ETF", "etf_us", "EEM", 1, "USD"),
    ("EWJ.US", "iShares MSCI Japan ETF", "etf_us", "EWJ", 1, "USD"),
    ("EWA.US", "iShares MSCI Australia ETF", "etf_us", "EWA", 1, "USD"),
    ("EWC.US", "iShares MSCI Canada ETF", "etf_us", "EWC", 1, "USD"),
    ("EWL.US", "iShares MSCI Switzerland ETF", "etf_us", "EWL", 1, "USD"),
    ("EWT.US", "iShares MSCI Taiwan ETF", "etf_us", "EWT", 1, "USD"),
    ("EWU.US", "iShares MSCI United Kingdom ETF", "etf_us", "EWU", 1, "USD"),
    ("EWW.US", "iShares MSCI Mexico ETF", "etf_us", "EWW", 1, "USD"),
    ("EWZ.US", "iShares MSCI Brazil ETF", "etf_us", "EWZ", 1, "USD"),
    ("ILF.US", "iShares Latin America 40 ETF", "etf_us", "ILF", 1, "USD"),
    ("IYR.US", "iShares US Real Estate ETF", "etf_us", "IYR", 1, "USD"),
    ("SCHH.US", "Schwab US REIT ETF", "etf_us", "SCHH", 1, "USD"),
    ("KRE.US", "SPDR S&P Regional Banking ETF", "etf_us", "KRE", 1, "USD"),
    ("XBI.US", "SPDR S&P Biotech ETF", "etf_us", "XBI", 1, "USD"),
    ("IBB.US", "iShares Nasdaq Biotechnology ETF", "etf_us", "IBB", 1, "USD"),
    ("XOP.US", "SPDR S&P Oil & Gas Exploration ETF", "etf_us", "XOP", 1, "USD"),
    ("UNG.US", "United States Natural Gas Fund", "etf_us", "UNG", 1, "USD"),
    ("GDX.US", "VanEck Gold Miners ETF", "etf_us", "GDX", 1, "USD"),
    ("SIL.US", "Global X Silver Miners ETF", "etf_us", "SIL", 1, "USD"),
    ("GLD.US", "SPDR Gold Shares", "etf_us", "GLD", 1, "USD"),
    ("GLDM.US", "SPDR Gold MiniShares", "etf_us", "GLDM", 1, "USD"),
    ("IAU.US", "iShares Gold Trust", "etf_us", "IAU", 1, "USD"),
    ("SLV.US", "iShares Silver Trust", "etf_us", "SLV", 1, "USD"),
    ("IEF.US", "iShares 7-10 Year Treasury Bond ETF", "etf_us", "IEF", 1, "USD"),
    ("AGG.US", "iShares Core US Aggregate Bond ETF", "etf_us", "AGG", 1, "USD"),
    ("BND.US", "Vanguard Total Bond Market ETF", "etf_us", "BND", 1, "USD"),
    ("BSV.US", "Vanguard Short-Term Bond ETF", "etf_us", "BSV", 1, "USD"),
    ("VCSH.US", "Vanguard Short-Term Corporate Bond ETF", "etf_us", "VCSH", 1, "USD"),
    ("HYG.US", "iShares iBoxx High Yield Corp Bond ETF", "etf_us", "HYG", 1, "USD"),
    ("IEFA.US", "iShares Core MSCI EAFE ETF", "etf_us", "IEFA", 1, "USD"),
    ("IXUS.US", "iShares Core MSCI Total Intl ETF", "etf_us", "IXUS", 1, "USD"),
    ("QTUM.US", "Defiance Quantum ETF", "etf_us", "QTUM", 1, "USD"),
    ("JEPI.US", "JPMorgan Equity Premium Income ETF", "etf_us", "JEPI", 1, "USD"),
    ("JEPQ.US", "JPMorgan Nasdaq Equity Premium ETF", "etf_us", "JEPQ", 1, "USD"),
    ("BITO.US", "ProShares Bitcoin Strategy ETF", "etf_us", "BITO", 1, "USD"),
    ("IBIT.US", "iShares Bitcoin Trust Spot ETF", "etf_us", "IBIT", 1, "USD"),
]

INDICES = [
    ("UsaTec", "US Tech 100 Cash Index", "index", "US100", 1, "USD"),
    ("Usa500", "S&P 500 Cash Index", "index", "US500", 1, "USD"),
    ("UsaInd", "Dow Jones Industrial Cash Index", "index", "US30", 1, "USD"),
    ("UsaRus", "US 2000 Cash Index", "index", "US2000", 1, "USD"),
    ("Ger40", "DAX Cash Index", "index", "DE40", 1, "EUR"),
    ("GerMid50", "MDAX 50 Cash Index", "index", "DE50", 1, "EUR"),
    ("GerTec", "TECDAX 30 Cash Index", "index", "DETEC", 1, "EUR"),
    ("Fra40", "CAC40 Cash Index", "index", "FR40", 1, "EUR"),
    ("UK100", "UK100 Cash Index", "index", "UK100", 1, "GBP"),
    ("Euro50", "EuroStoxx 50 Cash Index", "index", "EU50", 1, "EUR"),
    ("Esp35", "IBEX 35 Cash Index", "index", "ES35", 1, "EUR"),
    ("Ita40", "Italy 40 Cash Index CFD", "index", "IT40", 1, "EUR"),
    ("Swi20", "Switzerland 20 Cash Index", "index", "CH20", 1, "CHF"),
    ("Neth25", "AEX25 Cash Index", "index", "NL25", 1, "EUR"),
    ("Jp225", "Nikkei 225 Cash Index", "index", "JP225", 1, "JPY"),
    ("HKInd", "Hang Seng Cash Index", "index", "HK50", 1, "HKD"),
    ("Bra50", "Bovespa Cash Index", "index", "BR50", 1, "BRL"),
    ("ChinaA50", "China A50 Index", "index", "CN50", 1, "USD"),
]

METALS = [
    ("GOLD", "Gold Spot", "metal", "XAUUSD", 1, "USD"),
    ("SILVER", "Silver Spot", "metal", "XAGUSD", 1, "USD"),
    ("Platinum", "Platinum Spot", "metal", "XPTUSD", 1, "USD"),
    ("Palladium", "Palladium Spot", "metal", "XPDUSD", 1, "USD"),
]

ENERGIES_SOFTS = [
    ("LCrude", "Light Crude Oil Spot", "energy", "USOIL", 1, "USD"),
    ("Brent", "Brent Crude Oil Spot", "energy", "UKOIL", 1, "USD"),
    ("Diesel", "Low Sulphur Gasoil Cash CFD", "energy", "GASOIL", 1, "USD"),
    ("NGas", "Natural Gas Cash CFD", "energy", "NATGAS", 1, "USD"),
    ("Coffee", "Coffee Cash CFD", "soft", "COFFEE", 1, "USD"),
    ("Cotton", "Cotton Cash CFD", "soft", "COTTON", 1, "USD"),
    ("Sugar", "Sugar Cash CFD", "soft", "SUGAR", 1, "USD"),
    ("Cocoa", "Cocoa Cash CFD", "soft", "COCOA", 1, "USD"),
    ("CoffeeR", "Coffee Robusta Cash CFD", "soft", "COFFEER", 1, "USD"),
]

FX = [
    ("EURUSD", "Euro vs US Dollar", "fx", "EURUSD", 0, "USD"),
    ("GBPUSD", "Great Britain Pound vs US Dollar", "fx", "GBPUSD", 0, "USD"),
    ("USDJPY", "US Dollar vs Japanese Yen", "fx", "USDJPY", 0, "JPY"),
    ("USDCAD", "US Dollar vs Canadian Dollar", "fx", "USDCAD", 0, "CAD"),
    ("USDCHF", "US Dollar vs Swiss Franc", "fx", "USDCHF", 0, "CHF"),
    ("EURJPY", "Euro vs Japanese Yen", "fx", "EURJPY", 0, "JPY"),
    ("EURGBP", "Euro vs Great Britain Pound", "fx", "EURGBP", 0, "GBP"),
    ("EURCHF", "Euro vs Swiss Franc", "fx", "EURCHF", 0, "CHF"),
    ("EURCAD", "Euro vs Canadian Dollar", "fx", "EURCAD", 0, "CAD"),
    ("GBPJPY", "Great Britain Pound vs Japanese Yen", "fx", "GBPJPY", 0, "JPY"),
    ("GBPCAD", "Great Britain Pound vs Canadian Dollar", "fx", "GBPCAD", 0, "CAD"),
    ("GBPCHF", "Great Britain Pound vs Swiss Franc", "fx", "GBPCHF", 0, "CHF"),
    ("CHFJPY", "Swiss Franc vs Japanese Yen", "fx", "CHFJPY", 0, "JPY"),
    ("CADJPY", "Canadian Dollar vs Japanese Yen", "fx", "CADJPY", 0, "JPY"),
    ("CADCHF", "Canadian Dollar vs Swiss Franc", "fx", "CADCHF", 0, "CHF"),
]

ALL_SYMBOLS = (
    CRYPTOS + US_STOCKS + ETFS_US + INDICES + METALS + ENERGIES_SOFTS + FX
)


# ----------------------------------------------------------------------
# Insertion
# ----------------------------------------------------------------------

INSERT_SQL = """
INSERT INTO broker_universe_activtrades(
    broker_symbol, description, asset_class, underlying_ticker,
    is_cfd, quote_ccy, discovered_at, last_seen_at, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(broker_symbol) DO UPDATE SET
    description       = excluded.description,
    asset_class       = excluded.asset_class,
    underlying_ticker = excluded.underlying_ticker,
    is_cfd            = excluded.is_cfd,
    quote_ccy         = excluded.quote_ccy,
    last_seen_at      = excluded.last_seen_at;
"""


def seed_static(con):
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = con.cursor()
    n = 0
    for row in ALL_SYMBOLS:
        broker_symbol, desc, asset_class, underlying, is_cfd, ccy = row
        cur.execute(
            INSERT_SQL,
            (broker_symbol, desc, asset_class, underlying,
             is_cfd, ccy, ts, ts, "seed_v1_capture_2026-05-30"),
        )
        n += 1
    con.commit()
    return n


# ----------------------------------------------------------------------
# Enrichissement MetaAPI (optionnel)
# ----------------------------------------------------------------------

def enrich_specs(con):
    """
    Pour chaque ligne instrument_broker_mapping deja peuplee
    (broker_symbol non NULL), interroge MetaAPI getSymbolSpecifications
    et met a jour lot_step / min_lots / tick_size / tick_value / contract_size.

    Si metaapi_provider n'est pas importable ou si is_configured() est False,
    on log et on saute proprement (idempotent, sans modification).
    """
    try:
        import metaapi_provider as mp
    except Exception as e:
        print("[WARN] metaapi_provider non importable: " + str(e))
        return 0

    if not getattr(mp, "is_configured", lambda: False)():
        print("[WARN] MetaAPI non configure (METAAPI_TOKEN / ACCOUNT_ID)")
        return 0

    cur = con.cursor()
    cur.execute(
        "SELECT thesium_ticker, broker_symbol FROM instrument_broker_mapping "
        "WHERE broker_symbol IS NOT NULL AND broker_symbol <> ''"
    )
    rows = cur.fetchall()
    updated = 0
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for thesium_ticker, broker_symbol in rows:
        try:
            spec = mp.get_symbol_specification(broker_symbol)
        except AttributeError:
            print("[WARN] metaapi_provider.get_symbol_specification absent")
            return updated
        except Exception as e:
            print("[WARN] spec " + broker_symbol + ": " + str(e))
            continue

        if not spec:
            continue

        cur.execute(
            "UPDATE instrument_broker_mapping SET "
            "contract_size=?, min_lots=?, lot_step=?, tick_size=?, "
            "tick_value=?, quote_ccy=COALESCE(?, quote_ccy), tradable=1, "
            "last_verified_at=?, verification_source='metaapi.getSymbolSpec' "
            "WHERE thesium_ticker=?",
            (
                spec.get("contractSize"),
                spec.get("minVolume"),
                spec.get("volumeStep"),
                spec.get("tickSize"),
                spec.get("tickValue"),
                spec.get("baseCurrency") or spec.get("quoteCurrency"),
                ts,
                thesium_ticker,
            ),
        )
        cur.execute(
            "INSERT INTO broker_mapping_audit(ts, action, thesium_ticker, "
            "broker_symbol, payload_json, notes) VALUES(?, ?, ?, ?, ?, ?)",
            (ts, "enrich_specs", thesium_ticker, broker_symbol,
             json.dumps(spec)[:2000], "metaapi enrich"),
        )
        updated += 1

    con.commit()
    return updated


def main():
    if not os.path.exists(DB_PATH):
        print("[ERR] DB introuvable: " + DB_PATH)
        sys.exit(2)

    do_enrich = "--enrich" in sys.argv

    print("[INFO] DB: " + DB_PATH)
    con = sqlite3.connect(DB_PATH)
    try:
        n = seed_static(con)
        print("[OK] " + str(n) + " symboles seed/upsert")

        cur = con.cursor()
        cur.execute("SELECT asset_class, COUNT(*) FROM broker_universe_activtrades "
                    "GROUP BY asset_class ORDER BY asset_class")
        for cls, cnt in cur.fetchall():
            print("       " + cls + ": " + str(cnt))

        if do_enrich:
            u = enrich_specs(con)
            print("[OK] enrichissement specs MetaAPI: " + str(u) + " lignes")
        else:
            print("[INFO] --enrich omis ; specs MetaAPI non rafraichies")
    finally:
        con.close()


if __name__ == "__main__":
    main()
