# -*- coding: utf-8 -*-
"""
Trouve les 2 occurrences de 'article complet' dans app.js avec contexte
ET trouve les 3 occurrences de MutationObserver pour identifier le
MutationObserver geopolitique qui injecte du texte brut.
"""
from pathlib import Path

APP_JS = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js")
src = APP_JS.read_text(encoding="utf-8-sig")

print("=" * 90)
print("Occurrences 'article complet'")
print("=" * 90)

pos = 0
n = 0
while True:
    idx = src.find("article complet", pos)
    if idx == -1:
        break
    n += 1
    lineno = src[:idx].count("\n") + 1
    start = max(0, idx - 400)
    end = min(len(src), idx + 200)
    print(f"\n--- OCCURRENCE #{n} position {idx} (ligne ~{lineno}) ---")
    print(src[start:end])
    print(f"--- fin #{n} ---")
    pos = idx + 1

print(f"\n{'=' * 90}")
print("Occurrences 'MutationObserver'")
print("=" * 90)

pos = 0
n = 0
while True:
    idx = src.find("MutationObserver", pos)
    if idx == -1:
        break
    n += 1
    lineno = src[:idx].count("\n") + 1
    start = max(0, idx - 200)
    end = min(len(src), idx + 600)
    print(f"\n--- MUTATIONOBSERVER #{n} position {idx} (ligne ~{lineno}) ---")
    print(src[start:end])
    print(f"--- fin #{n} ---")
    pos = idx + 1

print(f"\n{'=' * 90}")
print("Marqueurs [PPLX_GEO_DETAIL_V1]")
print("=" * 90)
pos = 0
n = 0
while True:
    idx = src.find("[PPLX_GEO_DETAIL_V1]", pos)
    if idx == -1:
        break
    n += 1
    lineno = src[:idx].count("\n") + 1
    start = max(0, idx - 200)
    end = min(len(src), idx + 600)
    print(f"\n--- [PPLX_GEO_DETAIL_V1] #{n} position {idx} (ligne ~{lineno}) ---")
    print(src[start:end])
    print(f"--- fin #{n} ---")
    pos = idx + 1
