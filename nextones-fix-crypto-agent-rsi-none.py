# -*- coding: utf-8 -*-
"""
[FIX_CRYPTO_AGENT_RSI_NONE_V1]
Corrige le crash CryptoAgent quand rsi14 / mom30 / autres metriques sont
None (cas SOL nouvellement ajoute sans historique suffisant).

Probleme:
    File "agents.py", line 791, in run
        f"RSI(14) a {rsi14:.1f} ..."
    TypeError: unsupported format string passed to NoneType.__format__

Fix:
  - remplace toutes les f-string {var:.1f} / {var:.2f} dans CryptoAgent.run
    par une expression resistante a None: format si numerique, "N/A" sinon.

Idempotent: detecte le marker [CRYPTO_RSI_NONE_V1] et skip si deja applique.
Backup automatique: agents.py.bak-YYYYMMDD-HHMMSS-crypto-rsi-none

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-fix-crypto-agent-rsi-none.py
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
AGENTS = ROOT / "agents.py"
MARKER = "[CRYPTO_RSI_NONE_V1]"


def main() -> int:
    if not AGENTS.exists():
        print(f"[FAIL] {AGENTS} introuvable.")
        return 1

    src = AGENTS.read_text(encoding="utf-8-sig", errors="replace")

    if MARKER in src:
        print(f"[SKIP] Patch deja applique ({MARKER}).")
        return 0

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = AGENTS.with_suffix(f".py.bak-{ts}-crypto-rsi-none")
    shutil.copy2(AGENTS, backup)
    print(f"[BACKUP] {backup.name}")

    # ------------------------------------------------------------------
    # 1) Localiser la methode CryptoAgent.run et son corps
    # ------------------------------------------------------------------
    m_class = re.search(r"^class\s+CryptoAgent\b", src, re.MULTILINE)
    if not m_class:
        print("[FAIL] class CryptoAgent introuvable.")
        return 2
    class_start = m_class.start()

    # fin = debut de la prochaine class top-level OU fin de fichier
    m_next = re.search(r"^class\s+\w+", src[class_start + 5:], re.MULTILINE)
    class_end = class_start + 5 + m_next.start() if m_next else len(src)
    class_body = src[class_start:class_end]
    print(f"[INFO] CryptoAgent class: {len(class_body)} chars, lignes "
          f"{src[:class_start].count(chr(10))+1}..{src[:class_end].count(chr(10))+1}")

    # ------------------------------------------------------------------
    # 2) Compter les patterns {<var>:.<precision><type>} a corriger
    # ------------------------------------------------------------------
    # On cible UNIQUEMENT les fstrings de la forme {ident:.Nf} ou {ident:.N%}
    # ident peut etre identifiant simple (rsi14, mom30, vol, change_24h, etc.)
    pat_fmt = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(:\.[0-9]+[fFgG%])\}")
    matches = list(pat_fmt.finditer(class_body))
    print(f"[INFO] {len(matches)} format-fields trouves dans CryptoAgent.")

    if not matches:
        print("[WARN] Aucun champ format detecte, rien a patcher.")
        return 3

    # ------------------------------------------------------------------
    # 3) Remplacer chaque {x:.Nf} par {(_safe_fmt(x, '.Nf'))}
    #    On injecte une helper en haut de CryptoAgent.
    # ------------------------------------------------------------------
    def repl(m):
        ident = m.group(1)
        spec  = m.group(2)[1:]   # strip leading ':'
        return f"{{(_safe_fmt({ident}, '{spec}'))}}"

    new_class_body = pat_fmt.sub(repl, class_body)

    # ------------------------------------------------------------------
    # 4) Injecter la helper _safe_fmt juste apres "class CryptoAgent:"
    #    et le marker
    # ------------------------------------------------------------------
    helper = (
        "\n"
        f"    # {MARKER} helper: format-safe sur valeurs potentiellement None\n"
        "    @staticmethod\n"
        "    def _safe_fmt(v, spec='.1f'):\n"
        "        try:\n"
        "            if v is None:\n"
        "                return 'N/A'\n"
        "            return format(float(v), spec)\n"
        "        except (TypeError, ValueError):\n"
        "            return 'N/A'\n"
    )

    # Cherche la ligne 'class CryptoAgent...:' et insere apres la ligne suivante
    m_def = re.search(r"^class\s+CryptoAgent[^\n]*:\s*\n", new_class_body, re.MULTILINE)
    if not m_def:
        print("[FAIL] header class CryptoAgent introuvable apres substitution.")
        return 4
    insert_at = m_def.end()
    new_class_body = new_class_body[:insert_at] + helper + new_class_body[insert_at:]

    # Le helper utilise _safe_fmt(ident, '.1f'); il faut s'assurer que les
    # appels {(_safe_fmt(x, '.1f'))} resolvent _safe_fmt dans le scope local.
    # Comme c'est une @staticmethod sur la classe, dans .run() on doit appeler
    # self._safe_fmt OU on declare un alias local. Plus simple: alias local
    # injecte au debut de la methode run().
    # On cherche 'def run(' de CryptoAgent et on insere 'safe_fmt = self._safe_fmt'
    # au debut (juste apres le 1er '"""...docstring..."""' eventuel).
    # ---------------------------------------------------------
    # Plus robuste: on remplace _safe_fmt(...) par self._safe_fmt(...) dans le
    # corps de run uniquement. Mais l'attribut a deja ete substitue partout
    # dans la classe. Tactique alternative: helper module-level au lieu de
    # staticmethod. Revisons.
    # => On change: helper TOP-LEVEL au-dessus de class CryptoAgent.
    # ---------------------------------------------------------

    # On annule l'insertion staticmethod
    new_class_body = new_class_body[:insert_at] + new_class_body[insert_at + len(helper):]

    helper_top = (
        "\n"
        f"# {MARKER} helper top-level: format-safe sur valeurs potentiellement None\n"
        "def _safe_fmt(v, spec='.1f'):\n"
        "    try:\n"
        "        if v is None:\n"
        "            return 'N/A'\n"
        "        return format(float(v), spec)\n"
        "    except (TypeError, ValueError):\n"
        "        return 'N/A'\n"
        "\n"
    )

    # ------------------------------------------------------------------
    # 5) Reconstruire le fichier complet:
    #    src[:class_start] + helper_top + new_class_body + src[class_end:]
    # ------------------------------------------------------------------
    new_src = src[:class_start] + helper_top + new_class_body + src[class_end:]

    # Verification: au moins une substitution effectuee
    n_subs = new_src.count("_safe_fmt(")
    print(f"[INFO] {n_subs} appels a _safe_fmt apres patch.")
    if n_subs < 1:
        print("[FAIL] Substitution semble vide, annulation.")
        return 5

    # Sanity: la fonction d'origine doit avoir disparu pour les formats fragiles
    remaining_bad = pat_fmt.findall(new_src[class_start:class_end + (len(new_src)-len(src))])
    if remaining_bad:
        print(f"[WARN] {len(remaining_bad)} format-fields restants dans CryptoAgent (peut etre OK).")

    AGENTS.write_text(new_src, encoding="utf-8")
    print(f"[OK] {AGENTS.name} patche.")
    print(f"[OK] Marker insere: {MARKER}")
    print()
    print("Verification:")
    print(f"  py -3.13 -c \"from agents import CryptoAgent; print('import OK')\"")
    print()
    print("Test runtime:")
    print(f"  py -3.13 nextones-diag-run-decision-cycle.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
