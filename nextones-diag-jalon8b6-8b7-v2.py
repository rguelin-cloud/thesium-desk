"""
DIAG Jalon 8B.6 + 8B.7 v2 - corrections schema
- regime_log SANS vix (utiliser market_regime_log)
- convergence_snapshots SANS drift_block (utiliser forced_exit + drift)
- Ajout : fenetre aveugle convergence (cycles AVANT premier snapshot)
"""
import sqlite3
import json
import os
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
RUN_ID = 15
PIVOT_DAY = "2026-05-29"
OVERLAP_START = "2026-05-25"
OVERLAP_END = "2026-06-12"
CRYPTO_TICKERS = ("BTC", "ETH", "SOL", "LINK", "AMZN", "GOOGL", "MSFT")

if not os.path.exists(DB):
    print("DB introuvable:", DB)
    sys.exit(1)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()


def safe_exec(sql, params=()):
    try:
        return cur.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        print("    [SQL ERR]", e)
        return []


print("=" * 78)
print("[8B.6-B v2] regime / market_regime autour du pivot day", PIVOT_DAY)
print("=" * 78)

# regime_log (sans vix)
print("\n  regime_log (cols disponibles) autour du pivot day :")
rows = safe_exec(
    "SELECT cycle_id, regime, invested_pct, nav, cash, n_positions, "
    "n_proposals_in, n_proposals_attenuated, equity_regime, crypto_regime, "
    "equity_buy_mult, equity_sell_mult, crypto_buy_mult, crypto_sell_mult, "
    "created_at "
    "FROM regime_log "
    "WHERE substr(cycle_id,1,8) BETWEEN ? AND ? "
    "ORDER BY cycle_id",
    ("20260525", "20260612"),
)
print("    n_rows=", len(rows))
for r in rows[:30]:
    print(
        "    {:20s} reg={:10s} inv={:6.2f}% nav=${:10,.0f} eq={} cr={} ebm={} ebs={} cbm={} csm={}".format(
            r["cycle_id"],
            (r["regime"] or "?")[:10],
            (r["invested_pct"] or 0),
            (r["nav"] or 0),
            (r["equity_regime"] or "?")[:6],
            (r["crypto_regime"] or "?")[:6],
            r["equity_buy_mult"],
            r["equity_sell_mult"],
            r["crypto_buy_mult"],
            r["crypto_sell_mult"],
        )
    )

# market_regime_log (vix + drawdown + score)
print("\n  market_regime_log (avec vix/drawdown) autour du pivot day :")
rows = safe_exec(
    "SELECT cycle_id, asset_class, regime, vix_value, realized_vol_pct, "
    "drawdown_5d_pct, score, buy_mult, sell_mult, convergence_thresh, created_at "
    "FROM market_regime_log "
    "WHERE substr(cycle_id,1,8) BETWEEN ? AND ? "
    "ORDER BY cycle_id, asset_class",
    ("20260525", "20260612"),
)
print("    n_rows=", len(rows))
for r in rows[:60]:
    print(
        "    {:20s} {:8s} {:8s} vix={:5.2f} dd5d={:5.2f}% sc={} bm={} sm={} ct={}".format(
            r["cycle_id"],
            (r["asset_class"] or "?")[:8],
            (r["regime"] or "?")[:8],
            (r["vix_value"] or 0),
            (r["drawdown_5d_pct"] or 0),
            r["score"],
            r["buy_mult"],
            r["sell_mult"],
            r["convergence_thresh"],
        )
    )

print()
print("=" * 78)
print("[8B.6-C v2] convergence_snapshots prod - vraie distribution")
print("=" * 78)

# Premier et dernier snapshot par jour
print("\n  Distribution n_snapshots par jour (depuis debut) :")
rows = safe_exec(
    "SELECT substr(cycle_id,1,8) day_t, COUNT(*) n, "
    "SUM(forced_exit) n_fe, "
    "AVG(convergence_pct) avg_conv "
    "FROM convergence_snapshots "
    "GROUP BY substr(cycle_id,1,8) "
    "ORDER BY day_t"
)
print("    day      | n_snapshots | n_forced_exit | avg_convergence_pct")
print("    " + "-" * 70)
for r in rows:
    print(
        "    {} |     {:5d}   |     {:5d}     |    {:5.3f}".format(
            r["day_t"], r["n"], r["n_fe"] or 0, r["avg_conv"] or 0
        )
    )

