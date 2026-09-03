"""
Patch ciblé api_server.py — Correction Total P&L % + Daily P&L + snapshot quotidien
=====================================================================================

Bugs corrigés :
  A) total_pnl_pct divisait par total_cost (cost basis des positions actives)
     → Maintenant divise par INITIAL_CAPITAL (1 000 000) — cohérent avec NAV
  B) daily_pnl utilisait le DERNIER snapshot de portfolio_history (parfois intraday)
     → Maintenant prend explicitement le dernier snapshot AVANT aujourd'hui
  C) Aucun snapshot du jour n'était inséré dans portfolio_history
     → Ajoute un INSERT/UPDATE quotidien (upsert sur date UNIQUE)

Usage :
  cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
  py -3.13 api_server_pnl_patch.py

Le script :
  1. Sauvegarde api_server.py → api_server.py.bak-<timestamp>
  2. Applique les 3 modifs via remplacements ciblés
  3. Crée l'index UNIQUE sur portfolio_history.date dans thesium.db
  4. Vérifie la cohérence (syntaxe Python) du fichier patché
  5. Idempotent : ne ré-applique pas si déjà patché

Auteur : Perplexity Computer
"""

import os
import re
import sys
import shutil
import sqlite3
import datetime
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).parent.resolve()
API_FILE = PROJECT_DIR / "api_server.py"
DB_FILE = PROJECT_DIR / "thesium.db"
INITIAL_CAPITAL = 1_000_000

MARKER = "# [NEXTONES_PNL_PATCH_APPLIED]"  # Empêche double application


# ---------------------------------------------------------------------------
# Patch 1 — Total P&L %
# ---------------------------------------------------------------------------
PATCH_1_OLD = (
    "        total_cost = sum(u[4] * u[5] for u in updates)\n"
    "        total_pnl = total_market_value - total_cost\n"
    "        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0"
)

PATCH_1_NEW = (
    "        total_cost = sum(u[4] * u[5] for u in updates)\n"
    "        total_pnl = total_market_value - total_cost\n"
    "        # PATCH: % rapporté au capital initial (NAV), pas au cost basis des positions ouvertes\n"
    f"        INITIAL_CAPITAL = {INITIAL_CAPITAL}\n"
    "        total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0"
)


# ---------------------------------------------------------------------------
# Patch 2 — Daily P&L (lookup baseline veille)
# ---------------------------------------------------------------------------
PATCH_2_OLD = (
    "        # Daily P&L = today's portfolio value - yesterday's portfolio value\n"
    "        daily_pnl = total_value - total_prev_value\n"
    "        daily_pnl_pct = (daily_pnl / total_prev_value * 100) if total_prev_value > 0 else 0"
)

PATCH_2_NEW = (
    "        # PATCH: Daily P&L = NAV courant - dernière clôture STRICTEMENT avant aujourd'hui\n"
    "        today_str = datetime.now().strftime(\"%Y-%m-%d\")\n"
    "        prev_row = conn.execute(\n"
    "            \"SELECT total_value FROM portfolio_history WHERE date < ? \"\n"
    "            \"ORDER BY date DESC LIMIT 1\",\n"
    "            (today_str,),\n"
    "        ).fetchone()\n"
    "        total_prev_value = prev_row[0] if prev_row else total_value\n"
    "        daily_pnl = total_value - total_prev_value\n"
    "        daily_pnl_pct = (daily_pnl / total_prev_value * 100) if total_prev_value > 0 else 0\n"
    "\n"
    "        # PATCH: Upsert du snapshot du jour dans portfolio_history\n"
    "        conn.execute(\n"
    "            \"\"\"INSERT INTO portfolio_history (date, total_value, cash, total_pnl)\n"
    "               VALUES (?, ?, ?, ?)\n"
    "               ON CONFLICT(date) DO UPDATE SET\n"
    "                 total_value=excluded.total_value,\n"
    "                 cash=excluded.cash,\n"
    "                 total_pnl=excluded.total_pnl\"\"\",\n"
    "            (today_str, round(total_value, 2), round(cash, 2), round(total_pnl, 2)),\n"
    "        )"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg, level="INFO"):
    prefix = {"INFO": "[i]", "OK": "[OK]", "WARN": "[!]", "ERR": "[X]"}[level]
    print(f"{prefix} {msg}")


def backup_file(path: Path) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak-{ts}")
    shutil.copy2(path, backup)
    log(f"Backup créé : {backup.name}", "OK")
    return backup


def already_patched(content: str) -> bool:
    return MARKER in content


