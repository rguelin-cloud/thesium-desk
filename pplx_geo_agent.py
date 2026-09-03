"""
pplx_geo_agent.py — Agent géopolitique Perplexity (étape 4/5)

Génère un contexte géopolitique structuré :
- 1-2 phrases summary
- score global 0-100 + regime
- top 5 risques (region, severity, horizon, type, narrative, catalysts,
  sectors_impacted, tickers_impacted_book mappés sur le book, mécanisme, sources)

Stockage : table pplx_geo_context (1 ligne par risque, PK=risk_id)
Modèle   : sonar-reasoning-pro (MODEL_REASON)
Cache    : 4h via TTL de pplx_query

Usage CLI :
    py -3.13 pplx_geo_agent.py             # refresh avec cache 4h
    py -3.13 pplx_geo_agent.py force       # force refresh
    py -3.13 pplx_geo_agent.py show        # affiche dernier snapshot
    py -3.13 pplx_geo_agent.py dry         # exécute sans persister
"""
from __future__ import annotations
import json, sys, sqlite3, time, datetime as dt
from pathlib import Path
from typing import Any

# Charge pplx_client depuis le dossier courant
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from pplx_client import pplx_query, MODEL_DEEP  # noqa: E402

_DB_PATH = _HERE / "thesium.db"
_CACHE_TTL = 4 * 3600          # 4 heures de cache pplx_query
_TOP_N = 5
_MODEL = MODEL_DEEP            # sonar-pro (validé OK sur ThesisAgent, JSON propre)
_AGENT_KEY = "geo_context"     # clé d'audit/cache dans pplx_query

# ---------------------------------------------------------------------------
# JSON Schema strict pour Perplexity (response_format=json_schema)
# ---------------------------------------------------------------------------
SCHEMA_GEO: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "global_risk_score", "regime", "risks"],
    "properties": {
        "summary": {
            "type": "string",
            "description": "1-2 phrases sur la météo géopolitique globale actuelle"
        },
        "global_risk_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100
        },
        "regime": {
            "type": "string",
            "enum": ["calm", "elevated", "stressed", "crisis"]
        },
        "risks": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "title", "region", "severity", "horizon",
                             "type", "narrative", "catalysts_next_30d",
                             "sectors_impacted", "tickers_impacted_book",
                             "mechanism", "sources"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string", "maxLength": 120},
                    "region": {"type": "string"},
                    "severity": {"type": "number", "minimum": 0, "maximum": 100},
                    "horizon": {"type": "string", "enum": ["0-1m", "1-3m", "3-12m"]},
                    "type": {
                        "type": "string",
                        "enum": ["military", "trade", "energy", "cyber",
                                 "sanctions", "election", "chokepoint"]
                    },
                    "narrative": {"type": "string", "maxLength": 1500},
                    "catalysts_next_30d": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 5
                    },
                    "sectors_impacted": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 10
                    },
                    "tickers_impacted_book": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 0,
                        "maxItems": 5
                    },
                    "mechanism": {"type": "string", "maxLength": 800},
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 6
                    }
                }
            }
        }
    }
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(_DB_PATH), timeout=10)
    con.execute("PRAGMA busy_timeout = 10000")  # [DB_LOCK_FIX_V1]
    con.row_factory = sqlite3.Row
    return con


