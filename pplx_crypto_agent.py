# [PPLX_CRYPTO_AGENT_V1] CryptoAgent enrichi Perplexity pour NEXTONES.
# - Recupere TOUS les cryptos en DB (instruments WHERE asset_class='crypto' OR symbol IN ...)
# - Pour chaque symbole, recupere narrative + on-chain + reglementaire + sentiment + catalysts
# - Stocke dans table crypto_context (joinable avec instruments)
# - Cache 4h par defaut (crypto bouge vite mais pas a la seconde)
# - Tolere les echecs : si Perplexity timeout, garde l'ancien snapshot

from __future__ import annotations
import sqlite3
import time
import json
from pathlib import Path
from pplx_client import pplx_query, MODEL_DEEP

_DB_PATH = Path(__file__).resolve().parent / "thesium.db"


# ---------------------------------------------------------------------------
# Schema JSON pour la reponse Perplexity
# ---------------------------------------------------------------------------
SCHEMA_CRYPTO = {
    "type": "object",
    "properties": {
        "symbol": {
            "type": "string",
            "description": "Ticker crypto (BTC, ETH, SOL, etc.)"
        },
        "narrative_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Score narratif global 0-100 (100=narratif tres bullish dominant)"
        },
        "current_narratives": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {"type": "string"},
            "description": "Narratifs en cours (ex: 'BTC ETF inflows', 'ETH staking yield', 'SOL meme season')"
        },
        "regulatory_status": {
            "type": "object",
            "properties": {
                "us": {"type": "string", "description": "Statut SEC/CFTC, 1 phrase"},
                "eu_mica": {"type": "string", "description": "Conformite MiCA, 1 phrase"},
                "asia": {"type": "string", "description": "Singapour/Japon/HK, 1 phrase"}
            }
        },
        "onchain_signals": {
            "type": "array",
            "maxItems": 5,
            "items": {"type": "string"},
            "description": "Whale moves, exchange flows, unlock schedules significatifs"
        },
        "smart_money_positioning": {
            "type": "string",
            "description": "Ce que font les institutionnels (BlackRock, MicroStrategy, Grayscale, etc.) en 1-2 phrases"
        },
        "social_sentiment": {
            "type": "string",
            "enum": ["euphoric", "bullish", "neutral", "bearish", "capitulation"]
        },
        "key_catalysts_30d": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD si connu, sinon 'TBD'"},
                    "event": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["unlock", "upgrade", "listing", "regulatory", "macro", "earnings"]
                    },
                    "impact": {"type": "string", "enum": ["low", "medium", "high"]}
                },
                "required": ["event", "type"]
            }
        },
        "red_flags": {
            "type": "array",
            "maxItems": 5,
            "items": {"type": "string"},
            "description": "Exploits recents, depegs, team turnovers, manipulation suspectee"
        },
        "thesis_short": {
            "type": "string",
            "description": "Synthese 2-3 phrases pour decision trading"
        }
    },
    "required": ["symbol", "narrative_score", "current_narratives", "social_sentiment", "thesis_short"]
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _db():
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")  # [DB_LOCK_FIX_V1]
    conn.row_factory = sqlite3.Row
    return conn


def init_crypto_context_table():
    """Cree la table crypto_context si absente."""
    conn = _db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crypto_context (
                symbol TEXT PRIMARY KEY,
                narrative_score REAL,
                social_sentiment TEXT,
                current_narratives TEXT,
                regulatory_status TEXT,
                onchain_signals TEXT,
                smart_money_positioning TEXT,
                key_catalysts_30d TEXT,
                red_flags TEXT,
                thesis_short TEXT,
                citations TEXT,
                model TEXT,
                ts INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_crypto_context_ts ON crypto_context(ts)")
        conn.commit()
    finally:
        conn.close()


def list_crypto_symbols() -> list[str]:
    """Recupere les tickers crypto depuis la table instruments."""
    conn = _db()
    try:
        # Colonne reelle = 'ticker' (pas 'symbol')
        rows = conn.execute("""
            SELECT DISTINCT ticker FROM instruments
            WHERE LOWER(COALESCE(asset_class,'')) IN ('crypto','cryptocurrency','digital_asset')
               OR ticker IN ('BTC','ETH','SOL','BNB','XRP','ADA','DOGE','AVAX','DOT','LINK','MATIC','LTC','BCH','UNI','ATOM')
               OR ticker LIKE '%-USD'
               OR ticker LIKE '%USDT'
            ORDER BY ticker
        """).fetchall()
        return [r["ticker"] for r in rows]
    finally:
        conn.close()


def _save_context(symbol: str, result: dict):
    """Persiste le snapshot dans crypto_context (1 ligne par symbole, upsert)."""
    data = result["data"]
    conn = _db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO crypto_context (
                symbol, narrative_score, social_sentiment,
                current_narratives, regulatory_status, onchain_signals,
                smart_money_positioning, key_catalysts_30d, red_flags, thesis_short,
                citations, model, ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            data.get("narrative_score", 50),
            data.get("social_sentiment", "neutral"),
            json.dumps(data.get("current_narratives", []), ensure_ascii=False),
            json.dumps(data.get("regulatory_status", {}), ensure_ascii=False),
            json.dumps(data.get("onchain_signals", []), ensure_ascii=False),
            data.get("smart_money_positioning", ""),
            json.dumps(data.get("key_catalysts_30d", []), ensure_ascii=False),
            json.dumps(data.get("red_flags", []), ensure_ascii=False),
            data.get("thesis_short", ""),
            json.dumps(result.get("citations", []), ensure_ascii=False),
            result.get("model", ""),
            int(time.time()),
        ))
        conn.commit()
    finally:
        conn.close()


