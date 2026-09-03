# -*- coding: utf-8 -*-
"""
diff_engine.py
==============
Calcule et rend les diff J-1 / J-7 entre cycles decisionnels ThesiumDesk.

API publique :
    compute_cycle_diff(conn, today_cycle_id, ref="J-1") -> dict
    render_diff_markdown(diff_j1, diff_j7) -> str

Sources :
    - regime_log               (NAV, cash, regime, n_positions)
    - portfolio_history        (invested_pct)
    - factor_quality_history   (scores factors)
    - pplx_geo_history         (regions, sentiments)
    - cycle_reconciliation_log (decisions par cycle)
    - theses                   (conviction par ticker x cycle)

Auteur : Computer pour Nextones/ThesiumDesk - Etape 2.2
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "nav_pct": 0.2,           # % NAV
    "conviction": 0.5,        # points conviction
    "factor_score": 0.05,     # delta score factor
    "invested_pct": 0.5,      # % invested
}

REF_OFFSETS = {"J-1": 1, "J-7": 7}
REF_WINDOWS = {"J-1": (0, 2), "J-7": (5, 9)}  # tolerance [min, max] jours


# ---------------------------------------------------------------------------
# Helpers temporels
# ---------------------------------------------------------------------------

def _parse_cycle_date(cycle_id: str) -> Optional[datetime]:
    """cycle_id format YYYYMMDD-HHMMSS -> datetime."""
    if not cycle_id or len(cycle_id) < 8:
        return None
    try:
        return datetime.strptime(cycle_id[:8], "%Y%m%d")
    except ValueError:
        return None


def _find_ref_cycle(conn: sqlite3.Connection, today_cycle_id: str, ref: str) -> Optional[Tuple[str, int]]:
    """
    Trouve le cycle de reference dans la fenetre de tolerance.
    Retourne (ref_cycle_id, distance_days) ou None.
    """
    today_dt = _parse_cycle_date(today_cycle_id)
    if today_dt is None:
        return None
    min_d, max_d = REF_WINDOWS[ref]
    target = today_dt - timedelta(days=REF_OFFSETS[ref])
    lo = (today_dt - timedelta(days=max_d)).strftime("%Y%m%d")
    hi = (today_dt - timedelta(days=min_d)).strftime("%Y%m%d")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cycle_id FROM regime_log
        WHERE substr(cycle_id, 1, 8) BETWEEN ? AND ?
        ORDER BY cycle_id DESC
        """,
        (lo, hi),
    )
    candidates = [r[0] for r in cur.fetchall()]
    if not candidates:
        return None
    # Prend le cycle dont la date est la plus proche de target
    best = None
    best_dist_abs = None
    target_str = target.strftime("%Y%m%d")
    for cid in candidates:
        d = abs((_parse_cycle_date(cid) - target).days)
        if best_dist_abs is None or d < best_dist_abs:
            best = cid
            best_dist_abs = d
    real_dist = (today_dt - _parse_cycle_date(best)).days
    return (best, real_dist)


# ---------------------------------------------------------------------------
# Loaders par source
# ---------------------------------------------------------------------------

def _load_regime(conn: sqlite3.Connection, cycle_id: str) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        "SELECT regime, invested_pct, nav, cash, n_positions FROM regime_log WHERE cycle_id=? LIMIT 1",
        (cycle_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "regime": row[0],
        "invested_pct": row[1],
        "nav": row[2],
        "cash": row[3],
        "n_positions": row[4],
    }


