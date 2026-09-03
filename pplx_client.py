# [PPLX_CLIENT_V1] Client Perplexity partage par tous les agents NEXTONES.
# - Cache DB (pplx_cache) avec TTL par appel
# - Audit DB (pplx_audit) : prompt, reponse, citations, model, cost
# - Output JSON structure (response_format json_schema)
# - Fallback safe : retourne None si echec (l'agent appelant doit gerer)
# - Pas de boucle de retry agressive (on protege le rate limit)

from __future__ import annotations
import os
import json
import time
import sqlite3
import hashlib
import requests
from pathlib import Path
from typing import Any, Optional

# Localisation projet
_PROJECT_ROOT = Path(__file__).resolve().parent
_DB_PATH = _PROJECT_ROOT / "thesium.db"
_ENV_PATH = _PROJECT_ROOT / ".env"

# Lecture .env (pas d'erreur si dotenv absent : on lit env direct)
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)
except ImportError:
    pass

PPLX_API_KEY = os.environ.get("PPLX_API_KEY", "")
PPLX_ENDPOINT = "https://api.perplexity.ai/chat/completions"

# Modeles disponibles (selon doc officielle Perplexity)
MODEL_FAST = "sonar"                    # rapide, web search
MODEL_DEEP = "sonar-pro"                # multi-sources, plus profond
MODEL_REASON = "sonar-reasoning-pro"    # raisonnement structure

# Cout approximatif par 1M tokens (USD) — pour audit/monitoring uniquement
_COST_PER_MTOK = {
    "sonar":               {"in": 1.0,  "out": 1.0},
    "sonar-pro":           {"in": 3.0,  "out": 15.0},
    "sonar-reasoning-pro": {"in": 2.0,  "out": 8.0},
}


def _db():
    """Connexion DB avec row factory dict-like."""
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")  # [DB_LOCK_FIX_V1]
    conn.row_factory = sqlite3.Row
    return conn


def _cache_key(agent: str, prompt: str, schema_json: str, model: str) -> str:
    """Cle de cache deterministe."""
    h = hashlib.sha256(f"{agent}|{prompt}|{schema_json}|{model}".encode("utf-8")).hexdigest()[:24]
    return f"pplx_{agent}_{h}"


def _cache_get(key: str, ttl_seconds: int) -> Optional[dict]:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT data, ts FROM pplx_cache WHERE key=? AND (?-ts) < ?",
            (key, int(time.time()), ttl_seconds)
        ).fetchone()
        if row:
            return json.loads(row["data"])
    except Exception as e:
        print(f"[PPLX-CACHE] read error: {e}")
    finally:
        conn.close()
    return None


def _cache_put(key: str, data: dict):
    conn = _db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO pplx_cache(key, data, ts) VALUES (?, ?, ?)",
            (key, json.dumps(data, ensure_ascii=False), int(time.time()))
        )
        conn.commit()
    except Exception as e:
        print(f"[PPLX-CACHE] write error: {e}")
    finally:
        conn.close()


def _audit_log(agent: str, prompt: str, response: dict, citations: list,
               model: str, usage: dict):
    """Persiste l'appel pour audit/cout."""
    try:
        cost = 0.0
        if model in _COST_PER_MTOK and usage:
            rates = _COST_PER_MTOK[model]
            cost = (usage.get("prompt_tokens", 0) / 1e6) * rates["in"] \
                 + (usage.get("completion_tokens", 0) / 1e6) * rates["out"]
        conn = _db()
        conn.execute(
            "INSERT INTO pplx_audit(agent, prompt, response, citations, model, cost_usd, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agent, prompt[:2000], json.dumps(response, ensure_ascii=False),
             json.dumps(citations, ensure_ascii=False), model, cost, int(time.time()))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[PPLX-AUDIT] log error: {e}")


