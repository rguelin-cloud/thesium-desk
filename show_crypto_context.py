# Affiche le contenu de crypto_context (1 ligne par symbole).
import sqlite3, json, time
from pathlib import Path

DB = Path(__file__).resolve().parent / "thesium.db"
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM crypto_context ORDER BY symbol").fetchall()
if not rows:
    print("Table crypto_context vide. Lance: py -3.13 pplx_crypto_agent.py")
else:
    now = int(time.time())
    for r in rows:
        age_h = (now - r["ts"]) / 3600
        narr = json.loads(r["current_narratives"]) if r["current_narratives"] else []
        cit = json.loads(r["citations"]) if r["citations"] else []
        print(f"\n=== {r['symbol']} ({r['model']}, age={age_h:.1f}h) ===")
        print(f"  Score narratif   : {r['narrative_score']}/100")
        print(f"  Sentiment social : {r['social_sentiment']}")
        print(f"  Narratifs        : {', '.join(narr[:3])}")
        print(f"  Sources          : {len(cit)} URLs")
        print(f"  These trading    : {r['thesis_short'][:200]}")
conn.close()
