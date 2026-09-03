# -*- coding: utf-8 -*-
"""
Localise le code du scheduler price refresh
qui declenche le 'database is locked' pendant un cycle.
"""
import os, sys, io, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Logs reference :
# [scheduler] Refreshing prices...
# [scheduler] Price refresh error: database is locked
# [scheduler] Refreshing CoinGecko crypto prices...
# [scheduler] Refreshing Perplexity crypto contexts...

# 1. Cherche qui imprime '[scheduler]'
print("=" * 70); print("1. SOURCES de '[scheduler]' logs"); print("=" * 70)
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if not d.startswith("_backups") and d not in (".venv", "venv", "__pycache__", ".git")]
    for f in files:
        if not f.endswith(".py") or f.startswith("nextones-"):
            continue
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8-sig") as fh:
                src = fh.read()
        except Exception:
            continue
        if "[scheduler]" not in src:
            continue
        rel = os.path.relpath(fp, BASE)
        lines = src.split("\n")
        for i, line in enumerate(lines, 1):
            if "[scheduler]" in line and ("Refreshing" in line or "refresh error" in line or "crypto" in line.lower()):
                print(f"  {rel}:L{i}  {line.strip()[:140]}")

# 2. Cherche les fonctions cron : APScheduler / threading.Timer / asyncio.create_task
print("\n" + "=" * 70); print("2. CRON / SCHEDULER REGISTRATIONS"); print("=" * 70)
patterns = [
    r"@scheduler\.",
    r"add_job\(",
    r"BackgroundScheduler",
    r"scheduler\.start\(",
    r"refresh_prices",
    r"refresh_crypto",
    r"refresh_pplx",
]
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if not d.startswith("_backups") and d not in (".venv", "venv", "__pycache__", ".git")]
    for f in files:
        if not f.endswith(".py") or f.startswith("nextones-"):
            continue
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8-sig") as fh:
                src = fh.read()
        except Exception:
            continue
        lines = src.split("\n")
        for pat in patterns:
            for m in re.finditer(pat, src):
                line_num = src[:m.start()].count("\n") + 1
                line = lines[line_num - 1].strip()
                if line.startswith("#"):
                    continue
                rel = os.path.relpath(fp, BASE)
                print(f"  {rel}:L{line_num} [{pat[:25]}] {line[:140]}")

# 3. Cherche data_ingestion / fetch_yahoo_prices / refresh callsites
print("\n" + "=" * 70); print("3. FONCTIONS REFRESH PRICES"); print("=" * 70)
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if not d.startswith("_backups") and d not in (".venv", "venv", "__pycache__", ".git")]
    for f in files:
        if not f.endswith(".py") or f.startswith("nextones-"):
            continue
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8-sig") as fh:
                src = fh.read()
        except Exception:
            continue
        lines = src.split("\n")
        for m in re.finditer(r'^(\s*)(?:async\s+)?def\s+(\w*refresh\w*|\w*update_prices\w*|fetch_yahoo_prices|fetch_crypto_prices)\s*\(', src, re.MULTILINE):
            line_num = src[:m.start()].count("\n") + 1
            rel = os.path.relpath(fp, BASE)
            # Skip si script utility nextones-/_check_/_diag_ etc
            if rel.startswith("_") or rel.startswith("nextones-"):
                continue
            # Skip _backups
            if "_backup" in rel:
                continue
            print(f"  {rel}:L{line_num}  def {m.group(2)}()")

print("\n[DONE]")
