# -*- coding: utf-8 -*-
# replay_orchestrator.py
# Jalon 8B.2 + 8B.3 - Orchestrator event-driven : regime + convergence + PCA + EXECUTION
# v3 (8B.3) : ajout pipeline execution (qty + risk_check + fill_simulator + state update)
#
# Boucle :
#   for day_t in trading_calendar(window_start, window_end):
#       1. conn_replay = open_replay_conn_at(day_t)  # 11 tables, K=$1M seed
#       2. cycle_id_replay = insert replay_cycles
#       3. cycle_id_prod   = "YYYYMMDD-NNN" (cle pour les tables :memory:)
#       4. detect_market_regime (monkey-patch FRED VIX + freshness)
#       5. log_market_regime    -> regime_log dans la conn :memory:
#       6. compute_convergence  + save_convergence_snapshot dans :memory:
#       7. run_construction_agent (PCA) : ecrit portfolio_targets, portfolio_targets_history,
#                                          portfolio_state, et appelle apply_convergence_sizing
#                                          en interne (regime_info=None autorise).
#       8. Export :memory: -> replay_convergence_snapshots / replay_targets / replay_targets_history
#       9. Update replay_cycles (snapshot_id, n_targets, regime, vix, details_json)
#       10. conn_replay.close()
#
# JAMAIS d'ecriture vers la prod (toutes les ecritures vont dans replay_* uniquement).

import os
import sys
import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

# Force le mode replay des l'import
os.environ.setdefault("NEXTONES_REPLAY_MODE", "1")

DB_PATH_DEFAULT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Ajoute le dossier prod au sys.path pour importer les agents
if PROD_DIR not in sys.path:
    sys.path.insert(0, PROD_DIR)

# Ajoute aussi le workspace courant
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Imports replay
from replay_db_view import (
    open_replay_conn_at,
    get_snapshot_stats,
    monkey_patch_for_replay,
    restore_for_replay,
)
from replay_adapters import MarketDataAdapter, FREDAdapter, PPLXNeutralAdapter
from fill_simulator import simulate_fill, FillResult

# Cap de concentration single-name pour le replay (15% NAV).
# En prod c'est dynamique selon regime ; on prend la valeur prod par defaut.
REPLAY_CONCENTRATION_CAP_PCT = 0.15


def _is_trading_day(d: date) -> bool:
    """Heuristique simple : exclut weekends. Jours feries NYSE ignores (TODO)."""
    return d.weekday() < 5


def trading_calendar(window_start: str, window_end: str) -> List[str]:
    """Genere la liste des jours ouvres entre les 2 dates (incluses)."""
    start = datetime.strptime(window_start, "%Y-%m-%d").date()
    end = datetime.strptime(window_end, "%Y-%m-%d").date()
    out = []
    d = start
    while d <= end:
        if _is_trading_day(d):
            out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


