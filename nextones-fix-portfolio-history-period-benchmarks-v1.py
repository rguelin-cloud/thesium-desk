#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[PORTFOLIO_HISTORY_PERIOD_BENCHMARKS_V1]

Etend l'endpoint GET /api/portfolio/history avec :
  - query param 'period' : 30d | 6m | 1y | all   (default 30d)
  - query param 'benchmarks' : CSV de tickers (ex 'SPY,QQQ') -> series prices
  - reponse :
        {
          "period": "30d",
          "start_date": "2026-05-12",
          "end_date":   "2026-06-10",
          "portfolio": [{date, total_value, cash, total_pnl, perf_base100}, ...],
          "benchmarks": {
              "SPY": [{date, close, perf_base100}, ...],
              "QQQ": [{date, close, perf_base100}, ...]
          }
        }

Toutes les series sont normalisees base 100 au premier point commun du dataset.
Periode "all" = depuis MIN(date) de portfolio_history.

Patch chirurgical : remplace les lignes L490-L516 d'api_server.py par la
nouvelle definition. Backup, AST, py_compile, idempotent via marker.

ASCII pur, zero byte > 127.
"""
import ast
import os
import py_compile
import shutil
import sys
import time

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[PORTFOLIO_HISTORY_PERIOD_BENCHMARKS_V1]"

ANCHOR = (
    '@app.get("/api/portfolio/history")\n'
    'def get_portfolio_history():\n'
    '    """Last 30 days of portfolio value for the equity curve chart."""\n'
    '    conn = db()\n'
    '    try:\n'
    '        rows = conn.execute(\n'
    '            """SELECT date, total_value, cash, total_pnl\n'
    '               FROM portfolio_history\n'
    '               ORDER BY date DESC LIMIT 30"""\n'
    '        ).fetchall()\n'
    '        data = list(reversed([dict(r) for r in rows]))\n'
    '\n'
    '        # If no history, generate from portfolio_state\n'
    '        if not data:\n'
    '            ps = conn.execute("SELECT total_value FROM portfolio_state WHERE id = 1").fetchone()\n'
    '            total = ps["total_value"] if ps else 1_000_000\n'
    '            from datetime import date, timedelta\n'
    '            today = date.today()\n'
    '            data = [\n'
    '                {"date": (today - timedelta(days=i)).isoformat(),\n'
    '                 "total_value": total, "cash": total * 0.18, "total_pnl": 0}\n'
    '                for i in range(29, -1, -1)\n'
    '            ]\n'
    '\n'
    '        return {"history": data}\n'
    '    finally:\n'
    '        conn.close()\n'
)

