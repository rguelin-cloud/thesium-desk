"""Pourquoi 100% rejected ? Verifier close_dec et open_after pour quelques tickers."""
import os
os.environ["NEXTONES_REPLAY_MODE"] = "1"
from replay_adapters import MarketDataAdapter

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
adapter = MarketDataAdapter(db_path=DB)

DAYS = ["2026-06-12", "2026-06-11", "2026-06-10", "2026-06-09", "2026-06-08", "2026-05-29"]
TICKERS = ["BTC", "ETH", "AAPL", "GOOGL", "SOL", "AMZN"]

print(f"{'day':12s} {'ticker':8s} {'close_at':12s} {'open_after_date':16s} {'open_after_price':12s}")
for day in DAYS:
    for t in TICKERS:
        close = adapter.get_close_at(day, t)
        bar = adapter.get_open_after(day, t)
        close_s = f"{close:.2f}" if close else "None"
        if bar:
            bar_d = bar.get("date","?")
            bar_o = f"{bar.get('open'):.2f}" if bar.get("open") else "None"
        else:
            bar_d, bar_o = "None","None"
        print(f"  {day:10s} {t:8s} {close_s:12s} {bar_d:16s} {bar_o:12s}")
    print()