def _load_factor_quality(conn: sqlite3.Connection, cycle_id: str) -> Dict[str, Any]:
    cur = conn.cursor()
    cur.execute(
        "SELECT payload_json FROM factor_quality_history WHERE cycle_id=? ORDER BY id DESC LIMIT 1",
        (cycle_id,),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except Exception:
        return {}


def _load_geo(conn: sqlite3.Connection, cycle_id: str) -> Dict[str, Any]:
    cur = conn.cursor()
    cur.execute(
        "SELECT payload_json FROM pplx_geo_history WHERE cycle_id=? ORDER BY id DESC LIMIT 1",
        (cycle_id,),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except Exception:
        return {}


def _load_decisions(conn: sqlite3.Connection, cycle_id: str) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """SELECT ticker, action, qty_in, side_in, conviction_max, delta_target_pct
           FROM cycle_reconciliation_log WHERE cycle_id=?""",
        (cycle_id,),
    )
    out = []
    for r in cur.fetchall():
        out.append({
            "ticker": r[0], "action": r[1], "qty_in": r[2], "side": r[3],
            "conviction": r[4], "delta_target_pct": r[5],
        })
    return out


def _load_convictions(conn: sqlite3.Connection, cycle_id: str) -> Dict[str, float]:
    """Conviction max par ticker pour ce cycle (depuis theses)."""
    cur = conn.cursor()
    # Le schema theses contient cycle_id et conviction_score
    try:
        cur.execute(
            """SELECT ticker, MAX(conviction_score) FROM theses
               WHERE cycle_id=? GROUP BY ticker""",
            (cycle_id,),
        )
        return {t: c for t, c in cur.fetchall() if c is not None}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Diff par section
# ---------------------------------------------------------------------------

def _diff_portfolio(today: Dict, ref: Dict) -> Dict[str, Any]:
    if not today or not ref:
        return {"unavailable": True}

    def d(field, pct_ref=False):
        t, r = today.get(field), ref.get(field)
        if t is None or r is None:
            return None
        delta = t - r
        out = {"today": t, "ref": r, "delta": round(delta, 4)}
        if pct_ref and r:
            out["pct"] = round(delta / r * 100, 2)
        return out

    return {
        "nav":          d("nav", pct_ref=True),
        "cash":         d("cash", pct_ref=True),
        "invested_pct": d("invested_pct"),
        "n_positions":  d("n_positions"),
        "regime": {
            "today": today.get("regime"),
            "ref": ref.get("regime"),
            "changed": today.get("regime") != ref.get("regime"),
        },
    }


def _diff_factor_quality(today: Dict, ref: Dict) -> Dict[str, Any]:
    if not today and not ref:
        return {"unavailable": True}
    # Heuristique : on cherche des scores numeriques dans le payload
    # Format typique : {"factors": {"MOMENTUM": {"score": 0.62, ...}, ...}}
    # Sinon fallback : compare cles top-level.
    t_factors = _extract_factors(today)
    r_factors = _extract_factors(ref)
    added = sorted(set(t_factors) - set(r_factors))
    removed = sorted(set(r_factors) - set(t_factors))
    changed = []
    for k in sorted(set(t_factors) & set(r_factors)):
        tv = t_factors[k]
        rv = r_factors[k]
        if isinstance(tv, (int, float)) and isinstance(rv, (int, float)):
            delta = tv - rv
            if abs(delta) >= THRESHOLDS["factor_score"]:
                changed.append({"factor": k, "from": rv, "to": tv, "delta": round(delta, 4)})
    return {"added": added, "removed": removed, "changed": changed}


_META_KEYS = {"ts", "created_at", "updated_at", "cycle_id", "id", "snapshot_date",
              "timestamp", "date", "version", "source"}


def _extract_factors(payload: Dict) -> Dict[str, float]:
    """Tente d'extraire un dict {factor_name: score}. Tolerant.

    Strategie :
      1) payload['factors'] si dict -> on lit .score / scalar
      2) sinon top-level numerics MAIS exclut les cles meta (ts, created_at, etc.)
         et n'accepte que si >= 2 factors trouves (sinon on considere que le payload
         n'expose pas de factor scoring exploitable -> {} pour eviter faux positifs)
    """
    if not isinstance(payload, dict):
        return {}
    # Essai 1 : payload["factors"]
    f = payload.get("factors")
    if isinstance(f, dict):
        out = {}
        for k, v in f.items():
            if isinstance(v, dict) and "score" in v:
                out[k] = v["score"]
            elif isinstance(v, (int, float)):
                out[k] = v
        if out:
            return out
    # Essai 2 : top-level numerics (filtre meta)
    out = {k: v for k, v in payload.items()
           if isinstance(v, (int, float)) and k.lower() not in _META_KEYS}
    # Si moins de 2 factors, c'est probablement pas un payload de factors
    if len(out) < 2:
        return {}
    return out


def _diff_geo(today: Dict, ref: Dict) -> Dict[str, Any]:
    if not today and not ref:
        return {"unavailable": True}
    t_regions = _extract_geo_regions(today)
    r_regions = _extract_geo_regions(ref)
    added_keys = sorted(set(t_regions) - set(r_regions))
    removed_keys = sorted(set(r_regions) - set(t_regions))
    sentiment_shifts = []
    for k in sorted(set(t_regions) & set(r_regions)):
        t_sent = t_regions[k].get("sentiment")
        r_sent = r_regions[k].get("sentiment")
        if t_sent and r_sent and t_sent != r_sent:
            sentiment_shifts.append({"region": k, "from": r_sent, "to": t_sent})
    return {
        "added": [{"region": k, **t_regions[k]} for k in added_keys],
        "removed": [{"region": k, **r_regions[k]} for k in removed_keys],
        "sentiment_shifts": sentiment_shifts,
    }


def _extract_geo_regions(payload: Dict) -> Dict[str, Dict]:
    """Extrait dict {region_name: {sentiment, narrative, ...}}."""
    if not isinstance(payload, dict):
        return {}
    # Essai : payload["regions"] ou payload["geo"] ou liste
    for key in ("regions", "geo", "items", "events"):
        v = payload.get(key)
        if isinstance(v, dict):
            return {k: (vv if isinstance(vv, dict) else {"value": vv}) for k, vv in v.items()}
        if isinstance(v, list):
            out = {}
            for it in v:
                if isinstance(it, dict):
                    name = it.get("region") or it.get("name") or it.get("country") or it.get("title")
                    if name:
                        out[str(name)] = it
            if out:
                return out
    return {}


def _diff_decisions(today: List[Dict], ref: List[Dict],
                    t_conv: Dict[str, float], r_conv: Dict[str, float]) -> Dict[str, Any]:
    t_by = {d["ticker"]: d for d in today}
    r_by = {d["ticker"]: d for d in ref}
    new_buys = []
    new_sells = []
    removed = []
    for tk, d in t_by.items():
        if tk not in r_by:
            entry = {"ticker": tk, "qty_pct": d.get("qty_in"), "delta_pct": d.get("delta_target_pct"),
                     "conviction": d.get("conviction"), "side": d.get("side"), "action": d.get("action")}
            if d.get("side") == "BUY":
                new_buys.append(entry)
            elif d.get("side") == "SELL":
                new_sells.append(entry)
    # NOTE : on n'affiche PAS les decisions "retirees" car chaque cycle a son
    # propre set de decisions (cycle_reconciliation_log), elles ne sont pas
    # "annulees" mais simplement non-renouvelees. On garde removed=[] pour
    # ne pas polluer le memo, mais on conserve le calcul si besoin debug.
    removed = []  # intentionally empty - cf. note ci-dessus
    # Conviction shifts (sur tickers presents les 2 jours)
    conv_shifts = []
    for tk in set(t_conv) & set(r_conv):
        delta = t_conv[tk] - r_conv[tk]
        if abs(delta) >= THRESHOLDS["conviction"]:
            conv_shifts.append({"ticker": tk, "from": round(r_conv[tk], 2),
                                "to": round(t_conv[tk], 2), "delta": round(delta, 2)})
    conv_shifts.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return {
        "new_buys": new_buys,
        "new_sells": new_sells,
        "removed": removed,
        "conviction_shifts": conv_shifts[:10],  # top 10
    }


# ---------------------------------------------------------------------------
# API publique : compute_cycle_diff
# ---------------------------------------------------------------------------

def compute_cycle_diff(conn: sqlite3.Connection, today_cycle_id: str, ref: str = "J-1") -> Dict[str, Any]:
    """
    Calcule le diff entre today_cycle_id et le cycle de reference (J-1 ou J-7).
    Retourne un dict structure (voir docstring du module).
    """
    if ref not in REF_OFFSETS:
        raise ValueError(f"ref must be J-1 or J-7, got {ref}")

    ref_info = _find_ref_cycle(conn, today_cycle_id, ref)
    if ref_info is None:
        return {
            "ref_label": ref,
            "today_cycle_id": today_cycle_id,
            "ref_cycle_id": None,
            "ref_distance_days": None,
            "unavailable": True,
            "reason": f"No cycle found in window for {ref}",
        }
    ref_cycle_id, dist = ref_info

    today_regime = _load_regime(conn, today_cycle_id)
    ref_regime   = _load_regime(conn, ref_cycle_id)
    today_fq     = _load_factor_quality(conn, today_cycle_id)
    ref_fq       = _load_factor_quality(conn, ref_cycle_id)
    today_geo    = _load_geo(conn, today_cycle_id)
    ref_geo      = _load_geo(conn, ref_cycle_id)
    today_dec    = _load_decisions(conn, today_cycle_id)
    ref_dec      = _load_decisions(conn, ref_cycle_id)
    today_conv   = _load_convictions(conn, today_cycle_id)
    ref_conv     = _load_convictions(conn, ref_cycle_id)

    portfolio = _diff_portfolio(today_regime, ref_regime)
    factor    = _diff_factor_quality(today_fq, ref_fq)
    geo       = _diff_geo(today_geo, ref_geo)
    decisions = _diff_decisions(today_dec, ref_dec, today_conv, ref_conv)

    summary = _build_summary(portfolio, decisions, factor, ref, dist)

    return {
        "ref_label": ref,
        "today_cycle_id": today_cycle_id,
        "ref_cycle_id": ref_cycle_id,
        "ref_distance_days": dist,
        "portfolio": portfolio,
        "decisions": decisions,
        "factor_quality": factor,
        "geo": geo,
        "summary_line": summary,
    }


def _build_summary(portfolio: Dict, decisions: Dict, factor: Dict, ref: str, dist: int) -> str:
    parts = []
    nav = portfolio.get("nav") if isinstance(portfolio, dict) else None
    if nav and nav.get("pct") is not None and abs(nav["pct"]) >= THRESHOLDS["nav_pct"]:
        sign = "+" if nav["pct"] > 0 else ""
        parts.append(f"NAV {sign}{nav['pct']:.2f}%")
    inv = portfolio.get("invested_pct") if isinstance(portfolio, dict) else None
    if inv and inv.get("delta") is not None and abs(inv["delta"]) >= THRESHOLDS["invested_pct"]:
        sign = "+" if inv["delta"] > 0 else ""
        parts.append(f"invested {sign}{inv['delta']:.1f}pp")
    npos = portfolio.get("n_positions") if isinstance(portfolio, dict) else None
    if npos and npos.get("delta"):
        sign = "+" if npos["delta"] > 0 else ""
        parts.append(f"positions {sign}{npos['delta']}")
    reg = portfolio.get("regime") if isinstance(portfolio, dict) else None
    if reg and reg.get("changed"):
        parts.append(f"regime {reg['ref']} -> {reg['today']}")
    nb = len(decisions.get("new_buys", []))
    ns = len(decisions.get("new_sells", []))
    if nb or ns:
        bits = []
        if nb: bits.append(f"{nb} BUY")
        if ns: bits.append(f"{ns} SELL")
        parts.append(" / ".join(bits))
    cs = decisions.get("conviction_shifts", [])
    if cs:
        top = cs[0]
        sign = "+" if top["delta"] > 0 else ""
        parts.append(f"conviction {top['ticker']} {sign}{top['delta']:.1f}")
    fc = factor.get("changed", []) if isinstance(factor, dict) else []
    if fc:
        parts.append(f"{len(fc)} factor shift(s)")
    if not parts:
        return f"Aucun changement materiel vs {ref} (J-{dist})."
    return ", ".join(parts) + f" (vs J-{dist})"


# ---------------------------------------------------------------------------
# Rendu Markdown
# ---------------------------------------------------------------------------

def render_diff_markdown(diff_j1: Dict, diff_j7: Dict) -> str:
    """Rendu markdown de la section 'Ce qui a change' pour le memo IC."""
    out = ["## Ce qui a change", ""]
    for diff in (diff_j1, diff_j7):
        label = diff.get("ref_label", "?")
        if diff.get("unavailable"):
            out.append(f"### vs {label}")
            out.append(f"*Indisponible : {diff.get('reason', 'cycle de reference introuvable')}*")
            out.append("")
            continue
        dist = diff.get("ref_distance_days")
        ref_cid = diff.get("ref_cycle_id", "?")
        header = f"### vs {label}"
        if dist is not None and label == "J-7" and dist != 7:
            header += f"  *(reel : J-{dist}, cycle `{ref_cid}`)*"
        else:
            header += f"  *(cycle `{ref_cid}`)*"
        out.append(header)
        out.append("")
        out.append(f"**Synthese :** {diff.get('summary_line', '')}")
        out.append("")
        out.extend(_render_portfolio(diff.get("portfolio", {})))
        out.extend(_render_decisions(diff.get("decisions", {})))
        out.extend(_render_factor(diff.get("factor_quality", {})))
        out.extend(_render_geo(diff.get("geo", {})))
        out.append("")
    return "\n".join(out)


def _render_portfolio(p: Dict) -> List[str]:
    if not p or p.get("unavailable"):
        return ["**Portfolio :** *indisponible*", ""]
    lines = ["**Portfolio**", ""]
    nav = p.get("nav")
    if nav and nav.get("pct") is not None and abs(nav["pct"]) >= THRESHOLDS["nav_pct"]:
        sign = "+" if nav["pct"] > 0 else ""
        lines.append(f"- NAV : {nav['ref']:,.0f} -> {nav['today']:,.0f} ({sign}{nav['pct']:.2f}%)")
    inv = p.get("invested_pct")
    if inv and inv.get("delta") is not None and abs(inv["delta"]) >= THRESHOLDS["invested_pct"]:
        sign = "+" if inv["delta"] > 0 else ""
        lines.append(f"- Invested : {inv['ref']:.2f}% -> {inv['today']:.2f}% ({sign}{inv['delta']:.2f} pp)")
    reg = p.get("regime", {})
    if reg.get("changed"):
        lines.append(f"- **Regime : {reg['ref']} -> {reg['today']}**")
    npos = p.get("n_positions")
    if npos and npos.get("delta"):
        sign = "+" if npos["delta"] > 0 else ""
        lines.append(f"- Positions : {npos['ref']} -> {npos['today']} ({sign}{npos['delta']})")
    if len(lines) == 2:
        lines.append("- *Pas de mouvement materiel*")
    lines.append("")
    return lines


def _render_decisions(d: Dict) -> List[str]:
    if not d:
        return []
    lines = ["**Decisions**", ""]
    nb = d.get("new_buys", [])
    ns = d.get("new_sells", [])
    rm = d.get("removed", [])
    cs = d.get("conviction_shifts", [])
    if nb:
        lines.append(f"- Nouveaux BUY ({len(nb)}) : " + ", ".join(
            f"{x['ticker']} ({x.get('qty_pct') or 0:.2f}%)" for x in nb[:6]
        ))
    if ns:
        lines.append(f"- Nouveaux SELL ({len(ns)}) : " + ", ".join(
            f"{x['ticker']} ({x.get('qty_pct') or 0:.2f}%)" for x in ns[:6]
        ))
    # rm intentionnellement masque - cf. note dans _diff_decisions
    if cs:
        lines.append(f"- Conviction shifts (top {min(5,len(cs))}) :")
        for x in cs[:5]:
            sign = "+" if x["delta"] > 0 else ""
            lines.append(f"  - {x['ticker']} : {x['from']:.1f} -> {x['to']:.1f} ({sign}{x['delta']:.1f})")
    if len(lines) == 2:
        lines.append("- *Aucune nouvelle decision*")
    lines.append("")
    return lines


def _render_factor(f: Dict) -> List[str]:
    if not f or f.get("unavailable"):
        return ["**Factor quality :** *indisponible*", ""]
    lines = ["**Factor quality**", ""]
    if f.get("changed"):
        for x in f["changed"][:8]:
            sign = "+" if x["delta"] > 0 else ""
            lines.append(f"- {x['factor']} : {x['from']} -> {x['to']} ({sign}{x['delta']:.3f})")
    if f.get("added"):
        lines.append(f"- Nouveaux : {', '.join(f['added'][:8])}")
    if f.get("removed"):
        lines.append(f"- Disparus : {', '.join(f['removed'][:8])}")
    if len(lines) == 2:
        lines.append("- *Pas de shift materiel*")
    lines.append("")
    return lines


def _render_geo(g: Dict) -> List[str]:
    if not g or g.get("unavailable"):
        return ["**Geo / sentiment :** *indisponible*", ""]
    lines = ["**Geo / sentiment**", ""]
    if g.get("sentiment_shifts"):
        for x in g["sentiment_shifts"][:6]:
            lines.append(f"- {x['region']} : {x['from']} -> {x['to']}")
    if g.get("added"):
        names = [x.get("region", "?") for x in g["added"][:6]]
        lines.append(f"- Nouvelles regions surveillees : {', '.join(names)}")
    if g.get("removed"):
        names = [x.get("region", "?") for x in g["removed"][:6]]
        lines.append(f"- Regions retirees : {', '.join(names)}")
    if len(lines) == 2:
        lines.append("- *Pas de changement de narrative*")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
    conn = sqlite3.connect(DB)
    # Dernier cycle
    cid = conn.execute("SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
    if not cid:
        print("No cycle in regime_log")
        sys.exit(1)
    cid = cid[0]
    print(f"Testing diff for latest cycle: {cid}")
    print("=" * 70)
    d1 = compute_cycle_diff(conn, cid, ref="J-1")
    d7 = compute_cycle_diff(conn, cid, ref="J-7")
    print(json.dumps(d1, indent=2, ensure_ascii=False, default=str))
    print()
    print(json.dumps(d7, indent=2, ensure_ascii=False, default=str))
    print()
    print("=" * 70)
    print("MARKDOWN RENDER")
    print("=" * 70)
    print(render_diff_markdown(d1, d7))
    conn.close()