def get_context(symbol: str) -> dict | None:
    """Lit le snapshot le plus recent (utilise par UI et autres agents)."""
    conn = _db()
    try:
        row = conn.execute(
            "SELECT * FROM crypto_context WHERE symbol=?", (symbol,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        # Desolidifier les champs JSON
        for k in ("current_narratives", "regulatory_status", "onchain_signals",
                  "key_catalysts_30d", "red_flags", "citations"):
            try:
                d[k] = json.loads(d[k]) if d.get(k) else (None if k == "regulatory_status" else [])
            except Exception:
                d[k] = None if k == "regulatory_status" else []
        d["age_s"] = int(time.time()) - int(d.get("ts", 0))
        return d
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Core : fetch un symbole
# ---------------------------------------------------------------------------
def fetch_crypto_context(symbol: str, ttl_hours: int = 4) -> dict | None:
    """Interroge Perplexity pour un crypto donne. Renvoie {data, citations, model, ts} ou None."""
    sym_clean = symbol.replace("-USD", "").replace("USDT", "").upper()
    prompt = f"""Analyse le crypto {sym_clean} sur les 14 derniers jours pour un trader algorithmique professionnel.

Donne :
1. Score narratif global 0-100 (100 = narratif bullish dominant et evident)
2. Narratifs en cours qui drivent le prix (ETF, halving, upgrades, hype meme, regulatory tailwinds, etc.)
3. Statut reglementaire US (SEC/CFTC), EU (MiCA), Asie (Singapour/Japon/HK)
4. On-chain : whale moves significatifs, exchange flows (in/out), unlocks de tokens importants
5. Smart money : positions/moves recents de BlackRock, MicroStrategy, Grayscale, fonds majeurs
6. Sentiment social (Twitter/X, Reddit, indice F&G crypto specifique)
7. Catalystes a venir sur 30 jours (unlocks, upgrades reseau, listings, audiences SEC, FOMC pertinents)
8. Red flags : exploits, depegs, fuites de teams, suspicions de manipulation, dump whales
9. Synthese 2-3 phrases pour decision trading

Sources requises : CoinDesk, The Block, CoinTelegraph, Token Terminal, Arkham, Nansen, CryptoQuant, X/Twitter.
Reponds UNIQUEMENT en JSON conforme au schema."""

    return pplx_query(
        agent=f"crypto_{sym_clean.lower()}",
        prompt=prompt,
        schema=SCHEMA_CRYPTO,
        ttl=ttl_hours * 3600,
        model=MODEL_DEEP,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Boucle principale : refresh all crypto contexts
# ---------------------------------------------------------------------------
def refresh_all_crypto_contexts(ttl_hours: int = 4) -> dict:
    """
    Rafraichit le contexte de tous les cryptos en DB.
    Tolere les echecs : un symbole qui foire n'arrete pas les autres.
    Retourne un resume {ok, failed, skipped, elapsed_s}.
    """
    init_crypto_context_table()

    symbols = list_crypto_symbols()
    if not symbols:
        print("[CRYPTO-AGENT] Aucun symbole crypto trouve en DB")
        return {"ok": 0, "failed": 0, "skipped": 0, "elapsed_s": 0, "symbols": []}

    print(f"[CRYPTO-AGENT] Refresh contexte pour {len(symbols)} crypto(s): {', '.join(symbols)}")
    t0 = time.time()
    stats = {"ok": [], "failed": [], "skipped": []}

    for sym in symbols:
        try:
            result = fetch_crypto_context(sym, ttl_hours=ttl_hours)
            if result is None:
                stats["failed"].append(sym)
                print(f"  [{sym}] FAIL — pas de mise a jour (ancien snapshot conserve)")
            else:
                _save_context(sym, result)
                ns = result["data"].get("narrative_score", "?")
                sent = result["data"].get("social_sentiment", "?")
                src_count = len(result.get("citations", []))
                stats["ok"].append(sym)
                print(f"  [{sym}] OK narrative={ns} sentiment={sent} sources={src_count}")
            # Petit espacement pour ne pas matraquer l'API
            time.sleep(2)
        except Exception as e:
            stats["failed"].append(sym)
            print(f"  [{sym}] EXCEPTION: {e}")

    elapsed = round(time.time() - t0, 1)
    print(f"[CRYPTO-AGENT] Done en {elapsed}s | OK={len(stats['ok'])} FAIL={len(stats['failed'])}")
    return {
        "ok": len(stats["ok"]),
        "failed": len(stats["failed"]),
        "skipped": len(stats["skipped"]),
        "elapsed_s": elapsed,
        "symbols": stats,
    }


# ---------------------------------------------------------------------------
# CLI / test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_crypto_context_table()
        print("Table crypto_context creee")
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        print(list_crypto_symbols())
    elif len(sys.argv) > 1 and sys.argv[1] == "one" and len(sys.argv) > 2:
        sym = sys.argv[2].upper()
        r = fetch_crypto_context(sym)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        # Refresh all
        summary = refresh_all_crypto_contexts(ttl_hours=4)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