def _ensure_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS pplx_geo_context (
        risk_id              TEXT PRIMARY KEY,
        title                TEXT,
        region               TEXT,
        severity             REAL,
        horizon              TEXT,
        type                 TEXT,
        narrative            TEXT,
        catalysts_json       TEXT,
        sectors_json         TEXT,
        tickers_json         TEXT,
        mechanism            TEXT,
        sources_json         TEXT,
        global_score         REAL,
        regime               TEXT,
        summary              TEXT,
        model                TEXT,
        ts                   INTEGER,
        generated_at         TEXT
    )
    """
    with _connect() as con:
        con.execute(sql)
        con.commit()


def _all_instruments() -> list[dict[str, str]]:
    sql = "SELECT ticker, name, sector, asset_class FROM instruments ORDER BY ticker"
    with _connect() as con:
        rows = con.execute(sql).fetchall()
    return [dict(r) for r in rows]


def _persist(payload: dict[str, Any], citations: list[str]) -> int:
    """Snapshot complet : DELETE puis INSERT des risques."""
    ts = int(time.time())
    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    global_score = float(payload.get("global_risk_score") or 0)
    regime = (payload.get("regime") or "elevated").lower()
    summary = payload.get("summary") or ""
    risks = payload.get("risks") or []

    rows_written = 0
    with _connect() as con:
        con.execute("DELETE FROM pplx_geo_context")
        for r in risks[:_TOP_N]:
            risk_id = str(r.get("id") or f"R{rows_written+1}")
            sources = r.get("sources") or []
            # Si Perplexity n'a pas mis de sources par risque, fallback sur citations globales
            if not sources and citations:
                sources = list(citations[:5])
            con.execute(
                """
                INSERT OR REPLACE INTO pplx_geo_context
                    (risk_id, title, region, severity, horizon, type, narrative,
                     catalysts_json, sectors_json, tickers_json, mechanism,
                     sources_json, global_score, regime, summary,
                     model, ts, generated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    risk_id,
                    str(r.get("title") or "")[:300],
                    str(r.get("region") or "")[:120],
                    float(r.get("severity") or 0),
                    str(r.get("horizon") or "1-3m"),
                    str(r.get("type") or "")[:30],
                    str(r.get("narrative") or "")[:2000],
                    json.dumps(r.get("catalysts_next_30d") or [], ensure_ascii=False),
                    json.dumps(r.get("sectors_impacted") or [], ensure_ascii=False),
                    json.dumps(r.get("tickers_impacted_book") or [], ensure_ascii=False),
                    str(r.get("mechanism") or "")[:1000],
                    json.dumps(sources, ensure_ascii=False),
                    global_score,
                    regime,
                    summary[:600],
                    _MODEL,
                    ts,
                    generated_at,
                ),
            )
            rows_written += 1
        con.commit()
    return rows_written


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def _build_prompt() -> str:
    instr = _all_instruments()
    by_sector: dict[str, list[str]] = {}
    for i in instr:
        s = (i.get("sector") or "Other").strip()
        by_sector.setdefault(s, []).append(i["ticker"])
    lines = []
    for sec in sorted(by_sector):
        lines.append(f"  - {sec}: {', '.join(sorted(by_sector[sec]))}")
    book_str = "\n".join(lines)
    today = dt.date.today().isoformat()

    return f"""Tu es un analyste géopolitique senior pour un fonds quantitatif.
Date du jour : {today}

CONTEXTE — Mon book contient ces instruments (groupés par secteur) :
{book_str}

OBJECTIF — Identifie les 5 risques géopolitiques les plus pressants à 0-12 mois,
classés par sévérité décroissante. Pour CHAQUE risque, indique précisément quels
tickers de MON book sont MATÉRIELLEMENT et DIRECTEMENT concernés, avec le
mécanisme de transmission.

RÈGLES DE NOTATION (très important) :
- global_risk_score : entier 0-100 sur l'échelle /100 (pas /10).
  Repères : 0-30 calme, 30-55 elevated, 55-75 stressed, 75-100 crisis.
- severity de chaque risque : entier 0-100 sur l'échelle /100 (pas /10).
  Ne renvoie JAMAIS de score inférieur à 30 — si un risque est mineur, ne l'inclus pas.

RÈGLES DE MAPPING tickers_impacted_book :
- MAXIMUM 5 tickers par risque (be picky)
- Uniquement les tickers dont la P&L bouge MATÉRIELLEMENT et DIRECTEMENT (>2% move probable)
- INTERDIT : citer SPY/QQQ "par contagion macro générale". Ne les cite que si l'événement
  cible explicitement le marché US large.
- INTERDIT : citer tous les tickers Tech à la fois. Sois sélectif.
- Exemples corrects :
    - Risque Taiwan/semi-conducteurs → NVDA, AAPL (exposition chaîne TSMC)
    - Risque mer Rouge/pétrole → XOM (direct), TSLA (input cost si carburant)
    - Risque élections US → SPY ou QQQ (régulation tech) OU UNH (healthcare reform)
    - Risque cyber → MSFT, GOOGL (si target probable)

CONTRAINTES TECHNIQUES :
- Exactement 5 risques
- tickers_impacted_book : uniquement des tickers de la liste ci-dessus (case exacte)
- sources : 2-5 URLs récentes vérifiables (presse financière, think tanks, gov)
- Sois factuel et actuel : utilise les news/évènements des 14 derniers jours

Le schéma JSON fourni est strict. Respecte les enums (regime, horizon, type) à la lettre.
"""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def run_geo_agent(force: bool = False, dry: bool = False) -> dict[str, Any]:
    _ensure_table()
    print(f"[geo] modèle = {_MODEL}, top_n = {_TOP_N}, ttl = {_CACHE_TTL}s")

    prompt = _build_prompt()
    print(f"[geo] prompt = {len(prompt)} chars")

    # Si force=True, on bypasse le cache pplx_query en utilisant ttl=0
    ttl = 0 if force else _CACHE_TTL

    t0 = time.time()
    result = pplx_query(
        agent=_AGENT_KEY,
        prompt=prompt,
        schema=SCHEMA_GEO,
        ttl=ttl,
        model=_MODEL,
        timeout=60,  # sonar-pro répond généralement en 15-25s
        system=(
            "Tu es un analyste géopolitique senior. "
            "Réponds UNIQUEMENT en JSON conforme au schéma fourni. "
            "Cite tes sources avec des URLs."
        ),
    )
    elapsed = time.time() - t0
    print(f"[geo] pplx_query terminé en {elapsed:.1f}s")

    if not result or not isinstance(result, dict):
        print("[geo] ERREUR : pplx_query a renvoyé None ou objet invalide")
        return {"status": "api_error", "rows": 0}

    payload = result.get("data")
    citations = result.get("citations") or []

    if not payload or not isinstance(payload, dict):
        print("[geo] ERREUR : data absent dans la réponse")
        print(f"[geo] result keys = {list(result.keys())}")
        return {"status": "parse_error", "rows": 0}

    risks = payload.get("risks") or []
    print(f"[geo] {len(risks)} risques | {len(citations)} citations globales")
    print(f"[geo] regime = {payload.get('regime')} | score = {payload.get('global_risk_score')}")
    print(f"[geo] summary : {(payload.get('summary') or '')[:200]}")
    print()
    for i, r in enumerate(risks[:_TOP_N], 1):
        tickers = ", ".join(r.get("tickers_impacted_book") or []) or "(aucun)"
        print(f"  R{i} [sev={r.get('severity',0):>3.0f}] {r.get('region','?')[:18]:18} "
              f"{r.get('horizon','?'):5} {r.get('type','?'):10} "
              f"{r.get('title','')[:50]:50} → {tickers}")

    if dry:
        print("\n[geo] dry-run : pas de persistance.")
        return {"status": "dry", "rows": len(risks), "data": payload}

    rows = _persist(payload, citations)
    print(f"\n[geo] {rows} lignes écrites dans pplx_geo_context")
    return {
        "status": "ok",
        "rows": rows,
        "elapsed_s": round(elapsed, 1),
        "regime": payload.get("regime"),
        "global_score": payload.get("global_risk_score"),
    }