REPLACEMENT = (
    '# [PORTFOLIO_HISTORY_PERIOD_BENCHMARKS_V1]\n'
    '@app.get("/api/portfolio/history")\n'
    'def get_portfolio_history(\n'
    '    period: str = Query("30d", description="30d | 6m | 1y | all"),\n'
    '    benchmarks: str = Query("", description="CSV tickers, ex SPY,QQQ"),\n'
    '):\n'
    '    """Equity curve + optional benchmarks, all normalized to base 100.\n'
    '\n'
    '    Backward compat: if no params, behaves like previous 30d call but\n'
    '    response now includes ``portfolio`` and ``benchmarks`` keys.\n'
    '    Legacy ``history`` key is preserved for old clients.\n'
    '    """\n'
    '    from datetime import date, timedelta\n'
    '    conn = db()\n'
    '    try:\n'
    '        # 1) Resolve start_date from period\n'
    '        today = date.today()\n'
    '        if period == "30d":\n'
    '            start_date = (today - timedelta(days=30)).isoformat()\n'
    '        elif period == "6m":\n'
    '            start_date = (today - timedelta(days=183)).isoformat()\n'
    '        elif period == "1y":\n'
    '            start_date = (today - timedelta(days=365)).isoformat()\n'
    '        elif period == "all":\n'
    '            row = conn.execute(\n'
    '                "SELECT MIN(date) AS d FROM portfolio_history"\n'
    '            ).fetchone()\n'
    '            start_date = (row["d"] if row and row["d"] else today.isoformat())\n'
    '        else:\n'
    '            start_date = (today - timedelta(days=30)).isoformat()\n'
    '\n'
    '        # 2) Fetch portfolio rows in window, oldest first\n'
    '        rows = conn.execute(\n'
    '            """SELECT date, total_value, cash, total_pnl\n'
    '               FROM portfolio_history\n'
    '               WHERE date >= ?\n'
    '               ORDER BY date ASC""",\n'
    '            (start_date,),\n'
    '        ).fetchall()\n'
    '        portfolio = [dict(r) for r in rows]\n'
    '\n'
    '        # Fallback : flat curve if nothing\n'
    '        if not portfolio:\n'
    '            ps = conn.execute(\n'
    '                "SELECT total_value FROM portfolio_state WHERE id = 1"\n'
    '            ).fetchone()\n'
    '            total = ps["total_value"] if ps else 1000000\n'
    '            portfolio = [\n'
    '                {\n'
    '                    "date": (today - timedelta(days=i)).isoformat(),\n'
    '                    "total_value": total,\n'
    '                    "cash": total * 0.18,\n'
    '                    "total_pnl": 0,\n'
    '                }\n'
    '                for i in range(29, -1, -1)\n'
    '            ]\n'
    '\n'
    '        # 3) Normalize portfolio to base 100\n'
    '        if portfolio:\n'
    '            base_pf = portfolio[0]["total_value"] or 1\n'
    '            for p in portfolio:\n'
    '                p["perf_base100"] = round(\n'
    '                    (p["total_value"] / base_pf) * 100.0, 4\n'
    '                )\n'
    '\n'
    '        # 4) Fetch benchmark series in same window, normalized base 100\n'
    '        bench_out = {}\n'
    '        if benchmarks:\n'
    '            tickers = [\n'
    '                t.strip().upper()\n'
    '                for t in benchmarks.split(",")\n'
    '                if t.strip()\n'
    '            ]\n'
    '            for tk in tickers:\n'
    '                bench_rows = conn.execute(\n'
    '                    """SELECT p.date, p.close\n'
    '                       FROM prices p\n'
    '                       JOIN instruments i ON i.id = p.instrument_id\n'
    '                       WHERE i.ticker = ? AND p.date >= ?\n'
    '                       ORDER BY p.date ASC""",\n'
    '                    (tk, start_date),\n'
    '                ).fetchall()\n'
    '                series = [dict(r) for r in bench_rows]\n'
    '                if series:\n'
    '                    base = series[0]["close"] or 1\n'
    '                    for s in series:\n'
    '                        s["perf_base100"] = round(\n'
    '                            (s["close"] / base) * 100.0, 4\n'
    '                        )\n'
    '                bench_out[tk] = series\n'
    '\n'
    '        end_date = portfolio[-1]["date"] if portfolio else today.isoformat()\n'
    '\n'
    '        return {\n'
    '            "period": period,\n'
    '            "start_date": start_date,\n'
    '            "end_date": end_date,\n'
    '            "portfolio": portfolio,\n'
    '            "benchmarks": bench_out,\n'
    '            # legacy compat for older UI code paths\n'
    '            "history": portfolio,\n'
    '        }\n'
    '    finally:\n'
    '        conn.close()\n'
)


def read_utf8_sig(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")


def write_utf8_no_bom(path, text):
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def main():
    if not os.path.isfile(TARGET):
        print("ERROR: target not found: " + TARGET)
        sys.exit(2)

    src = read_utf8_sig(TARGET)

    if MARKER in src:
        print("SKIP: marker already present")
        return

    count = src.count(ANCHOR)
    if count == 0:
        print("ERROR: anchor not found")
        # debug
        for needle in (
            '@app.get("/api/portfolio/history")',
            'def get_portfolio_history(',
            '"""Last 30 days of portfolio value for the equity curve chart."""',
        ):
            print("  " + needle[:60] + " : pos=" + str(src.find(needle)))
        sys.exit(3)
    if count > 1:
        print("ERROR: anchor not unique, " + str(count) + " matches")
        sys.exit(4)

    new_src = src.replace(ANCHOR, REPLACEMENT, 1)

    # Ensure Query is imported (it is used elsewhere in api_server.py, but
    # double-check)
    if "from fastapi" not in new_src or "Query" not in new_src:
        print("WARN: 'Query' might not be imported, please verify")
    # Note: existing endpoints already use Query (e.g. list_theses), so the
    # import is already in place.

    try:
        ast.parse(new_src, filename=TARGET)
    except SyntaxError as e:
        print("ERROR: ast.parse failed after patch")
        print(str(e))
        sys.exit(5)

    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("BACKUP: " + backup)

    write_utf8_no_bom(TARGET, new_src)
    print("WRITE OK: " + TARGET)

    try:
        py_compile.compile(TARGET, doraise=True)
        print("PY_COMPILE OK")
    except py_compile.PyCompileError as e:
        print("ERROR: py_compile failed, restoring backup")
        shutil.copy2(backup, TARGET)
        print(str(e))
        sys.exit(6)

    print("DONE " + MARKER)


if __name__ == "__main__":
    main()