def ensure_unique_index(db_path: Path):
    """Crée l'index UNIQUE sur portfolio_history.date (requis pour ON CONFLICT)."""
    if not db_path.exists():
        log(f"DB introuvable : {db_path} — index non créé (sera créé au prochain démarrage)", "WARN")
        return

    # Vérifier d'abord s'il n'y a pas de doublons qui empêcheraient la création
    conn = sqlite3.connect(str(db_path))
    try:
        dups = conn.execute(
            "SELECT date, COUNT(*) c FROM portfolio_history GROUP BY date HAVING c > 1"
        ).fetchall()
        if dups:
            log(f"Doublons détectés dans portfolio_history.date : {dups}", "WARN")
            log("Nettoyage : on garde la ligne de plus haut id pour chaque date", "INFO")
            conn.execute(
                """DELETE FROM portfolio_history
                   WHERE id NOT IN (
                     SELECT MAX(id) FROM portfolio_history GROUP BY date
                   )"""
            )
            conn.commit()
            log(f"Doublons supprimés", "OK")

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_history_date "
            "ON portfolio_history(date)"
        )
        conn.commit()
        log("Index UNIQUE sur portfolio_history(date) créé/vérifié", "OK")
    finally:
        conn.close()


def apply_patches(content: str) -> tuple[str, list[str]]:
    """Applique les patches. Retourne (nouveau_contenu, liste_des_patches_appliqués)."""
    applied = []
    new_content = content

    # Patch 1
    if PATCH_1_OLD in new_content:
        new_content = new_content.replace(PATCH_1_OLD, PATCH_1_NEW, 1)
        applied.append("Patch 1 (Total P&L %)")
    else:
        log("Patch 1 : bloc cible introuvable — déjà appliqué ou api_server.py modifié", "WARN")

    # Patch 2
    if PATCH_2_OLD in new_content:
        new_content = new_content.replace(PATCH_2_OLD, PATCH_2_NEW, 1)
        applied.append("Patch 2 (Daily P&L + snapshot)")
    else:
        log("Patch 2 : bloc cible introuvable — déjà appliqué ou api_server.py modifié", "WARN")

    # Marqueur en tête de fichier
    if applied and MARKER not in new_content:
        # Insérer le marqueur juste après le shebang/docstring éventuel
        lines = new_content.splitlines(keepends=True)
        insert_at = 0
        # Skip shebang
        if lines and lines[0].startswith("#!"):
            insert_at = 1
        # Skip module docstring
        if insert_at < len(lines) and lines[insert_at].strip().startswith(('"""', "'''")):
            quote = '"""' if '"""' in lines[insert_at] else "'''"
            # docstring sur une ligne ?
            if lines[insert_at].count(quote) >= 2:
                insert_at += 1
            else:
                insert_at += 1
                while insert_at < len(lines) and quote not in lines[insert_at]:
                    insert_at += 1
                insert_at += 1  # ligne contenant la fermeture
        marker_line = f"{MARKER}  # {datetime.datetime.now().isoformat(timespec='seconds')}\n"
        lines.insert(insert_at, marker_line)
        new_content = "".join(lines)

    return new_content, applied


def verify_syntax(file_path: Path) -> bool:
    """Vérifie que le fichier patché reste un Python valide."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            log("Syntaxe Python du fichier patché : OK", "OK")
            return True
        else:
            log(f"Erreur de syntaxe après patch :\n{result.stderr}", "ERR")
            return False
    except Exception as e:
        log(f"Impossible de vérifier la syntaxe : {e}", "WARN")
        return True  # Ne bloque pas si py_compile indisponible


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log(f"Répertoire projet : {PROJECT_DIR}")
    log(f"Fichier cible    : {API_FILE.name}")
    log(f"Base de données  : {DB_FILE.name}")
    print()

    if not API_FILE.exists():
        log(f"Fichier introuvable : {API_FILE}", "ERR")
        sys.exit(1)

    content = API_FILE.read_text(encoding="utf-8")

    if already_patched(content):
        log("Le fichier porte déjà le marqueur du patch — rien à faire", "WARN")
        log("Si tu veux ré-appliquer, restaure depuis un .bak puis relance", "INFO")
        # On crée quand même l'index DB au cas où
        ensure_unique_index(DB_FILE)
        return

    backup = backup_file(API_FILE)
    new_content, applied = apply_patches(content)

    if not applied:
        log("Aucun patch n'a pu être appliqué — vérifie que api_server.py n'a pas été modifié", "ERR")
        log(f"Le backup reste disponible : {backup.name}", "INFO")
        sys.exit(2)

    API_FILE.write_text(new_content, encoding="utf-8")
    log(f"Patches appliqués : {', '.join(applied)}", "OK")

    if not verify_syntax(API_FILE):
        log("Restauration du backup…", "WARN")
        shutil.copy2(backup, API_FILE)
        log("Backup restauré, patch annulé", "OK")
        sys.exit(3)

    # Index DB
    ensure_unique_index(DB_FILE)

    print()
    log("=" * 60, "OK")
    log("Patch terminé avec succès", "OK")
    log("=" * 60, "OK")
    print()
    log("Prochaines étapes :")
    log("  1. Redémarrer le serveur :")
    log("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    log("  2. Recharger l'UI → les widgets Total P&L et Daily P&L doivent être cohérents")
    log("  3. Demain, le snapshot d'aujourd'hui servira de baseline pour le Daily P&L")


if __name__ == "__main__":
    main()
