# -*- coding: utf-8 -*-
"""
Jalon 9.5b - Generateur de memo IA pour shadow_perf_rolling.

Pour chaque variant de la derniere as_of_day (window=30) :
  - Build prompt avec description + stats prod/variant + delta + n_orders + n_cycles
  - Appel pplx_query (MODEL_FAST) avec JSON schema strict
  - UPDATE shadow_perf_rolling : recommendation_memo, memo_source, memo_generated_at, memo_cost_usd

Usage :
  py -3.13 .\\shadow_memo_generator.py
  py -3.13 .\\shadow_memo_generator.py --force         # bypass cache PPLX (TTL=0)
  py -3.13 .\\shadow_memo_generator.py --variant 2     # une seule variante

Idempotent : skip si memo deja present (sauf --force).
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime

# pplx_client est dans le meme dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pplx_client import pplx_query, MODEL_FAST  # noqa: E402

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
WINDOW_DAYS = 30

# JSON Schema strict pour le memo - le modele doit produire ces 4 champs
MEMO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict_court", "justification", "risques", "action_recommandee"],
    "properties": {
        "verdict_court": {
            "type": "string",
            "description": "Phrase tres courte (max 80 caracteres) qui resume le verdict"
        },
        "justification": {
            "type": "string",
            "description": "Analyse 3-5 phrases sur la performance vs prod : delta, sharpe, drawdown, fiabilite"
        },
        "risques": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Liste 2-4 risques identifies (data, regime, taille echantillon, etc.)"
        },
        "action_recommandee": {
            "type": "string",
            "description": "Une action concrete : Promouvoir / Rejeter / Continuer observation / Allonger fenetre"
        }
    }
}

SYSTEM_PROMPT = (
    "Tu es analyste quantitatif senior. Tu evalues une variante d'algorithme de trading "
    "shadow (paper-trading) vs la prod live. Reponds en francais, factuel, sans emoji. "
    "Reponds UNIQUEMENT en JSON conforme au schema fourni."
)


def fetch_latest_rows(conn, variant_filter=None):
    """Recupere les rows shadow_perf_rolling de la derniere as_of_day (window=30)."""
    cur = conn.execute(
        "SELECT MAX(as_of_day) FROM shadow_perf_rolling WHERE window_days=?",
        (WINDOW_DAYS,)
    )
    last = cur.fetchone()
    if not last or not last[0]:
        return None, []
    as_of = last[0]

    sql = (
        "SELECT p.id, p.variant_id, v.name AS variant_name, v.description AS variant_desc, "
        "       p.return_variant_pct, p.return_prod_pct, p.delta_pct, "
        "       p.sharpe_variant, p.sharpe_prod, "
        "       p.max_dd_variant_pct, p.max_dd_prod_pct, "
        "       p.n_cycles, p.n_orders_variant, p.n_orders_prod, "
        "       p.recommendation, p.recommendation_memo "
        "FROM shadow_perf_rolling p "
        "LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id "  # [SHADOW_MEMO_SQL_FIX_V2]
        "WHERE p.window_days=? AND p.as_of_day=? "
    )
    params = [WINDOW_DAYS, as_of]
    if variant_filter is not None:
        sql += "AND p.variant_id=? "
        params.append(variant_filter)
    sql += "ORDER BY p.variant_id"

    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return as_of, rows


def fmt_num(v, dec=3):
    if v is None:
        return "?"
    try:
        return ("{:." + str(dec) + "f}").format(float(v))
    except Exception:
        return str(v)


def build_prompt(row, as_of_day):
    """Construit un prompt riche avec toutes les stats."""
    name = row.get("variant_name") or ("variant_" + str(row.get("variant_id")))
    desc = row.get("variant_desc") or "(pas de description)"
    p = (
        "Tu evalues la variante shadow '" + name + "' sur " + str(WINDOW_DAYS)
        + " jours (as_of_day=" + str(as_of_day) + ").\n"
        "\n"
        "## Description variante\n"
        + desc + "\n"
        "\n"
        "## Statistiques fenetre J-" + str(WINDOW_DAYS) + " (sur "
        + str(row.get("n_cycles") or "?") + " cycles)\n"
        "| Metrique          | Prod           | Variante       | Delta          |\n"
        "|-------------------|----------------|----------------|----------------|\n"
        "| Retour (%)        | " + fmt_num(row.get("return_prod_pct")) + "        | "
        + fmt_num(row.get("return_variant_pct")) + "        | "
        + fmt_num(row.get("delta_pct")) + " pts |\n"
        "| Sharpe ratio      | " + fmt_num(row.get("sharpe_prod"), 2) + "         | "
        + fmt_num(row.get("sharpe_variant"), 2) + "         | "
        + fmt_num((row.get("sharpe_variant") or 0) - (row.get("sharpe_prod") or 0), 2) + "          |\n"
        "| Max Drawdown (%)  | " + fmt_num(row.get("max_dd_prod_pct")) + "       | "
        + fmt_num(row.get("max_dd_variant_pct")) + "       | "
        + fmt_num((row.get("max_dd_variant_pct") or 0) - (row.get("max_dd_prod_pct") or 0)) + " pts  |\n"
        "| Nombre d'ordres   | " + str(row.get("n_orders_prod") or "?") + "            | "
        + str(row.get("n_orders_variant") or "?") + "            | "
        + str((row.get("n_orders_variant") or 0) - (row.get("n_orders_prod") or 0)) + "             |\n"
        "\n"
        "## Recommandation algo\n"
        "Le moteur a classe cette variante comme : **" + str(row.get("recommendation") or "neutral") + "**\n"
        "(Regles : champion si delta > +2 pts ET Sharpe variant > Sharpe prod ; "
        "reject si delta < -1 pt ; sinon neutral.)\n"
        "\n"
        "## Ta mission\n"
        "1. Verdict court (max 80 caracteres).\n"
        "2. Justification factuelle 3-5 phrases : performance vs prod, qualite (sharpe), risque (DD), fiabilite (taille echantillon).\n"
        "3. 2 a 4 risques identifies (regime de marche, sample size, biais, etc.).\n"
        "4. Action recommandee concrete (Promouvoir / Rejeter / Continuer observation / Allonger fenetre).\n"
        "Soit factuel. N'invente pas de donnees externes.\n"
    )
    return p


def estimate_cost_usd(usage):
    """Estimation cout USD : sonar = $1/M input, $1/M output (approx)."""
    if not isinstance(usage, dict):
        return 0.0
    pt = usage.get("prompt_tokens", 0) or 0
    ct = usage.get("completion_tokens", 0) or 0
    return round((pt + ct) / 1_000_000.0, 6)


def update_memo(conn, row_id, memo_text, model, cost_usd):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE shadow_perf_rolling "
        "SET recommendation_memo=?, memo_source=?, memo_generated_at=?, memo_cost_usd=? "
        "WHERE id=?",
        (memo_text, "pplx:" + model, now, cost_usd, row_id)
    )
    conn.commit()


def generate_for_row(row, as_of_day, force=False):
    if row.get("recommendation_memo") and not force:
        print("  [SKIP] memo deja present (id={}, variant={})".format(
            row["id"], row.get("variant_name")))
        return None

    prompt = build_prompt(row, as_of_day)
    ttl = 0 if force else 24 * 3600  # 24h cache par defaut

    name = row.get("variant_name") or str(row.get("variant_id"))
    res = pplx_query(
        agent="shadow_memo_" + name,
        prompt=prompt,
        schema=MEMO_SCHEMA,
        ttl=ttl,
        model=MODEL_FAST,
        timeout=60,
        system=SYSTEM_PROMPT,
    )
    if not res or not res.get("data"):
        print("  [ERR] pplx_query a retourne None pour variant", name)
        return None

    data = res["data"]
    # Format memo lisible
    memo_lines = []
    memo_lines.append("VERDICT : " + str(data.get("verdict_court", "?")))
    memo_lines.append("")
    memo_lines.append("JUSTIFICATION")
    memo_lines.append(str(data.get("justification", "?")))
    memo_lines.append("")
    risques = data.get("risques", []) or []
    if risques:
        memo_lines.append("RISQUES")
        for r in risques:
            memo_lines.append("- " + str(r))
        memo_lines.append("")
    memo_lines.append("ACTION RECOMMANDEE")
    memo_lines.append(str(data.get("action_recommandee", "?")))

    citations = res.get("citations", []) or []
    if citations:
        memo_lines.append("")
        memo_lines.append("SOURCES")
        for i, c in enumerate(citations[:5], 1):
            memo_lines.append("[" + str(i) + "] " + str(c))

    memo_text = "\n".join(memo_lines)
    return {
        "memo_text": memo_text,
        "model": res.get("model", MODEL_FAST),
        "cost_usd": 0.0,  # cost reel pas expose, on laisse 0
        "data": data,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Regenere meme si memo present")
    ap.add_argument("--variant", type=int, default=None, help="Filtrer un variant_id")
    args = ap.parse_args()

    print("=" * 70)
    print("SHADOW MEMO GENERATOR - Jalon 9.5b")
    print("DB :", DB)
    print("Force :", args.force, "| Variant filter :", args.variant)
    print("=" * 70)

    conn = sqlite3.connect(DB, timeout=15.0)
    try:
        as_of, rows = fetch_latest_rows(conn, args.variant)
        if not rows:
            print("[ERR] Aucune row trouvee pour window=", WINDOW_DAYS)
            return 2
        print("as_of_day :", as_of, "| rows a traiter :", len(rows))
        print()

        n_ok = 0
        n_skip = 0
        n_err = 0
        for row in rows:
            print("[VARIANT {}] {}".format(row["variant_id"], row.get("variant_name")))
            try:
                result = generate_for_row(row, as_of, force=args.force)
                if result is None:
                    if row.get("recommendation_memo") and not args.force:
                        n_skip += 1
                    else:
                        n_err += 1
                    continue
                update_memo(conn, row["id"], result["memo_text"],
                            result["model"], result["cost_usd"])
                n_ok += 1
                # Affiche les 3 premieres lignes pour controle
                preview = result["memo_text"].split("\n")[:3]
                for ln in preview:
                    print("    | " + ln)
                print()
            except Exception as e:
                n_err += 1
                print("  [EXC] {}: {}".format(type(e).__name__, e))
                print()

        print("=" * 70)
        print("OK : {} | SKIP : {} | ERR : {}".format(n_ok, n_skip, n_err))
        print("=" * 70)
        return 0 if n_err == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
