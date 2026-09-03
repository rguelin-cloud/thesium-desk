import sqlite3, json, collections

c = sqlite3.connect("thesium.db")
c.row_factory = sqlite3.Row

print("=" * 78)
print("1. MOTIFS DE REJET")
print("=" * 78)
for r in c.execute("""
    SELECT COALESCE(rejection_reason,'(null)') AS reason, COUNT(*) n
    FROM orders WHERE status='rejected'
    GROUP BY reason ORDER BY n DESC
"""):
    print(f"{r['n']:5d}  {r['reason'][:95]}")

print()
print("=" * 78)
print("2. CLES DU RISK CHECK")
print("=" * 78)
keys = collections.Counter()
fails = collections.Counter()
for r in c.execute("""
    SELECT risk_check_result FROM orders
    WHERE status='rejected' AND risk_check_result IS NOT NULL
"""):
    try:
        d = json.loads(r[0])
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    for k, v in d.items():
        keys[k] += 1
        if v is False or (isinstance(v, str) and "fail" in v.lower()):
            fails[k] += 1
for k, n in keys.most_common(25):
    print(f"{n:5d}  {k:38s} fails={fails[k]}")

print()
print("=" * 78)
print("3. ECHANTILLONS")
print("=" * 78)
for r in c.execute("""
    SELECT id, rejection_reason, risk_check_result FROM orders
    WHERE status='rejected' AND risk_check_result IS NOT NULL LIMIT 3
"""):
    print(f"--- order {r[0]} | {r[1]} ---")
    print(str(r[2])[:600])
    print()

print("=" * 78)
print("4. EVOLUTION MENSUELLE")
print("=" * 78)
for r in c.execute("""
    SELECT substr(created_at,1,7) m,
           SUM(status='rejected') rej,
           SUM(status='filled') fil,
           SUM(status='cancelled') can,
           COUNT(*) tot
    FROM orders GROUP BY m ORDER BY m
"""):
    pct = 100.0*r['rej']/r['tot'] if r['tot'] else 0
    print(f"{r['m']}  rejetes {r['rej']:3d}  executes {r['fil']:3d}  "
          f"annules {r['can']:3d}  total {r['tot']:3d}  -> {pct:5.1f}% rejet")

print()
print("=" * 78)
print("5. REJETS PAR TICKER")
print("=" * 78)
for r in c.execute("""
    SELECT i.ticker, o.side,
           SUM(o.status='rejected') rej, COUNT(*) tot
    FROM orders o JOIN instruments i ON i.id = o.instrument_id
    GROUP BY i.ticker, o.side
    HAVING rej > 0 ORDER BY rej DESC LIMIT 20
"""):
    pct = 100.0*r['rej']/r['tot'] if r['tot'] else 0
    print(f"{r['ticker']:8s} {r['side']:5s}  {r['rej']:3d}/{r['tot']:3d}  {pct:5.1f}%")

c.close()
