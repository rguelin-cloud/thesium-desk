# -*- coding: utf-8 -*-
# nextones-diag-find-missing-agents-v1.py
# Trouve : micro_agent, exit_driver, agents factor/momentum/vol reels
# + dump bref de detect_market_regime + apply_convergence_sizing

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"


def find_py_files():
    out = []
    for root, dirs, files in os.walk(ROOT):
        # skip caches/venv
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "venv", ".venv", "node_modules", "dist")]
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return out


def search(patterns, label):
    print(f"\n--- {label} ---")
    files = find_py_files()
    found = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8-sig", errors="replace") as fp:
                src = fp.read()
        except Exception:
            continue
        for pat in patterns:
            if re.search(pat, src):
                found.append((f, pat))
                break
    if not found:
        print("  (aucun match)")
    for f, p in found:
        rel = os.path.relpath(f, ROOT)
        print(f"  {rel}  (pattern: {p})")
    return found


def main():
    print("=" * 80)
    print("FIND MISSING AGENTS + dump fonctions clees")
    print("=" * 80)

    # 1. micro_agent
    search(
        [r"\bmicro_agent\b", r"def\s+run_micro", r"micro_score", r"microstructure"],
        "MICRO AGENT - patterns micro/microstructure",
    )

    # 2. exit_driver
    search(
        [r"\bexit_driver\b", r"def\s+run_exit", r"exit_signals", r"\bforced_exit\b"],
        "EXIT DRIVER - patterns exit/forced_exit",
    )

    # 3. factor quant reel (momentum / vol / quality scores)
    search(
        [r"def\s+compute_momentum", r"def\s+factor_score", r"def\s+compute_vol(?!_penalty)", r"def\s+quality_score"],
        "FACTOR QUANT - momentum/vol/quality (hors pplx)",
    )

    # 4. crypto quant reel (hors PPLX)
    search(
        [r"def\s+score_crypto", r"def\s+crypto_quant", r"crypto_momentum"],
        "CRYPTO QUANT - hors pplx",
    )

    # 5. Dump detect_market_regime signature + corps premier
    print("\n" + "=" * 80)
    print("DUMP detect_market_regime (premier bloc 30 lignes)")
    print("=" * 80)
    p = os.path.join(ROOT, "market_regime_v1.py")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.readlines()
        for i, ln in enumerate(lines):
            if "def detect_market_regime" in ln:
                for j in range(i, min(i + 30, len(lines))):
                    print(f"  {j+1:4d}| {lines[j].rstrip()}")
                break

    # 6. Dump apply_convergence_sizing
    print("\n" + "=" * 80)
    print("DUMP apply_convergence_sizing (premier bloc 20 lignes)")
    print("=" * 80)
    p = os.path.join(ROOT, "portfolio_construction_agent.py")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.readlines()
        for i, ln in enumerate(lines):
            if "def apply_convergence_sizing" in ln:
                for j in range(i, min(i + 20, len(lines))):
                    print(f"  {j+1:4d}| {lines[j].rstrip()}")
                break

    # 7. Liste des "def " toplevel dans portfolio_construction_agent
    print("\n" + "=" * 80)
    print("ALL defs dans portfolio_construction_agent.py (top-level)")
    print("=" * 80)
    p = os.path.join(ROOT, "portfolio_construction_agent.py")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            src = f.read()
        defs = re.findall(r"^def\s+(\w+)\s*\(", src, re.MULTILINE)
        for d in defs:
            print(f"  {d}")

    # 8. Liste des def dans risk_pretrade.py
    print("\n" + "=" * 80)
    print("ALL defs dans risk_pretrade.py")
    print("=" * 80)
    p = os.path.join(ROOT, "risk_pretrade.py")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            src = f.read()
        defs = re.findall(r"^def\s+(\w+)\s*\(", src, re.MULTILINE)
        for d in defs:
            print(f"  {d}")


if __name__ == "__main__":
    main()
