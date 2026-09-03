"""
agents_factor_patch.py
=======================
Script de patch ciblé pour la classe FactorAgent dans agents.py.
Applique 3 corrections :
  1. quality_score robuste (fonction logistique au lieu de linéaire cassée)
  2. Pondération momentum renforcée (60% au lieu de 50%)
  3. Seuils overweight/underweight ramenés à 6 / 4 au lieu de 7 / 3

Sauvegarde l'ancien agents.py avant modification.
"""
import os
import re
import shutil
import sys
from datetime import datetime

AGENTS_PATH = "agents.py"

OLD_BLOCK = '''            # Quality proxy: lower volatility = higher quality score (0-10)
            quality_score = max(0, min(10, 10 - vol_20 * 20))

            # Momentum score (0-10)
            # Map -30% to +30% range to 0-10
            momentum_score = max(0, min(10, (momentum + 30) / 6))

            # Combined factor score
            combined = momentum_score * 0.5 + quality_score * 0.3 + (10 - rsi / 10) * 0.2

            # Conviction based on how extreme the combined score is
            extreme = abs(combined - 5)
            conviction = min(9, 4 + extreme)

            if combined >= 7:
                tilt = "overweight"
                proposed = f"Increase {inst['ticker']} allocation by 2-3%; factor composite score {combined:.1f}/10"
            elif combined <= 3:
                tilt = "underweight"
                proposed = f"Reduce {inst['ticker']} allocation by 2-3%; factor composite score {combined:.1f}/10"
            else:
                tilt = "neutral"
                proposed = f"Maintain current {inst['ticker']} allocation; no factor edge"'''

NEW_BLOCK = '''            # Quality proxy: lower volatility = higher quality score (0-10)
            # PATCH 2026-05-22 : formule logistique robuste, calibrée pour
            # rester sensible jusqu'à vol annuelle de 100%
            # vol_20 < 0.15 (faible vol) → score ~10
            # vol_20 = 0.30 (vol normale) → score ~5
            # vol_20 > 0.60 (forte vol) → score ~0
            quality_score = 10 / (1 + math.exp((vol_20 - 0.30) * 12))

            # Momentum score (0-10)
            # Map -30% to +30% range to 0-10
            momentum_score = max(0, min(10, (momentum + 30) / 6))

            # Combined factor score
            # PATCH : momentum 60% (au lieu de 50%) pour booster sensibilité signal
            combined = momentum_score * 0.6 + quality_score * 0.25 + (10 - rsi / 10) * 0.15

            # Conviction based on how extreme the combined score is
            extreme = abs(combined - 5)
            conviction = min(9, 4 + extreme)

            # PATCH : seuils ramenés à 6/4 (au lieu de 7/3) pour générer
            # des thèses actionnables sur marché normal
            if combined >= 6:
                tilt = "overweight"
                proposed = f"Increase {inst['ticker']} allocation by 2-3%; factor composite score {combined:.1f}/10"
            elif combined <= 4:
                tilt = "underweight"
                proposed = f"Reduce {inst['ticker']} allocation by 2-3%; factor composite score {combined:.1f}/10"
            else:
                tilt = "neutral"
                proposed = f"Maintain current {inst['ticker']} allocation; no factor edge"'''


def main():
    if not os.path.exists(AGENTS_PATH):
        print(f"[ERROR] {AGENTS_PATH} introuvable")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{AGENTS_PATH}.bak.{ts}"
    shutil.copy2(AGENTS_PATH, backup)
    print(f"[OK] Backup : {backup}")

    with open(AGENTS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if OLD_BLOCK not in content:
        print("[ERROR] Bloc cible introuvable dans agents.py")
        print("        Le fichier a peut-être déjà été patché ou modifié.")
        print("        Patch manuel requis dans FactorAgent.run()")
        sys.exit(2)

    new_content = content.replace(OLD_BLOCK, NEW_BLOCK)

    with open(AGENTS_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] {AGENTS_PATH} patché avec succès")
    print("     - quality_score : formule logistique robuste")
    print("     - pondération combined : 60% momentum / 25% quality / 15% RSI")
    print("     - seuils tilt : overweight >= 6, underweight <= 4")
    print(f"\n✅ Patch appliqué. Restauration : copy {backup} {AGENTS_PATH}")


if __name__ == "__main__":
    main()
