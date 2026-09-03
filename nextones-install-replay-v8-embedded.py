# -*- coding: utf-8 -*-
# nextones-install-replay-v8-embedded.py
# Jalon 8B.3 - Fix architectural : carryover state entre cycles replay.
#
# Probleme :
#   open_replay_conn_at() re-seed portfolio_state.cash=$1M et portfolio_positions
#   vide a chaque cycle (replay_db_view.py L146-157).
#   Resultat : chaque cycle achete 15 NOUVELLES positions, qty_current=0 partout,
#   sum(buy_notional) cumule 3x le NAV alors que cash final ne baisse que de
#   ~$287k (dernier cycle).
#
# Fix :
#   Ajouter helper _restore_state_from_previous_cycle dans ReplayOrchestrator
#   qui lit la derniere ligne replay_nav_history (cash) et replay_positions
#   (qty, avg_cost par ticker) du run_id courant, et les re-injecte dans
#   :memory:.portfolio_state / :memory:.portfolio_positions.
#   Hook : juste apres open_replay_conn_at, avant _insert_cycle.
#
# Marker : # [8B3_STATE_CARRYOVER_V1]
#
# Validation : ast.parse + py_compile + idempotent (skip si marker present).
# Backup .py.bak.<timestamp>
#
# Usage : py -3.13 nextones-install-replay-v8-embedded.py
# 100% ASCII pur (zero byte > 127).

import ast
import os
import py_compile
import shutil
import sys
import tempfile
import time
from datetime import datetime

# --- Config ---
TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\replay_orchestrator.py"
MARKER = "[8B3_STATE_CARRYOVER_V1]"

HELPER_CODE = '''
    # [8B3_STATE_CARRYOVER_V1] Restore state from previous cycle.
    def _restore_state_from_previous_cycle(self, conn_replay):
        """Lit derniere ligne replay_nav_history + replay_positions et restaure
        dans :memory:.portfolio_state / portfolio_positions.

        Si pas de cycle precedent dans replay_nav_history pour ce run_id,
        on garde le seed $1M (cycle 1).
        """
        import sqlite3 as _sql3
        if self.run_id is None:
            return {"restored": False, "reason": "no_run_id"}

        prod_conn = _sql3.connect(self.db_path, timeout=10.0)
        try:
            row = prod_conn.execute(
                "SELECT cash, day_t, cycle_id_replay FROM replay_nav_history "
                "WHERE run_id=? ORDER BY day_t DESC, cycle_id_replay DESC LIMIT 1",
                (self.run_id,),
            ).fetchone()
            if not row:
                if self.verbose:
                    print(f"           CARRYOVER skip : no prev nav_history for run_id={self.run_id}")
                return {"restored": False, "reason": "first_cycle"}
            prev_cash, prev_day, prev_cir = row
            prev_pos = prod_conn.execute(
                "SELECT ticker, quantity, avg_cost FROM replay_positions "
                "WHERE run_id=? AND cycle_id_replay=?",
                (self.run_id, prev_cir),
            ).fetchall()
        finally:
            prod_conn.close()

        # Update portfolio_state.cash dans :memory:
        conn_replay.execute(
            "UPDATE portfolio_state SET cash=?, total_value=? WHERE id=1",
            (float(prev_cash), float(prev_cash)),
        )

        # Re-injecter positions
        n_pos = 0
        for ticker, qty, avg_cost in prev_pos:
            if qty is None or float(qty) <= 0:
                continue
            irow = conn_replay.execute(
                "SELECT id FROM instruments WHERE ticker=?", (ticker,)
            ).fetchone()
            if not irow:
                continue
            iid = irow[0]
            # INSERT OR REPLACE : portfolio_positions UNIQUE sur instrument_id
            # (selon schema prod). Si la colonne avg_cost est absente du schema
            # in-memory, on essaie quand meme et on tombe sur quantity seul.
            try:
                conn_replay.execute(
                    "INSERT OR REPLACE INTO portfolio_positions "
                    "(instrument_id, quantity, avg_cost) VALUES (?, ?, ?)",
                    (iid, float(qty), float(avg_cost) if avg_cost is not None else 0.0),
                )
            except Exception:
                conn_replay.execute(
                    "INSERT OR REPLACE INTO portfolio_positions "
                    "(instrument_id, quantity) VALUES (?, ?)",
                    (iid, float(qty)),
                )
            n_pos += 1

        conn_replay.commit()

        if self.verbose:
            print(f"           CARRYOVER OK : cash={prev_cash:.2f} positions={n_pos} "
                  f"(from cycle_id_replay={prev_cir} day_t={prev_day})")
        return {"restored": True, "cash": float(prev_cash), "n_positions": n_pos,
                "from_day_t": prev_day, "from_cycle_id_replay": prev_cir}

'''.lstrip("\n")