class ReplayOrchestrator:
    """Orchestrateur d'un run de replay (1 run = 1 fenetre)."""

    def __init__(
        self,
        label: str,
        window_start: str,
        window_end: str,
        initial_capital: float = 1_000_000.0,
        ablation_flags: Optional[Dict[str, Any]] = None,
        db_path: str = DB_PATH_DEFAULT,
        verbose: bool = True,
    ):
        self.label = label
        self.window_start = window_start
        self.window_end = window_end
        self.initial_capital = float(initial_capital)
        self.ablation_flags = ablation_flags or {}
        self.db_path = db_path
        self.verbose = verbose

        self.run_id: Optional[int] = None
        self.market_data = MarketDataAdapter(db_path)
        self.fred = FREDAdapter(db_path)
        self.pplx = PPLXNeutralAdapter()

    # ---------- Run lifecycle ----------

    def open_run(self) -> int:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO replay_runs
              (label, window_start, window_end, initial_capital, ablation_flags,
               agents_perimeter, created_at, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                self.label,
                self.window_start,
                self.window_end,
                self.initial_capital,
                json.dumps(self.ablation_flags),
                "8B.2+8B.3: regime + convergence + PCA + execution(risk+fill)",
                datetime.now().isoformat(timespec="seconds"),
                "Jalon 8B.3 wrapper",
            ),
        )
        self.run_id = cur.lastrowid
        conn.commit()
        conn.close()
        if self.verbose:
            print(f"  [run_id={self.run_id}] OPENED  label={self.label}")
        return self.run_id

    def close_run(self, status: str = "done"):
        if self.run_id is None:
            return
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute(
            "UPDATE replay_runs SET status=?, finished_at=? WHERE run_id=?",
            (status, datetime.now().isoformat(timespec="seconds"), self.run_id),
        )
        conn.commit()
        conn.close()
        if self.verbose:
            print(f"  [run_id={self.run_id}] CLOSED  status={status}")

    # ---------- Per-cycle ----------

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

    def run_cycle(self, day_t: str, cycle_seq: int) -> Dict[str, Any]:
        """Joue un cycle complet 8B.2 : regime + convergence + portfolio_construction."""
        # 1. Conn :memory: snapshotee au day_t
        conn_replay = open_replay_conn_at(day_t, self.db_path)
        # [8B3_STATE_CARRYOVER_V1] Restore state from previous cycle if any.
        self._restore_state_from_previous_cycle(conn_replay)

        if self.verbose:
            stats = get_snapshot_stats(conn_replay)
            print(f"  [{day_t}] snapshot: prices={stats.get('prices')} max={stats.get('prices_max_date')} "
                  f"macro={stats.get('macro_history')} max={stats.get('macro_history_max_date')}")

        # 2. Insert ligne replay_cycles (sera updated en fin de cycle)
        cycle_id_replay = self._insert_cycle(day_t, cycle_seq)

        # 3. cycle_id_prod : clef utilisee par tous les agents prod (TEXT, format "YYYYMMDD-NNN")
        cycle_id_prod = day_t.replace("-", "") + f"-{cycle_seq:03d}"

        # 4. Detect regime (monkey-patch combine : FRED VIX + freshness vs day_t)
        originals = monkey_patch_for_replay(day_t, self.db_path)
        regime = {}
        try:
            import market_regime_v1
            regime = market_regime_v1.detect_market_regime(conn_replay)
            # 5. Log regime dans regime_log (table de la conn :memory:)
            try:
                market_regime_v1.log_market_regime(conn_replay, cycle_id_prod, regime)
            except Exception as e:
                if self.verbose:
                    print(f"           WARN log_market_regime: {e}")
        finally:
            restore_for_replay(originals)

        # 6. Convergence
        conv_n_inserted = 0
        try:
            import convergence_engine
            conv_results = convergence_engine.compute_convergence(conn_replay, cycle_id_prod)
            conv_n_inserted = convergence_engine.save_convergence_snapshot(
                conn_replay, cycle_id_prod, conv_results
            ) or 0
        except Exception as e:
            if self.verbose:
                print(f"           ERR convergence: {e}")
            conv_results = []

        # 7. Portfolio Construction Agent (PCA)
        #    regime_info=None autorise : PCA detecte auto via regime_log :memory:
        pca_result: Dict[str, Any] = {}
        try:
            import portfolio_construction_agent as pca
            pca_result = pca.run_construction_agent(
                conn_replay,
                cycle_id=cycle_id_prod,
                regime_info=None,
                dry_run=False,
            ) or {}
        except Exception as e:
            if self.verbose:
                print(f"           ERR run_construction_agent: {e}")
            pca_result = {"error": str(e)}

        snapshot_id = pca_result.get("snapshot_id")
        n_targets = pca_result.get("n_targets", 0)

        # 8. Export PCA -> tables replay_*
        n_conv = self._export_convergence_snapshots(conn_replay, cycle_id_replay, day_t, cycle_id_prod)
        n_tgt = self._export_targets(conn_replay, cycle_id_replay, day_t)
        n_hist = self._export_targets_history(conn_replay, cycle_id_replay, day_t)

        # 11. [8B.3] EXECUTION : qty + risk_check + fill_simulator + state update
        exec_stats = self._execute_targets(conn_replay, cycle_id_replay, day_t, cycle_id_prod)

        # 12. [8B.3] Recompute NAV final = cash + sum(qty * close_day_t)
        nav_stats = self._compute_nav_and_update_state(conn_replay, day_t)

        # 13. [8B.3] Exports execution : orders + fills + positions + nav_history
        n_orders_exp = self._export_orders(conn_replay, cycle_id_replay, day_t)
        n_fills_exp = self._export_fills(conn_replay, cycle_id_replay, day_t)
        n_pos_exp = self._export_positions(conn_replay, cycle_id_replay, day_t)
        self._insert_nav_history(
            cycle_id_replay, day_t,
            nav=nav_stats["nav"],
            cash=nav_stats["cash"],
            positions_value=nav_stats["positions_value"],
            n_positions=nav_stats["n_positions"],
            n_orders=exec_stats["n_orders"],
            n_fills=exec_stats["n_fills"],
        )

        # 14. Snapshot final pour diag
        cash_after = nav_stats["cash"]
        nav_after = nav_stats["nav"]

        # 15. Update replay_cycles avec tout le payload (incl. 8B.3)
        self._update_cycle(
            cycle_id_replay,
            regime=regime,
            cycle_id_prod=cycle_id_prod,
            snapshot_id=snapshot_id,
            n_targets=n_targets,
            n_conv_exported=n_conv,
            n_targets_exported=n_tgt,
            n_history_exported=n_hist,
            cash_after=cash_after,
            pca_result=pca_result,
            exec_stats=exec_stats,
            nav_stats=nav_stats,
        )

        conn_replay.close()

        if self.verbose:
            eq = regime.get("equity", {}) or {}
            cr = regime.get("crypto", {}) or {}
            print(f"           regime equity={str(eq.get('regime')):<7s} (vix={eq.get('vix_value')})  "
                  f"crypto={str(cr.get('regime')):<7s}")
            print(f"           convergence: saved={conv_n_inserted}  exported={n_conv}")
            print(f"           PCA: snapshot_id={snapshot_id}  n_targets={n_targets}  exported targets={n_tgt} hist={n_hist}")
            print(f"           EXEC: orders={exec_stats['n_orders']} approved={exec_stats['n_approved']} "
                  f"filled={exec_stats['n_fills']} rejected={exec_stats['n_rejected']} "
                  f"buys={exec_stats['n_buys']} sells={exec_stats['n_sells']}")
            print(f"           NAV: nav={nav_after:,.2f}  cash={cash_after:,.2f}  "
                  f"positions_value={nav_stats['positions_value']:,.2f}  n_pos={nav_stats['n_positions']}")

        return {
            "cycle_id": cycle_id_replay,
            "cycle_id_prod": cycle_id_prod,
            "day_t": day_t,
            "regime": regime,
            "snapshot_id": snapshot_id,
            "n_targets": n_targets,
            "n_conv_exported": n_conv,
            "n_targets_exported": n_tgt,
            "n_history_exported": n_hist,
            "cash_after": cash_after,
            "nav_after": nav_after,
            "exec_stats": exec_stats,
            "nav_stats": nav_stats,
        }

    # ---------- Writes vers replay_* ----------

    def _insert_cycle(self, day_t: str, cycle_seq: int) -> int:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO replay_cycles (run_id, day_t, cycle_seq, cycle_status, created_at)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (self.run_id, day_t, cycle_seq, datetime.now().isoformat(timespec="seconds")),
        )
        cid = cur.lastrowid
        conn.commit()
        conn.close()
        return cid

    def _update_cycle(
        self,
        cycle_id: int,
        regime: Dict[str, Any],
        cycle_id_prod: str,
        snapshot_id: Any,
        n_targets: int,
        n_conv_exported: int,
        n_targets_exported: int,
        n_history_exported: int,
        cash_after: Optional[float],
        pca_result: Dict[str, Any],
        exec_stats: Optional[Dict[str, Any]] = None,
        nav_stats: Optional[Dict[str, Any]] = None,
    ):
        eq = regime.get("equity", {}) or {}
        cr = regime.get("crypto", {}) or {}
        details = {
            "equity": eq,
            "crypto": cr,
            "cycle_id_prod": cycle_id_prod,
            "snapshot_id": snapshot_id,
            "n_targets": n_targets,
            "n_conv_exported": n_conv_exported,
            "n_targets_exported": n_targets_exported,
            "n_history_exported": n_history_exported,
            "cash_after": cash_after,
            "pca_regime": pca_result.get("regime"),
            "pca_budget_pct": pca_result.get("budget_pct"),
            "pca_n_tickers_evaluated": pca_result.get("n_tickers_evaluated"),
            "pca_n_tickers_included": pca_result.get("n_tickers_included"),
            "exec": exec_stats or {},
            "nav": nav_stats or {},
        }
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE replay_cycles
            SET regime_equity=?, regime_crypto=?, vix=?, cycle_status='ok', details_json=?
            WHERE cycle_id=?
            """,
            (
                eq.get("regime"),
                cr.get("regime"),
                eq.get("vix_value"),
                json.dumps(details, default=str),
                cycle_id,
            ),
        )
        # Log regime aussi dans replay_regime_log
        cur.execute(
            """
            INSERT INTO replay_regime_log
              (run_id, cycle_id, day_t, regime_equity, regime_crypto, vix,
               spy_dd_20j, btc_dd_20j, vol_equity, vol_crypto,
               multiplier_equity, multiplier_crypto, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.run_id,
                cycle_id,
                self._day_t_of(cycle_id, conn),
                eq.get("regime"),
                cr.get("regime"),
                eq.get("vix_value"),
                eq.get("drawdown_5d_pct"),
                cr.get("drawdown_5d_pct"),
                eq.get("realized_vol_pct"),
                cr.get("realized_vol_pct"),
                eq.get("buy_mult"),
                cr.get("buy_mult"),
                json.dumps({"equity": eq, "crypto": cr}, default=str),
            ),
        )
        conn.commit()
        conn.close()

    def _day_t_of(self, cycle_id: int, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT day_t FROM replay_cycles WHERE cycle_id=?", (cycle_id,)
        ).fetchone()
        return row[0] if row else ""

    # ---------- Exports :memory: -> replay_* ----------

    def _export_convergence_snapshots(
        self, conn_replay: sqlite3.Connection, cycle_id_replay: int, day_t: str, cycle_id_prod: str
    ) -> int:
        """Copie convergence_snapshots (memory) -> replay_convergence_snapshots (prod)."""
        try:
            rows = conn_replay.execute(
                """
                SELECT cycle_id, ticker, direction_consensus, n_aligned, n_present,
                       convergence_pct, sizing_multiplier, forced_exit, drift, is_crypto,
                       buckets_json, created_at
                FROM convergence_snapshots
                WHERE cycle_id = ?
                """,
                (cycle_id_prod,),
            ).fetchall()
        except sqlite3.Error as e:
            if self.verbose:
                print(f"           WARN export convergence: {e}")
            return 0

        if not rows:
            return 0

        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        n = 0
        for r in rows:
            (cid_prod, ticker, dir_cons, n_align, n_pres, conv_pct, sizing_m,
             forced, drift, is_cr, buckets_j, created_at) = r
            cur.execute(
                """
                INSERT INTO replay_convergence_snapshots
                  (run_id, cycle_id_replay, day_t, cycle_id_prod, ticker,
                   direction_consensus, n_aligned, n_present, convergence_pct,
                   sizing_multiplier, forced_exit, drift, is_crypto, buckets_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id, cycle_id_replay, day_t, cid_prod, ticker,
                    dir_cons, n_align, n_pres, conv_pct, sizing_m,
                    forced, drift, is_cr, buckets_j, created_at or now,
                ),
            )
            n += 1
        conn.commit()
        conn.close()
        return n

    def _export_targets(
        self, conn_replay: sqlite3.Connection, cycle_id_replay: int, day_t: str
    ) -> int:
        """Copie portfolio_targets (memory) -> replay_targets (prod)."""
        try:
            rows = conn_replay.execute(
                """
                SELECT ticker, target_weight_pct, active, source,
                       snapshot_id, score, agent_decided, updated_at
                FROM portfolio_targets
                """
            ).fetchall()
        except sqlite3.Error as e:
            if self.verbose:
                print(f"           WARN export targets: {e}")
            return 0

        if not rows:
            return 0

        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        n = 0
        for r in rows:
            ticker, tw, active, source, snap_id, score, agent_dec, updated_at = r
            cur.execute(
                """
                INSERT INTO replay_targets
                  (run_id, cycle_id_replay, day_t, ticker, target_weight_pct,
                   active, source, snapshot_id, score, agent_decided, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id, cycle_id_replay, day_t, ticker, tw,
                    active, source, snap_id, score, agent_dec, updated_at or now,
                ),
            )
            n += 1
        conn.commit()
        conn.close()
        return n

    def _export_targets_history(
        self, conn_replay: sqlite3.Connection, cycle_id_replay: int, day_t: str
    ) -> int:
        """Copie portfolio_targets_history (memory) -> replay_targets_history (prod)."""
        try:
            rows = conn_replay.execute(
                """
                SELECT snapshot_id, ticker, score, target_weight_pct, prev_target_weight_pct,
                       components_json, regime, included, cap_floor_applied, created_at
                FROM portfolio_targets_history
                """
            ).fetchall()
        except sqlite3.Error as e:
            if self.verbose:
                print(f"           WARN export history: {e}")
            return 0

        if not rows:
            return 0

        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        n = 0
        for r in rows:
            (snap_id, ticker, score, tw, prev_tw, comp_j, regime_s,
             included, capfloor, created_at) = r
            cur.execute(
                """
                INSERT INTO replay_targets_history
                  (run_id, cycle_id_replay, day_t, snapshot_id, ticker, score,
                   target_weight_pct, prev_target_weight_pct, components_json,
                   regime, included, cap_floor_applied, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id, cycle_id_replay, day_t, snap_id, ticker, score,
                    tw, prev_tw, comp_j, regime_s, included, capfloor, created_at or now,
                ),
            )
            n += 1
        conn.commit()
        conn.close()
        return n

    def _read_cash(self, conn_replay: sqlite3.Connection) -> Optional[float]:
        try:
            row = conn_replay.execute(
                "SELECT cash FROM portfolio_state WHERE id=1"
            ).fetchone()
            return float(row[0]) if row else None
        except sqlite3.Error:
            return None

    # ============================================================
    # [8B.3] EXECUTION ENGINE WRAPPER
    # ============================================================

    def _get_close_at(self, conn_replay: sqlite3.Connection, ticker: str, day_t: str) -> Optional[float]:
        """Lit le close du day_t (max date <= day_t) pour un ticker."""
        try:
            row = conn_replay.execute(
                """
                SELECT p.close FROM prices p
                JOIN instruments i ON i.id = p.instrument_id
                WHERE i.ticker = ? AND p.date <= ?
                ORDER BY p.date DESC LIMIT 1
                """,
                (ticker, day_t),
            ).fetchone()
            return float(row[0]) if row and row[0] is not None else None
        except sqlite3.Error:
            return None

    def _get_instrument_id(self, conn_replay: sqlite3.Connection, ticker: str) -> Optional[int]:
        try:
            row = conn_replay.execute(
                "SELECT id FROM instruments WHERE ticker = ?", (ticker,)
            ).fetchone()
            return int(row[0]) if row else None
        except sqlite3.Error:
            return None

    def _get_current_position_qty(self, conn_replay: sqlite3.Connection, instrument_id: int) -> float:
        try:
            row = conn_replay.execute(
                "SELECT quantity FROM portfolio_positions WHERE instrument_id = ?",
                (instrument_id,),
            ).fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
        except sqlite3.Error:
            return 0.0

    def _get_current_avg_cost(self, conn_replay: sqlite3.Connection, instrument_id: int) -> float:
        try:
            row = conn_replay.execute(
                "SELECT avg_cost FROM portfolio_positions WHERE instrument_id = ?",
                (instrument_id,),
            ).fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
        except sqlite3.Error:
            return 0.0

    def _read_nav(self, conn_replay: sqlite3.Connection) -> float:
        """NAV courante (cash + sum(qty * current_price)) approche.
        Pour le sizing, on prend total_value de portfolio_state (mis a jour
        en fin de cycle precedent)."""
        try:
            row = conn_replay.execute(
                "SELECT total_value FROM portfolio_state WHERE id=1"
            ).fetchone()
            return float(row[0]) if row and row[0] is not None else self.initial_capital
        except sqlite3.Error:
            return self.initial_capital

    def _check_concentration(self, ticker_pct_after: float) -> bool:
        """Cap concentration simple : new_weight_pct <= 15%."""
        return ticker_pct_after <= REPLAY_CONCENTRATION_CAP_PCT * 100.0

    def _execute_targets(
        self, conn_replay: sqlite3.Connection, cycle_id_replay: int,
        day_t: str, cycle_id_prod: str,
    ) -> Dict[str, Any]:
        """
        Pour chaque target (target_weight_pct > 0) :
          1. Calcule qty_target = floor((pct/100 * NAV) / close_day_t)
          2. Compare a current_qty -> delta_qty (buy si > 0, sell si < 0)
          3. Check concentration (15% cap)
          4. INSERT orders (status='approved' ou 'rejected')
          5. Si approved : simulate_fill -> INSERT fills + UPSERT positions + update cash
        """
        stats = {
            "n_orders": 0, "n_approved": 0, "n_rejected": 0,
            "n_fills": 0, "n_buys": 0, "n_sells": 0,
            "total_buy_notional": 0.0, "total_sell_notional": 0.0,
        }

        try:
            targets = conn_replay.execute(
                """
                SELECT ticker, target_weight_pct, score, snapshot_id
                FROM portfolio_targets
                WHERE target_weight_pct IS NOT NULL
                ORDER BY target_weight_pct DESC
                """
            ).fetchall()
        except sqlite3.Error as e:
            if self.verbose:
                print(f"           ERR read targets: {e}")
            return stats

        nav_before = self._read_nav(conn_replay)

        for tgt_row in targets:
            ticker = tgt_row[0]
            pct = float(tgt_row[1] or 0.0)
            score = tgt_row[2]
            snap_id = tgt_row[3]

            instrument_id = self._get_instrument_id(conn_replay, ticker)
            if instrument_id is None:
                continue

            close_t = self._get_close_at(conn_replay, ticker, day_t)
            if close_t is None or close_t <= 0:
                self._insert_replay_order(
                    conn_replay, cycle_id_replay, day_t, cycle_id_prod, ticker,
                    side="BUY", qty=0.0, qty_target=0.0, qty_current=0.0,
                    target_pct=pct, status="rejected", fill_price=None, slippage=None,
                    price_close=None, nav_before=nav_before,
                    risk_json=json.dumps({"reason": "no_close_price"}),
                    rejection="no_close_price",
                )
                stats["n_orders"] += 1
                stats["n_rejected"] += 1
                continue

            # Sizing
            qty_target_float = (pct / 100.0) * nav_before / close_t
            qty_target = int(qty_target_float)  # floor entier
            qty_current = self._get_current_position_qty(conn_replay, instrument_id)
            delta_qty = qty_target - qty_current

            if delta_qty == 0:
                # Pas d'ordre necessaire, on log un "hold" non comptabilise
                continue

            side = "BUY" if delta_qty > 0 else "SELL"
            abs_qty = abs(delta_qty)
            notional = abs_qty * close_t

            # Risk check : concentration apres trade (uniquement pour BUY)
            risk_passed = True
            risk_blocked = None
            if side == "BUY":
                new_qty = qty_current + abs_qty
                new_notional = new_qty * close_t
                new_pct = (new_notional / nav_before) * 100.0 if nav_before > 0 else 0.0
                if not self._check_concentration(new_pct):
                    risk_passed = False
                    risk_blocked = "concentration_cap_15pct"

            risk_json = json.dumps({
                "passed": risk_passed,
                "blocked_by": risk_blocked,
                "check": "concentration_simple",
                "cap_pct": REPLAY_CONCENTRATION_CAP_PCT * 100.0,
                "nav_before": nav_before,
                "close_t": close_t,
                "qty_target": qty_target,
                "qty_current": qty_current,
                "delta_qty": delta_qty,
            })

            if not risk_passed:
                self._insert_replay_order(
                    conn_replay, cycle_id_replay, day_t, cycle_id_prod, ticker,
                    side=side, qty=abs_qty, qty_target=qty_target, qty_current=qty_current,
                    target_pct=pct, status="rejected", fill_price=None, slippage=None,
                    price_close=close_t, nav_before=nav_before,
                    risk_json=risk_json, rejection=risk_blocked,
                )
                stats["n_orders"] += 1
                stats["n_rejected"] += 1
                continue

            # Simulate fill
            try:
                fr = simulate_fill(self.market_data, ticker, side, abs_qty, day_t)
            except Exception as e:
                fr = FillResult(
                    ticker, side, abs_qty, day_t, None, None, None, None,
                    "rejected", f"simulate_fill_error: {str(e)[:100]}",
                )

            if fr.status != "filled":
                self._insert_replay_order(
                    conn_replay, cycle_id_replay, day_t, cycle_id_prod, ticker,
                    side=side, qty=abs_qty, qty_target=qty_target, qty_current=qty_current,
                    target_pct=pct, status="rejected", fill_price=fr.price_filled,
                    slippage=fr.slippage_bps, price_close=close_t, nav_before=nav_before,
                    risk_json=risk_json, rejection=fr.reason or "fill_failed",
                )
                stats["n_orders"] += 1
                stats["n_rejected"] += 1
                continue

            # FILLED : on insere order + fill + update positions + cash
            fill_price = float(fr.price_filled)
            slippage = float(fr.slippage_bps or 0.0)
            fill_notional = abs_qty * fill_price

            order_id = self._insert_replay_order(
                conn_replay, cycle_id_replay, day_t, cycle_id_prod, ticker,
                side=side, qty=abs_qty, qty_target=qty_target, qty_current=qty_current,
                target_pct=pct, status="filled", fill_price=fill_price,
                slippage=slippage, price_close=close_t, nav_before=nav_before,
                risk_json=risk_json, rejection=None,
            )

            # INSERT fill dans la conn :memory: (orders table prod-shaped)
            try:
                cur = conn_replay.cursor()
                cur.execute(
                    """
                    INSERT INTO orders
                      (instrument_id, side, quantity, order_type, status,
                       risk_check_result, created_at, cycle_id)
                    VALUES (?, ?, ?, 'market', 'filled', ?, ?, ?)
                    """,
                    (instrument_id, side.lower(), abs_qty, risk_json,
                     datetime.now().isoformat(timespec="seconds"), cycle_id_prod),
                )
                mem_order_id = cur.lastrowid
                cur.execute(
                    """
                    INSERT INTO fills
                      (order_id, fill_price, fill_quantity, slippage, fees, filled_at)
                    VALUES (?, ?, ?, ?, 0, ?)
                    """,
                    (mem_order_id, fill_price, abs_qty, slippage,
                     datetime.now().isoformat(timespec="seconds")),
                )
            except sqlite3.Error as e:
                if self.verbose:
                    print(f"           WARN insert order/fill :memory:: {e}")

            # Update portfolio_positions :memory:
            self._upsert_position(conn_replay, instrument_id, side, abs_qty, fill_price, close_t)

            # Update cash
            self._update_cash(conn_replay, side, fill_notional)

            stats["n_orders"] += 1
            stats["n_approved"] += 1
            stats["n_fills"] += 1
            if side == "BUY":
                stats["n_buys"] += 1
                stats["total_buy_notional"] += fill_notional
            else:
                stats["n_sells"] += 1
                stats["total_sell_notional"] += fill_notional

        try:
            conn_replay.commit()
        except sqlite3.Error:
            pass

        return stats

    def _upsert_position(
        self, conn_replay: sqlite3.Connection, instrument_id: int,
        side: str, qty: float, fill_price: float, current_price: float,
    ):
        """UPSERT portfolio_positions :memory: avec recalcul avg_cost (BUY)."""
        try:
            cur = conn_replay.cursor()
            row = cur.execute(
                "SELECT quantity, avg_cost FROM portfolio_positions WHERE instrument_id = ?",
                (instrument_id,),
            ).fetchone()
            now = datetime.now().isoformat(timespec="seconds")
            if row is None:
                # Premiere position : BUY pur
                if side == "BUY":
                    cur.execute(
                        """
                        INSERT INTO portfolio_positions
                          (instrument_id, quantity, avg_cost, current_price,
                           unrealized_pnl, weight_pct, updated_at)
                        VALUES (?, ?, ?, ?, 0, 0, ?)
                        """,
                        (instrument_id, qty, fill_price, current_price, now),
                    )
                return

            cur_qty = float(row[0] or 0.0)
            cur_avg = float(row[1] or 0.0)

            if side == "BUY":
                new_qty = cur_qty + qty
                # Recalcul avg_cost pondere (uniquement sur BUY)
                if new_qty > 0:
                    new_avg = (cur_qty * cur_avg + qty * fill_price) / new_qty
                else:
                    new_avg = fill_price
            else:  # SELL
                new_qty = cur_qty - qty
                if new_qty < 0:
                    new_qty = 0.0
                new_avg = cur_avg  # avg_cost ne bouge pas sur sell

            if new_qty == 0:
                cur.execute(
                    "DELETE FROM portfolio_positions WHERE instrument_id = ?",
                    (instrument_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE portfolio_positions
                    SET quantity = ?, avg_cost = ?, current_price = ?, updated_at = ?
                    WHERE instrument_id = ?
                    """,
                    (new_qty, new_avg, current_price, now, instrument_id),
                )
        except sqlite3.Error as e:
            if self.verbose:
                print(f"           WARN upsert position: {e}")

    def _update_cash(self, conn_replay: sqlite3.Connection, side: str, notional: float):
        """BUY decremente cash, SELL incremente cash."""
        try:
            sign = -1.0 if side == "BUY" else 1.0
            now = datetime.now().isoformat(timespec="seconds")
            conn_replay.execute(
                """
                UPDATE portfolio_state
                SET cash = cash + ?, updated_at = ?
                WHERE id = 1
                """,
                (sign * notional, now),
            )
        except sqlite3.Error as e:
            if self.verbose:
                print(f"           WARN update cash: {e}")

    def _compute_nav_and_update_state(
        self, conn_replay: sqlite3.Connection, day_t: str,
    ) -> Dict[str, Any]:
        """
        Recalcule NAV = cash + sum(qty * close_day_t pour chaque position).
        Met a jour portfolio_state et upsert portfolio_history :memory:.
        """
        out = {
            "nav": self.initial_capital, "cash": self.initial_capital,
            "positions_value": 0.0, "n_positions": 0,
            "total_pnl": 0.0, "total_pnl_pct": 0.0,
        }
        try:
            cur = conn_replay.cursor()
            cash_row = cur.execute(
                "SELECT cash FROM portfolio_state WHERE id=1"
            ).fetchone()
            cash = float(cash_row[0]) if cash_row and cash_row[0] is not None else self.initial_capital

            pos_rows = cur.execute(
                """
                SELECT pp.instrument_id, i.ticker, pp.quantity, pp.avg_cost
                FROM portfolio_positions pp
                JOIN instruments i ON i.id = pp.instrument_id
                WHERE pp.quantity > 0
                """
            ).fetchall()

            positions_value = 0.0
            n_positions = 0
            # Refresh current_price + unrealized_pnl + weight_pct par position
            for (instr_id, ticker, qty, avg_cost) in pos_rows:
                close_t = self._get_close_at(conn_replay, ticker, day_t)
                if close_t is None or close_t <= 0:
                    continue
                pos_val = float(qty) * close_t
                positions_value += pos_val
                n_positions += 1
                unreal = (close_t - float(avg_cost or 0.0)) * float(qty)
                # NAV partiel pour weight_pct (sera affine apres calcul total)
                cur.execute(
                    """
                    UPDATE portfolio_positions
                    SET current_price = ?, unrealized_pnl = ?
                    WHERE instrument_id = ?
                    """,
                    (close_t, unreal, instr_id),
                )

            nav = cash + positions_value
            total_pnl = nav - self.initial_capital
            total_pnl_pct = (total_pnl / self.initial_capital) * 100.0 if self.initial_capital > 0 else 0.0

            # Update weight_pct par position avec NAV total
            if nav > 0:
                cur.execute(
                    """
                    UPDATE portfolio_positions
                    SET weight_pct = (quantity * current_price) / ? * 100.0
                    WHERE quantity > 0
                    """,
                    (nav,),
                )

            # Update portfolio_state
            now = datetime.now().isoformat(timespec="seconds")
            cur.execute(
                """
                UPDATE portfolio_state
                SET cash = ?, total_value = ?, total_pnl = ?, total_pnl_pct = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (cash, nav, total_pnl, total_pnl_pct, now),
            )

            # Upsert portfolio_history :memory: (UNIQUE date)
            cur.execute(
                """
                INSERT INTO portfolio_history (date, total_value, cash, total_pnl)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                  total_value = excluded.total_value,
                  cash = excluded.cash,
                  total_pnl = excluded.total_pnl
                """,
                (day_t, nav, cash, total_pnl),
            )
            conn_replay.commit()

            out.update({
                "nav": nav, "cash": cash, "positions_value": positions_value,
                "n_positions": n_positions, "total_pnl": total_pnl,
                "total_pnl_pct": total_pnl_pct,
            })
        except sqlite3.Error as e:
            if self.verbose:
                print(f"           ERR compute_nav: {e}")
        return out

    # ---------- Exports 8B.3 ----------

    def _insert_replay_order(
        self, conn_replay: sqlite3.Connection,
        cycle_id_replay: int, day_t: str, cycle_id_prod: str, ticker: str,
        side: str, qty: float, qty_target: float, qty_current: float,
        target_pct: float, status: str, fill_price: Optional[float],
        slippage: Optional[float], price_close: Optional[float],
        nav_before: float, risk_json: str, rejection: Optional[str],
    ) -> int:
        """Insere directement dans replay_orders (prod DB)."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO replay_orders
                  (run_id, cycle_id_replay, day_t, cycle_id_prod, ticker, side, qty,
                   qty_target, qty_current, target_weight_pct, status, fill_price,
                   slippage_bps, price_close_t, nav_before, risk_check_json,
                   rejection_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id, cycle_id_replay, day_t, cycle_id_prod, ticker, side,
                    qty, qty_target, qty_current, target_pct, status, fill_price,
                    slippage, price_close, nav_before, risk_json, rejection,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            order_id = cur.lastrowid
            conn.commit()
            return order_id
        finally:
            conn.close()

    def _export_orders(
        self, conn_replay: sqlite3.Connection, cycle_id_replay: int, day_t: str,
    ) -> int:
        # replay_orders est deja rempli par _insert_replay_order au moment du trade.
        # On retourne juste le count pour le log.
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM replay_orders WHERE cycle_id_replay = ?",
                (cycle_id_replay,),
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def _export_fills(
        self, conn_replay: sqlite3.Connection, cycle_id_replay: int, day_t: str,
    ) -> int:
        """Copie fills :memory: -> replay_fills."""
        try:
            rows = conn_replay.execute(
                """
                SELECT f.order_id, o.cycle_id, i.ticker, o.side,
                       f.fill_price, f.fill_quantity, f.slippage, f.fees, f.filled_at
                FROM fills f
                JOIN orders o ON o.id = f.order_id
                JOIN instruments i ON i.id = o.instrument_id
                """
            ).fetchall()
        except sqlite3.Error:
            return 0
        if not rows:
            return 0
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            cur = conn.cursor()
            n = 0
            for (oid, cid_prod, ticker, side, fprice, fqty, slip, fees, filled_at) in rows:
                notional = float(fqty) * float(fprice) if fprice else 0.0
                cur.execute(
                    """
                    INSERT INTO replay_fills
                      (run_id, cycle_id_replay, day_t, day_fill, ticker, side,
                       fill_price, fill_quantity, open_j1, slippage_bps, fees,
                       notional, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.run_id, cycle_id_replay, day_t, filled_at, ticker, side,
                        fprice, fqty, fprice, slip, fees or 0, notional,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                n += 1
            conn.commit()
            return n
        finally:
            conn.close()

    def _export_positions(
        self, conn_replay: sqlite3.Connection, cycle_id_replay: int, day_t: str,
    ) -> int:
        """Snapshot final positions :memory: -> replay_positions."""
        try:
            rows = conn_replay.execute(
                """
                SELECT i.ticker, pp.quantity, pp.avg_cost, pp.current_price,
                       pp.weight_pct, pp.unrealized_pnl
                FROM portfolio_positions pp
                JOIN instruments i ON i.id = pp.instrument_id
                WHERE pp.quantity > 0
                """
            ).fetchall()
        except sqlite3.Error:
            return 0
        if not rows:
            return 0
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            cur = conn.cursor()
            n = 0
            for (ticker, qty, avg_cost, current_price, weight, unreal) in rows:
                cur.execute(
                    """
                    INSERT INTO replay_positions
                      (run_id, cycle_id_replay, day_t, ticker, quantity,
                       avg_cost, current_price, weight_pct, unrealized_pnl, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.run_id, cycle_id_replay, day_t, ticker, qty,
                        avg_cost, current_price, weight, unreal,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                n += 1
            conn.commit()
            return n
        finally:
            conn.close()

    def _insert_nav_history(
        self, cycle_id_replay: int, day_t: str, nav: float, cash: float,
        positions_value: float, n_positions: int, n_orders: int, n_fills: int,
    ):
        """INSERT replay_nav_history avec daily_pnl par diff vs cycle precedent."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            # Lit le NAV du cycle precedent du meme run pour calculer daily_pnl
            prev_row = conn.execute(
                """
                SELECT nav FROM replay_nav_history
                WHERE run_id = ?
                ORDER BY day_t DESC LIMIT 1
                """,
                (self.run_id,),
            ).fetchone()
            prev_nav = float(prev_row[0]) if prev_row else self.initial_capital
            daily_pnl = nav - prev_nav
            daily_pnl_pct = (daily_pnl / prev_nav) * 100.0 if prev_nav > 0 else 0.0
            cumul_pnl = nav - self.initial_capital
            cumul_pnl_pct = (cumul_pnl / self.initial_capital) * 100.0

            conn.execute(
                """
                INSERT INTO replay_nav_history
                  (run_id, cycle_id_replay, day_t, nav, cash, positions_value,
                   daily_pnl, daily_pnl_pct, cumul_pnl, cumul_pnl_pct,
                   n_positions, n_orders, n_fills, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, day_t) DO UPDATE SET
                  nav = excluded.nav, cash = excluded.cash,
                  positions_value = excluded.positions_value,
                  daily_pnl = excluded.daily_pnl, daily_pnl_pct = excluded.daily_pnl_pct,
                  cumul_pnl = excluded.cumul_pnl, cumul_pnl_pct = excluded.cumul_pnl_pct,
                  n_positions = excluded.n_positions, n_orders = excluded.n_orders,
                  n_fills = excluded.n_fills
                """,
                (
                    self.run_id, cycle_id_replay, day_t, nav, cash, positions_value,
                    daily_pnl, daily_pnl_pct, cumul_pnl, cumul_pnl_pct,
                    n_positions, n_orders, n_fills,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    # ---------- Boucle haute ----------

    def run(self, max_cycles: Optional[int] = None) -> Dict[str, Any]:
        """Joue la boucle complete sur la fenetre. max_cycles pour debug."""
        cal = trading_calendar(self.window_start, self.window_end)
        if max_cycles is not None:
            cal = cal[:max_cycles]

        self.open_run()
        try:
            for seq, day_t in enumerate(cal, start=1):
                self.run_cycle(day_t, seq)
            self.close_run("done")
            return {"run_id": self.run_id, "cycles": len(cal), "status": "done"}
        except Exception:
            self.close_run("error")
            raise


__all__ = ["ReplayOrchestrator", "trading_calendar"]
