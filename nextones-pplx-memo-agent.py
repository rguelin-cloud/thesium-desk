# -*- coding: utf-8 -*-
"""
MemoAgent Perplexity - on-demand par symbole.
Genere un memo structure (JSON) avec cache 1h via pplx_client.

Usage:
    py -3.13 pplx_memo_agent.py dry NVDA           # dry-run (pas de persist DB)
    py -3.13 pplx_memo_agent.py one NVDA           # force refresh + persist
    py -3.13 pplx_memo_agent.py get NVDA           # lit le dernier memo en DB
    py -3.13 pplx_memo_agent.py list               # liste symbols avec memo

Etape 5/5 du plan Perplexity. Cache court (1h) car on-demand.
"""
import sys
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone

# --- Config ---
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "thesium.db"
TABLE = "pplx_memo_context"
CACHE_TTL = 3600  # 1h
MODEL = "sonar-pro"
AGENT_PREFIX = "memo"

# --- JSON Schema Perplexity natif ---
# Strict maxLength sur chaque string pour eviter les boucles de repetition
# du modele (probleme observe sur sonar-pro quand champs trop libres).
MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "minLength": 20,
            "maxLength": 120,
            "description": "Titre punchy 60-100 chars (sans citations [N])"
        },
        "stance": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {
            "type": "string",
            "minLength": 40,
            "maxLength": 280,
            "description": "Resume 1-2 phrases (max 250 chars, sans citations)"
        },
        "bullets": {
            "type": "array",
            "items": {"type": "string", "minLength": 30, "maxLength": 280},
            "minItems": 3,
            "maxItems": 5,
            "description": "Observations cles, catalystes recents (1 phrase, 15-25 mots, citation [N] OK en fin)"
        },
        "risks": {
            "type": "array",
            "items": {"type": "string", "minLength": 30, "maxLength": 240},
            "minItems": 1,
            "maxItems": 3,
            "description": "Risques specifiques au symbole (1 phrase, 15-20 mots)"
        },
        "catalysts_upcoming": {
            "type": "array",
            "items": {"type": "string", "minLength": 20, "maxLength": 220},
            "minItems": 0,
            "maxItems": 3,
            "description": "Catalystes a venir (1 phrase courte)"
        },
        "time_horizon": {"type": "string", "enum": ["1w", "1m", "3m"]},
        "sources_summary": {
            "type": "string",
            "minLength": 20,
            "maxLength": 200,
            "description": "Description des sources utilisees (1 phrase)"
        }
    },
    "required": ["headline", "stance", "confidence", "summary", "bullets", "risks", "time_horizon", "sources_summary"]
}


