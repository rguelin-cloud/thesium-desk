# -*- coding: utf-8 -*-
"""
Diag mojibake v2 : cible specifiquement les drivers ExitAgent
contenant ≤ et → (en bytes UTF-8 vs cp1252-encoded-as-utf-8).
"""
import os, sys, io, sqlite3, json, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Cycle le plus recent
print("=" * 60); print("1. CYCLE RECENT"); print("=" * 60)
cur.execute("SELECT cycle_id, COUNT(*) c FROM convergence_snapshots GROUP BY cycle_id ORDER BY MAX(rowid) DESC LIMIT 5")
for r in cur.fetchall():
    print(f"  cycle_id={r['cycle_id']}  n={r['c']}")

# 2. Lire les tickers forced_exit du dernier cycle
print("\n" + "=" * 60); print("2. DRIVERS FORCED_EXIT - cycle le plus recent"); print("=" * 60)
cur.execute("SELECT cycle_id FROM convergence_snapshots ORDER BY rowid DESC LIMIT 1")
last_cycle = cur.fetchone()["cycle_id"]
print(f"  cycle: {last_cycle}")

cur.execute("""
    SELECT ticker, forced_exit, drift, buckets_json
    FROM convergence_snapshots
    WHERE cycle_id = ? AND (forced_exit = 1 OR drift = 1)
    ORDER BY ticker
""", (last_cycle,))

rows = cur.fetchall()
print(f"  {len(rows)} ligne(s) forced_exit/drift")

mojibake_in_db = 0
clean_in_db = 0
samples = []

for row in rows:
    buckets_raw = row["buckets_json"]
    if not buckets_raw:
        continue
    try:
        buckets = json.loads(buckets_raw)
    except Exception as e:
        print(f"  [ERR] {row['ticker']} json.loads: {e}")
        continue

    # Cherche un driver L5 (ExitAgent)
    for level, b in buckets.items():
        if not isinstance(b, dict):
            continue
        drv = b.get("driver")
        if not drv:
            continue
        # Patterns mojibake
        has_moji = any(p in drv for p in ("â‰¤", "â†'", "â†™", "â†’", "Ã©", "â‰¥"))
        has_clean = any(p in drv for p in ("≤", "→", "≥"))
        tag = "MOJIBAKE" if has_moji else ("CLEAN_UNICODE" if has_clean else "ASCII")
        if has_moji:
            mojibake_in_db += 1
        elif has_clean:
            clean_in_db += 1
        samples.append((row["ticker"], level, tag, drv[:120]))

print(f"\n  Totaux : mojibake={mojibake_in_db}, clean_unicode={clean_in_db}")
print("\n  Echantillons :")
for t, lv, tag, d in samples[:20]:
    print(f"    [{tag}] {t:6s} {lv}: {d}")

# 3. Pour le ticker AMD, dump les bytes RAW du buckets_json
print("\n" + "=" * 60); print("3. BYTES BRUTS DE AMD"); print("=" * 60)
cur.execute("SELECT buckets_json FROM convergence_snapshots WHERE cycle_id=? AND ticker='AMD'", (last_cycle,))
r = cur.fetchone()
if r:
    raw = r["buckets_json"]
    print(f"  type str, len={len(raw)}")
    # Encode en bytes pour voir
    b_utf8 = raw.encode("utf-8")
    print(f"  UTF-8 bytes len = {len(b_utf8)}")
    # Chercher les patterns
    patterns = {
        b"\xe2\x89\xa4": "≤ (vrai utf-8)",
        b"\xe2\x86\x92": "→ (vrai utf-8)",
        b"\xc3\xa2\xe2\x80\xb0\xc2\xa4": "â‰¤ (mojibake double-encoded)",
        b"\xc3\xa2\xe2\x80\xa0\xe2\x80\x99": "â†'  (mojibake double-encoded)",
        b"\xc3\xa2\xe2\x80\xa0\xe2\x86\x92": "â†→ (autre mojibake)",
    }
    for pat, name in patterns.items():
        cnt = b_utf8.count(pat)
        if cnt:
            print(f"  pattern {name!r} x{cnt}")
            idx = b_utf8.find(pat)
            ctx = b_utf8[max(0, idx-30):idx+len(pat)+30]
            print(f"    ctx : {ctx!r}")

# 4. Test reverse : tenter la conversion cp1252 -> utf-8
print("\n" + "=" * 60); print("4. TEST REVERSE encode('cp1252').decode('utf-8')"); print("=" * 60)
if r:
    raw = r["buckets_json"]
    try:
        fixed = raw.encode("cp1252", errors="replace").decode("utf-8", errors="replace")
        # Compare
        moji_before = sum(raw.count(p) for p in ("â‰¤", "â†'", "â†™", "â†’"))
        moji_after = sum(fixed.count(p) for p in ("â‰¤", "â†'", "â†™", "â†’"))
        clean_after = sum(fixed.count(p) for p in ("≤", "→", "≥"))
        print(f"  AVANT : mojibake x{moji_before}")
        print(f"  APRES encode('cp1252').decode('utf-8') : mojibake x{moji_after}, clean x{clean_after}")
        # Echantillon
        try:
            buckets_fixed = json.loads(fixed)
            for lv, b in buckets_fixed.items():
                if isinstance(b, dict) and b.get("driver"):
                    print(f"    {lv} driver FIXED : {b['driver'][:120]}")
                    break
        except Exception as e:
            print(f"    [json.loads APRES] {e}")
    except Exception as e:
        print(f"  [ERR] {e}")

# 5. Code de l'insertion : convergence_engine.py L629
print("\n" + "=" * 60); print("5. CODE INSERTION convergence_engine.py L629"); print("=" * 60)
ce_path = os.path.join(BASE, "convergence_engine.py")
with open(ce_path, "r", encoding="utf-8-sig") as f:
    ce_src = f.read()
ce_lines = ce_src.split("\n")
# Dump lignes 620-680 pour voir le SQL et le serializer
for i in range(615, min(685, len(ce_lines))):
    print(f"  {i+1:4d}| {ce_lines[i]}")

# 6. Origine des drivers - cherche dans exit_agent / ExitAgent
print("\n" + "=" * 60); print("6. SOURCE DRIVERS - exit_agent"); print("=" * 60)
for fn in ("exit_agent.py", "agents.py", "execution_engine.py"):
    fp = os.path.join(BASE, fn)
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8-sig") as f:
        src = f.read()
    # Cherche les f-strings contenant ≤ ou → (vrais ou mojibake)
    for needle in ("≤", "→", "â‰¤", "â†'", "â†™", "â‰¥", "seuil"):
        for m in re.finditer(re.escape(needle), src):
            line_num = src[:m.start()].count("\n") + 1
            line = ce_lines[0] if False else src.split("\n")[line_num - 1]
            print(f"  {fn}:L{line_num} pattern '{needle}' : {line.strip()[:140]}")
            break  # 1 echantillon par needle/fichier

conn.close()
print("\n[DONE]")