def pplx_query(
    agent: str,
    prompt: str,
    schema: dict,
    ttl: int = 3600,
    model: str = MODEL_FAST,
    timeout: int = 45,
    system: str = "Tu es un analyste financier rigoureux. Reponds UNIQUEMENT en JSON conforme au schema fourni. Cite tes sources.",
) -> Optional[dict]:
    """
    Interroge Perplexity API avec cache + audit + fallback safe.

    Args:
        agent: nom de l'agent appelant (ex: 'crypto_context', 'factor_quality')
        prompt: question utilisateur
        schema: JSON Schema pour structurer la reponse
        ttl: duree de cache en secondes (defaut 1h)
        model: modele Perplexity (MODEL_FAST/DEEP/REASON)
        timeout: timeout HTTP en secondes
        system: prompt systeme

    Returns:
        dict avec {data, citations, model, ts} ou None si echec.
    """
    if not PPLX_API_KEY:
        print(f"[PPLX-{agent}] PPLX_API_KEY absente, abort")
        return None

    schema_json = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    key = _cache_key(agent, prompt, schema_json, model)

    # 1) Cache
    cached = _cache_get(key, ttl)
    if cached:
        print(f"[PPLX-{agent}] cache hit")
        return cached

    # 2) Appel API
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": schema}
        },
        "return_citations": True,
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json",
    }

    t0 = time.time()
    try:
        r = requests.post(PPLX_ENDPOINT, json=payload, headers=headers, timeout=timeout)
        elapsed = time.time() - t0
        if r.status_code != 200:
            print(f"[PPLX-{agent}] HTTP {r.status_code} en {elapsed:.1f}s : {r.text[:200]}")
            return None
        body = r.json()
    except requests.Timeout:
        print(f"[PPLX-{agent}] TIMEOUT apres {timeout}s")
        return None
    except Exception as e:
        print(f"[PPLX-{agent}] erreur reseau: {e}")
        return None

    # 3) Parse reponse
    try:
        raw_content = body["choices"][0]["message"]["content"]
        content = json.loads(raw_content)
        citations = body.get("citations", []) or []
        usage = body.get("usage", {}) or {}
    except Exception as e:
        print(f"[PPLX-{agent}] parse error: {e} | body: {str(body)[:300]}")
        return None

    result = {
        "data": content,
        "citations": citations,
        "model": model,
        "ts": int(time.time()),
        "elapsed_s": round(elapsed, 2),
    }

    # 4) Cache + audit
    _cache_put(key, result)
    _audit_log(agent, prompt, content, citations, model, usage)
    print(f"[PPLX-{agent}] OK en {elapsed:.1f}s, {len(citations)} sources")
    return result


def get_recent_audit(agent: Optional[str] = None, hours: int = 24, limit: int = 50) -> list:
    """Recupere les derniers appels (pour UI / debug)."""
    conn = _db()
    try:
        cutoff = int(time.time()) - hours * 3600
        if agent:
            rows = conn.execute(
                "SELECT agent, model, cost_usd, ts FROM pplx_audit WHERE agent=? AND ts>=? ORDER BY ts DESC LIMIT ?",
                (agent, cutoff, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT agent, model, cost_usd, ts FROM pplx_audit WHERE ts>=? ORDER BY ts DESC LIMIT ?",
                (cutoff, limit)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def total_cost(hours: int = 24) -> float:
    """Cout cumule sur la periode."""
    conn = _db()
    try:
        cutoff = int(time.time()) - hours * 3600
        row = conn.execute(
            "SELECT SUM(cost_usd) AS total FROM pplx_audit WHERE ts>=?",
            (cutoff,)
        ).fetchone()
        return float(row["total"] or 0.0)
    finally:
        conn.close()


if __name__ == "__main__":
    # Test de fumee
    test_schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["answer"]
    }
    r = pplx_query("smoke_test", "Quelle est la capitale de la France ? Reponds court.",
                   test_schema, ttl=60)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"Cout 24h: ${total_cost(24):.4f}")