def _utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_table(cx):
    cx.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            symbol TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            citations_json TEXT,
            generated_at TEXT NOT NULL,
            generated_ts INTEGER NOT NULL,
            model TEXT NOT NULL,
            elapsed_s REAL
        )
    """)
    cx.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_ts ON {TABLE}(generated_ts)")
    cx.commit()


def _get_cached_db(cx, symbol):
    _ensure_table(cx)
    row = cx.execute(
        f"SELECT payload_json, citations_json, generated_at, generated_ts, model "
        f"FROM {TABLE} WHERE symbol=?",
        (symbol,)
    ).fetchone()
    if not row:
        return None
    payload_json, citations_json, generated_at, generated_ts, model = row
    age = int(time.time()) - int(generated_ts)
    return {
        "symbol": symbol,
        "payload": json.loads(payload_json),
        "citations": json.loads(citations_json) if citations_json else [],
        "generated_at": generated_at,
        "model": model,
        "age_seconds": age,
        "cached": True
    }


def _save(cx, symbol, payload, citations, model, elapsed_s):
    _ensure_table(cx)
    now_ts = int(time.time())
    now_iso = _utcnow_iso()
    cx.execute(
        f"INSERT OR REPLACE INTO {TABLE}(symbol, payload_json, citations_json, "
        f"generated_at, generated_ts, model, elapsed_s) VALUES (?,?,?,?,?,?,?)",
        (
            symbol,
            json.dumps(payload, ensure_ascii=False),
            json.dumps(citations or [], ensure_ascii=False),
            now_iso, now_ts, model, float(elapsed_s or 0),
        )
    )
    cx.commit()


# Limites de safety net post-reception (cas ou le modele ignore le schema)
LIMITS = {
    "headline": 120,
    "summary": 280,
    "bullets_item": 280,
    "risks_item": 240,
    "catalysts_item": 220,
    "sources_summary": 200,
}

def _truncate(s, n):
    if not isinstance(s, str):
        return s
    s = s.strip()
    if len(s) <= n:
        return s
    # Coupe propre au dernier espace avant n
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut or s[:n]).rstrip(".,;:—- ") + "…"


def _sanitize_payload(payload):
    """Tronque les champs si depasse les limites + dedupe les listes."""
    if not isinstance(payload, dict):
        return payload
    for k, lim_key in (("headline", "headline"), ("summary", "summary"), ("sources_summary", "sources_summary")):
        if k in payload and isinstance(payload[k], str):
            payload[k] = _truncate(payload[k], LIMITS[lim_key])
    # Listes : tronque chaque item + dedupe (ordre preserve)
    for k, lim_key, max_items in (("bullets", "bullets_item", 5), ("risks", "risks_item", 3), ("catalysts_upcoming", "catalysts_item", 3)):
        if k in payload and isinstance(payload[k], list):
            seen = set()
            cleaned = []
            for item in payload[k]:
                if not isinstance(item, str):
                    continue
                t = _truncate(item, LIMITS[lim_key])
                key_dedup = t[:60].lower()  # cle de dedup courte
                if key_dedup in seen:
                    continue
                seen.add(key_dedup)
                cleaned.append(t)
                if len(cleaned) >= max_items:
                    break
            payload[k] = cleaned
    return payload


def _build_prompt(symbol):
    return (
        f"Genere un memo financier CONCIS et actionnable sur le symbole {symbol}.\n\n"
        f"Couvre :\n"
        f"- Actualite recente (30 derniers jours)\n"
        f"- Catalystes a venir (earnings, regulations, evenements macro affectant le titre)\n"
        f"- Sentiment de marche actuel (analystes, flux, options si crypto)\n"
        f"- Risques specifiques au symbole (pas les risques marche globaux)\n"
        f"- Stance claire (bullish/neutral/bearish) avec niveau de confiance 0-100\n\n"
        f"REGLES STRICTES :\n"
        f"- Chaque bullet/risk/catalyst = UNE SEULE phrase de 15-25 mots, max 250 caracteres.\n"
        f"- 3 a 5 bullets, 1 a 3 risks, 0 a 3 catalysts_upcoming.\n"
        f"- Texte en francais, sans markdown.\n"
        f"- Citations [N] autorisees uniquement en fin de phrase, pas de repetition.\n"
        f"- Une fois une phrase ecrite, NE PAS la repeter ni paraphraser.\n"
        f"- Reponds STRICTEMENT au format JSON demande."
    )


def _call_perplexity(symbol, ttl=CACHE_TTL):
    """
    Appel via pplx_client.pplx_query.
    Retourne le dict complet {data, citations, model, ts, elapsed_s} ou None.
    """
    try:
        from pplx_client import pplx_query
    except ImportError as e:
        raise RuntimeError(f"pplx_client introuvable : {e}")

    sym_clean = symbol.upper().strip()
    agent_key = f"{AGENT_PREFIX}_{sym_clean.lower()}"
    prompt = _build_prompt(sym_clean)

    result = pplx_query(
        agent=agent_key,
        prompt=prompt,
        schema=MEMO_SCHEMA,
        ttl=ttl,
        model=MODEL,
        timeout=60,
        system=(
            "Tu es un analyste financier senior. "
            "Reponds UNIQUEMENT en JSON conforme au schema fourni. "
            "Texte en francais. Cite tes sources."
        ),
    )
    return result  # None si echec, sinon dict


def run_memo_agent(symbol, force=False):
    """
    Point d'entree principal.
    Retourne : dict {symbol, payload, citations, generated_at, model, age_seconds, cached}.
    """
    symbol = symbol.upper().strip()
    if not symbol:
        raise ValueError("symbol vide")

    cx = sqlite3.connect(str(DB_PATH))
    try:
        # Cache DB hit (independant du cache pplx_client interne)
        if not force:
            cached = _get_cached_db(cx, symbol)
            if cached and cached["age_seconds"] < CACHE_TTL:
                return cached

        # Appel Perplexity (ttl=0 si force pour bypass cache client)
        ttl_eff = 0 if force else CACHE_TTL
        result = _call_perplexity(symbol, ttl=ttl_eff)
        if result is None:
            return {
                "symbol": symbol,
                "payload": None,
                "citations": [],
                "generated_at": _utcnow_iso(),
                "model": MODEL,
                "age_seconds": 0,
                "cached": False,
                "error": "pplx_query a renvoye None (cf logs)"
            }

        payload = result.get("data") or {}
        # Safety net : tronque + dedupe avant persistance
        payload = _sanitize_payload(payload)
        citations = result.get("citations") or []
        elapsed = result.get("elapsed_s") or 0
        model = result.get("model") or MODEL

        _save(cx, symbol, payload, citations, model, elapsed)

        return {
            "symbol": symbol,
            "payload": payload,
            "citations": citations,
            "generated_at": _utcnow_iso(),
            "model": model,
            "age_seconds": 0,
            "cached": False,
            "elapsed_s": elapsed
        }
    finally:
        cx.close()


def list_all(cx):
    _ensure_table(cx)
    rows = cx.execute(
        f"SELECT symbol, generated_at, model, generated_ts FROM {TABLE} ORDER BY generated_ts DESC"
    ).fetchall()
    return rows


# --- CLI ---
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower()

    if cmd == "list":
        cx = sqlite3.connect(str(DB_PATH))
        try:
            rows = list_all(cx)
            print(f"=== {len(rows)} memo(s) en cache DB ===")
            now_ts = int(time.time())
            for sym, ts_iso, model, ts_int in rows:
                age_min = (now_ts - int(ts_int)) // 60
                fresh = "FRESH" if age_min < 60 else "STALE"
                print(f"  {sym:8s}  {ts_iso}  ({age_min} min)  {model}  [{fresh}]")
        finally:
            cx.close()
        return

    if cmd in ("dry", "one", "get"):
        if len(sys.argv) < 3:
            print("ERROR: symbol manquant")
            print("Usage: py pplx_memo_agent.py dry|one|get SYMBOL")
            sys.exit(1)
        symbol = sys.argv[2]

        if cmd == "get":
            cx = sqlite3.connect(str(DB_PATH))
            try:
                cached = _get_cached_db(cx, symbol.upper())
                if not cached:
                    print(f"Aucun memo en cache pour {symbol}")
                    sys.exit(0)
                print(json.dumps(cached, indent=2, ensure_ascii=False))
            finally:
                cx.close()
            return

        if cmd == "dry":
            print(f"=== DRY-RUN MemoAgent : {symbol} ===")
            # ttl=0 pour forcer un appel (sinon cache client peut servir)
            result = _call_perplexity(symbol, ttl=0)
            if result is None:
                print("[KO] Appel Perplexity a echoue (cf logs ci-dessus)")
                sys.exit(2)
            # Sanitise aussi en dry pour voir le rendu final
            if isinstance(result, dict) and "data" in result:
                result["data"] = _sanitize_payload(result["data"])
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if cmd == "one":
            print(f"=== Force refresh MemoAgent : {symbol} ===")
            result = run_memo_agent(symbol, force=True)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if result.get("payload"):
                print(f"\n[OK] Persiste dans {TABLE}")
            else:
                print(f"\n[KO] Pas persiste (payload vide)")
            return

    print(f"Commande inconnue : {cmd}")
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