def show_snapshot() -> None:
    _ensure_table()
    with _connect() as con:
        rows = con.execute(
            "SELECT * FROM pplx_geo_context ORDER BY severity DESC"
        ).fetchall()
    if not rows:
        print("[geo] aucun snapshot en base.")
        return
    first = rows[0]
    print(f"\n=== Snapshot géo (model={first['model']}) ===")
    print(f"Généré le        : {first['generated_at']}")
    print(f"Score global     : {first['global_score']}/100 ({first['regime']})")
    print(f"Summary          : {first['summary']}")
    print(f"\nRisques ({len(rows)}) :")
    for r in rows:
        tickers = ", ".join(json.loads(r["tickers_json"] or "[]")) or "(aucun)"
        catalysts = json.loads(r["catalysts_json"] or "[]")
        print(f"\n  [{r['risk_id']}] {r['title']}")
        print(f"    sev={r['severity']} ({r['horizon']}, {r['type']}, {r['region']})")
        print(f"    Tickers   : {tickers}")
        print(f"    Mécanisme : {r['mechanism']}")
        print(f"    Catalysts : {' ; '.join(catalysts)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(json.dumps(run_geo_agent(), indent=2, ensure_ascii=False))
    elif args[0] == "show":
        show_snapshot()
    elif args[0] == "dry":
        out = run_geo_agent(force=True, dry=True)
        # Retire 'data' du print pour pas spammer
        out.pop("data", None)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    elif args[0] == "force":
        print(json.dumps(run_geo_agent(force=True), indent=2, ensure_ascii=False))
    else:
        print(f"Usage: {sys.argv[0]} [show|dry|force]")
        sys.exit(1)