# Forced exit detail sur tickers crypto
print("\n  forced_exit/drift par ticker (overlap + extension):")
rows = safe_exec(
    "SELECT cycle_id, ticker, direction_consensus, convergence_pct, "
    "sizing_multiplier, forced_exit, drift, is_crypto, n_aligned, n_present "
    "FROM convergence_snapshots "
    "WHERE ticker IN ({}) "
    "ORDER BY cycle_id, ticker".format(",".join("?" * len(CRYPTO_TICKERS))),
    CRYPTO_TICKERS,
)
print("    n_rows=", len(rows))
print(
    "    cycle_id              tkr   dir    conv  mult fe dr crypto n_al/n_pr"
)
for r in rows[:80]:
    print(
        "    {:21s} {:5s} {:5s} {:5.2f}  {:4.2f}  {} {}    {}    {}/{}".format(
            r["cycle_id"],
            r["ticker"],
            (r["direction_consensus"] or "?")[:5],
            r["convergence_pct"] or 0,
            r["sizing_multiplier"] or 0,
            r["forced_exit"],
            r["drift"],
            r["is_crypto"],
            r["n_aligned"],
            r["n_present"],
        )
    )

print()
print("=" * 78)
print("[8B.7 v2] Fenetre aveugle convergence - quels orders prod non filtres")
print("=" * 78)

# Premier cycle avec convergence
first_conv = safe_exec(
    "SELECT MIN(cycle_id) c FROM convergence_snapshots"
)
first_conv_cycle = first_conv[0]["c"] if first_conv else None
print("  Premier cycle convergence : ", first_conv_cycle)

# Orders prod AVANT le premier snapshot conv (dans overlap)
print(
    "\n  Orders prod overlap AVANT debut convergence "
    "(2026-05-25 -> 2026-06-08 inclus) :"
)
rows = safe_exec(
    "SELECT i.ticker, o.side, COUNT(*) n, SUM(o.quantity) qty_tot, "
    "SUM(CASE WHEN o.status='filled' THEN 1 ELSE 0 END) n_filled "
    "FROM orders o "
    "JOIN instruments i ON i.id = o.instrument_id "
    "WHERE substr(o.cycle_id,1,8) BETWEEN '20260525' AND '20260608' "
    "GROUP BY i.ticker, o.side "
    "ORDER BY n DESC"
)
print("    n_groups=", len(rows))
for r in rows[:40]:
    print(
        "    {:6s} {:4s} n={:3d} qty_tot={:10.2f} filled={}".format(
            r["ticker"], r["side"], r["n"], r["qty_tot"] or 0, r["n_filled"]
        )
    )

# Notional pendant la fenetre aveugle
print("\n  Notional fills prod pendant la fenetre aveugle (avant 2026-06-09) :")
rows = safe_exec(
    "SELECT substr(f.filled_at,1,10) day_t, i.ticker, o.side, "
    "SUM(f.fill_price * f.fill_quantity) notional "
    "FROM fills f "
    "JOIN orders o ON o.id = f.order_id "
    "JOIN instruments i ON i.id = o.instrument_id "
    "WHERE substr(f.filled_at,1,10) BETWEEN '2026-05-25' AND '2026-06-08' "
    "GROUP BY day_t, i.ticker, o.side "
    "HAVING notional > 5000 "
    "ORDER BY notional DESC"
)
print("    " + "-" * 60)
total_blind = 0.0
for r in rows[:40]:
    n = r["notional"] or 0
    total_blind += n
    print(
        "    {} {:6s} {:4s} ${:12,.2f}".format(r["day_t"], r["ticker"], r["side"], n)
    )
print("    TOTAL fenetre aveugle (>$5k items) = ${:,.2f}".format(total_blind))

print()
print("=" * 78)
print("[8B.7 v2] Convergence snapshots APRES debut sur crypto tickers")
print("=" * 78)