HOOK_LINE = (
    "        # [8B3_STATE_CARRYOVER_V1] Restore state from previous cycle if any.\n"
    "        self._restore_state_from_previous_cycle(conn_replay)\n"
)


def _read_utf8_sig(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")


def _write_utf8_nobom(path, content):
    with open(path, "wb") as f:
        f.write(content.encode("utf-8"))


def _validate_ascii(content, label):
    bad = []
    for i, ch in enumerate(content):
        if ord(ch) > 127:
            bad.append((i, ord(ch), ch))
            if len(bad) >= 5:
                break
    if bad:
        print(f"FAIL {label} : non-ASCII bytes detected : {bad}")
        sys.exit(1)


def _validate_python(content, label):
    try:
        ast.parse(content)
    except SyntaxError as e:
        print(f"FAIL {label} ast.parse : {e}")
        sys.exit(1)
    tmp = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".py")
    tmp.write(content.encode("utf-8"))
    tmp.close()
    try:
        py_compile.compile(tmp.name, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"FAIL {label} py_compile : {e}")
        sys.exit(1)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def main():
    if not os.path.exists(TARGET):
        print(f"FAIL : target not found : {TARGET}")
        sys.exit(1)

    src = _read_utf8_sig(TARGET)

    # Validate ASCII of helper code (paranoid)
    _validate_ascii(HELPER_CODE, "HELPER_CODE")
    _validate_ascii(HOOK_LINE, "HOOK_LINE")

    # Idempotence : skip si marker present
    if MARKER in src:
        print(f"SKIP : marker {MARKER} already present in {TARGET}")
        # Verifier que ca compile quand meme
        _validate_python(src, "current file")
        print("OK   : file is valid Python.")
        return

    # ----- PATCH 1 : inserer le helper avant la methode run_cycle -----
    # On cherche la ligne "    def run_cycle(" (indentation classe) et on
    # insere HELPER_CODE juste avant.
    anchor1 = "    def run_cycle(self, day_t: str, cycle_seq: int)"
    idx1 = src.find(anchor1)
    if idx1 == -1:
        print(f"FAIL : anchor1 not found : {anchor1!r}")
        sys.exit(1)
    # Remonter au debut de la ligne (devrait deja l'etre)
    # Insertion avant l'anchor (avec un saut de ligne deja present avant la def)
    patched = src[:idx1] + HELPER_CODE + src[idx1:]

    # ----- PATCH 2 : appel du helper dans run_cycle, juste apres
    # open_replay_conn_at, AVANT le bloc "if self.verbose: stats = get_snapshot_stats"
    # On cible la ligne exacte "        conn_replay = open_replay_conn_at(day_t, self.db_path)"
    anchor2 = "        conn_replay = open_replay_conn_at(day_t, self.db_path)\n"
    idx2 = patched.find(anchor2)
    if idx2 == -1:
        print(f"FAIL : anchor2 not found : {anchor2!r}")
        sys.exit(1)
    # Inserer HOOK_LINE juste apres
    insert_at = idx2 + len(anchor2)
    patched = patched[:insert_at] + HOOK_LINE + patched[insert_at:]

    # Validate
    _validate_ascii(patched, "patched content")
    _validate_python(patched, "patched content")

    # Backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print(f"BACKUP : {bak}")

    # Write
    _write_utf8_nobom(TARGET, patched)
    print(f"WRITE  : {TARGET} ({len(patched)} chars)")

    # Re-read + re-validate
    final = _read_utf8_sig(TARGET)
    if MARKER not in final:
        print("FAIL : marker missing after write")
        sys.exit(1)
    _validate_python(final, "post-write file")
    print(f"OK     : marker {MARKER} present, file is valid Python.")
    print("DONE   : ready to relaunch nextones-run-replay-8b3-v2.py")


if __name__ == "__main__":
    main()