# Que dit convergence pour BTC/ETH/SOL/LINK dans la fenetre 2026-06-09 -> now ?
rows = safe_exec(
    "SELECT substr(cycle_id,1,8) day_t, ticker, "
    "AVG(convergence_pct) avg_conv, "
    "SUM(forced_exit) n_fe, "
    "AVG(sizing_multiplier) avg_mult, "
    "COUNT(*) n "
    "FROM convergence_snapshots "
    "WHERE ticker IN ('BTC','ETH','SOL','LINK') "
    "GROUP BY substr(cycle_id,1,8), ticker "
    "ORDER BY day_t, ticker"
)
print("  day      | tkr  | n  | avg_conv | n_fe | avg_mult")
for r in rows[:60]:
    print(
        "  {} | {:4s} | {:2d} |  {:5.2f}   | {:3d}  |  {:4.2f}".format(
            r["day_t"], r["ticker"], r["n"], r["avg_conv"] or 0, r["n_fe"] or 0,
            r["avg_mult"] or 0
        )
    )

# Distribution forced_exit globale
print("\n  Distribution forced_exit globale convergence_snapshots :")
rows = safe_exec(
    "SELECT forced_exit, COUNT(*) n FROM convergence_snapshots GROUP BY forced_exit"
)
for r in rows:
    print("    forced_exit={} n={}".format(r["forced_exit"], r["n"]))

print()
print("=" * 78)
print("[8B.7 v2] portfolio_targets actifs sur pivot day vs aujourd hui")
print("=" * 78)
rows = safe_exec(
    "SELECT snapshot_id, COUNT(*) n, AVG(target_weight_pct) avg_w, "
    "MAX(target_weight_pct) max_w, "
    "GROUP_CONCAT(ticker, ',') tickers "
    "FROM portfolio_targets "
    "WHERE active=1 "
    "GROUP BY snapshot_id "
    "ORDER BY snapshot_id"
)
for r in rows[:5]:
    tks = (r["tickers"] or "")[:120]
    print(
        "    snap={} n={} avg_w={:.2f}% max_w={:.2f}%\n      tickers={}".format(
            r["snapshot_id"], r["n"], r["avg_w"] or 0, r["max_w"] or 0, tks
        )
    )

print()
print("=" * 78)
print("[8B.7 v2] Verifier patch risk_v2_dblock applique a quelle date")
print("=" * 78)
rows = safe_exec(
    "SELECT id, substr(created_at,1,10) day_t, "
    "json_extract(risk_check_result,'$.warnings[0].message') w_msg, "
    "COUNT(*) OVER (PARTITION BY substr(created_at,1,10)) n_day "
    "FROM orders "
    "WHERE created_at IS NOT NULL "
    "ORDER BY id DESC "
    "LIMIT 30"
)
print("  Sample 30 derniers orders : si w_msg='database is locked' => risk v2 silently broken")
print("  id    | day        | warning_msg                                | n_orders_day")
for r in rows:
    wm = (r["w_msg"] or "")[:40]
    print("  {:5d} | {} | {:42s} | {}".format(r["id"], r["day_t"], wm, r["n_day"]))

# Distribution par jour des risk_v2_error
print("\n  Distribution risk_v2 'database is locked' par jour :")
rows = safe_exec(
    "SELECT substr(created_at,1,10) day_t, "
    "SUM(CASE WHEN risk_check_result LIKE '%risk_v2_error%' THEN 1 ELSE 0 END) n_v2_err, "
    "COUNT(*) n_tot "
    "FROM orders "
    "GROUP BY substr(created_at,1,10) "
    "ORDER BY day_t"
)
print("  day        | n_orders | n_risk_v2_err | pct")
for r in rows:
    pct = (100 * (r["n_v2_err"] or 0) / r["n_tot"]) if r["n_tot"] else 0
    print(
        "  {} |    {:4d}   |     {:4d}     | {:5.1f}%".format(
            r["day_t"], r["n_tot"], r["n_v2_err"] or 0, pct
        )
    )

print()
print("=" * 78)
print("DONE - 8B.6/8B.7 v2 analyse fenetre aveugle convergence")
print("=" * 78)

con.close()
