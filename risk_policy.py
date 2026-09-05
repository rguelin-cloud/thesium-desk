# risk_policy.py
# [RISK_POLICY_CONFIG_V1]
"""Resolution de la politique de blocage risk_v2 depuis la base.

Remplace la liste blanche codee en dur de execution_engine.py
(bloc historique lignes 1348-1363, mode "hybride").

Regles cardinales
-----------------
1. Un motif de blocage inconnu ne passe JAMAIS silencieusement.
   Defaut fail-closed : 'block' en live, 'warn' en paper.
2. La politique vit en base (table risk_policy_config), pas dans le code.
   Ajuster un motif = une ligne SQL ou un appel set_policy(), pas un patch.
3. Une ligne specifique a l'environnement ('live' ou 'paper') a toujours
   priorite sur une ligne generique ('both').

Decisions de gouvernance du 2026-09-03
--------------------------------------
- stop_loss               -> block (protection non contournable)
- convergence_forced_exit -> block (sortie obligatoire)
- motif non liste         -> block en live / warn en paper (fail-closed)

Usage
-----
    from risk_policy import resolve_policy
    mode, source = resolve_policy(conn, "stop_loss", mode_env="paper")
    if mode == "block":
        risk_result["approved"] = False

Auto-test
---------
    py -3.13 risk_policy.py
"""

from __future__ import annotations

__all__ = [
    "ensure_risk_policy_table",
    "resolve_policy",
    "set_policy",
    "list_policies",
    "DEFAULT_MODE_LIVE",
    "DEFAULT_MODE_PAPER",
    "VALID_MODES",
    "VALID_SCOPES",
]

MARKER = "[RISK_POLICY_CONFIG_V1]"

# --- Defauts fail-closed -----------------------------------------------------
DEFAULT_MODE_LIVE = "block"
DEFAULT_MODE_PAPER = "warn"

VALID_MODES = ("block", "warn", "ignore")
VALID_SCOPES = ("live", "paper", "both")


# --- Schema ------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS risk_policy_config (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    blocked_by  TEXT NOT NULL,
    mode        TEXT NOT NULL CHECK(mode IN ('block','warn','ignore')),
    applies_to  TEXT NOT NULL DEFAULT 'both'
                CHECK(applies_to IN ('live','paper','both')),
    active      INTEGER NOT NULL DEFAULT 1,
    note        TEXT,
    updated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(blocked_by, applies_to)
)
"""

_INDEX = """
CREATE INDEX IF NOT EXISTS idx_risk_policy_lookup
    ON risk_policy_config(blocked_by, active, applies_to)
"""

# --- Politique initiale ------------------------------------------------------
# (blocked_by, mode, applies_to, note)
_SEED = [
    ("concentration",           "block", "both",  "Bloc dur historique, cap 15pct"),
    ("stop_loss",               "block", "both",  "Protection non contournable (decision 2026-09-03)"),
    ("convergence_forced_exit", "block", "both",  "Sortie obligatoire convergence (decision 2026-09-03)"),
    ("correlation",             "block", "live",  "Controle de portefeuille reel"),
    ("correlation",             "warn",  "paper", "Tolere en simulation, a trancher"),
    ("var_budget",              "warn",  "both",  "Cible budgetaire, depassement tolere"),
    ("var_marginal",            "warn",  "both",  "Cible budgetaire, depassement tolere"),
    ("broker_mapping_ok",       "block", "live",  "Mapping absent = pas d'execution reelle"),
    ("broker_mapping_ok",       "warn",  "paper", "Infrastructure, pas un risque portefeuille"),
]


def _normalize_env(mode_env) -> str:
    """Tout ce qui n'est pas explicitement 'live' est traite comme 'paper'."""
    return "live" if str(mode_env or "").strip().lower() == "live" else "paper"


def ensure_risk_policy_table(conn) -> bool:
    """Cree la table + l'index et injecte la politique initiale si vide.

    Idempotent : un second appel ne duplique rien.
    Ne commit pas : c'est a l'appelant de gerer la transaction.
    """
    conn.execute(_SCHEMA)
    conn.execute(_INDEX)
    count = conn.execute("SELECT COUNT(*) FROM risk_policy_config").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO risk_policy_config (blocked_by, mode, applies_to, note) "
            "VALUES (?, ?, ?, ?)",
            _SEED,
        )
    return True


def resolve_policy(conn, blocked_by, mode_env="paper"):
    """Retourne (mode, source) pour un motif de blocage donne.

    Parametres
    ----------
    conn       : connexion sqlite3 ouverte
    blocked_by : motif renvoye par risk_pretrade (ex. 'stop_loss'), ou None
    mode_env   : 'paper' (defaut) ou 'live'

    Retour
    ------
    mode   : 'block' | 'warn' | 'ignore'
    source : 'config'              -> ligne trouvee en base
             'default_fail_closed' -> motif inconnu ou base illisible
             'no_block'            -> blocked_by vide (aucun refus)

    Ne leve jamais : toute anomalie retombe sur le defaut fail-closed.
    """
    if not blocked_by:
        return ("ignore", "no_block")

    env = _normalize_env(mode_env)

    try:
        ensure_risk_policy_table(conn)
        row = conn.execute(
            "SELECT mode FROM risk_policy_config "
            "WHERE blocked_by = ? AND active = 1 "
            "  AND applies_to IN (?, 'both') "
            "ORDER BY CASE applies_to WHEN ? THEN 0 ELSE 1 END "
            "LIMIT 1",
            (str(blocked_by), env, env),
        ).fetchone()
        if row and row[0] in VALID_MODES:
            return (row[0], "config")
    except Exception:
        # Fail-closed volontaire : une base cassee ne doit pas ouvrir la vanne.
        pass

    return (
        DEFAULT_MODE_LIVE if env == "live" else DEFAULT_MODE_PAPER,
        "default_fail_closed",
    )


def set_policy(conn, blocked_by, mode, applies_to="both", note=None, active=1):
    """Cree ou met a jour la politique d'un motif. UPSERT sur (blocked_by, applies_to).

    Leve ValueError si mode ou applies_to est invalide.
    Ne commit pas : c'est a l'appelant.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode invalide: {mode!r} (attendu {VALID_MODES})")
    if applies_to not in VALID_SCOPES:
        raise ValueError(f"applies_to invalide: {applies_to!r} (attendu {VALID_SCOPES})")

    ensure_risk_policy_table(conn)
    conn.execute(
        "INSERT INTO risk_policy_config (blocked_by, mode, applies_to, active, note) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(blocked_by, applies_to) DO UPDATE SET "
        "  mode = excluded.mode, "
        "  active = excluded.active, "
        "  note = COALESCE(excluded.note, risk_policy_config.note), "
        "  updated_at = datetime('now')",
        (str(blocked_by), mode, applies_to, int(active), note),
    )
    return True


def list_policies(conn, active_only=True):
    """Retourne la politique courante : liste de tuples
    (blocked_by, mode, applies_to, active, note)."""
    ensure_risk_policy_table(conn)
    sql = (
        "SELECT blocked_by, mode, applies_to, active, note "
        "FROM risk_policy_config "
    )
    if active_only:
        sql += "WHERE active = 1 "
    sql += "ORDER BY blocked_by, applies_to"
    return list(conn.execute(sql))


# --- Auto-test ---------------------------------------------------------------
if __name__ == "__main__":
    import sqlite3

    c = sqlite3.connect(":memory:")
    ensure_risk_policy_table(c)

    failures = 0

    def check(label, got, expected):
        global failures
        ok = got == expected
        if not ok:
            failures += 1
        print("  %-52s %-24s %s" % (label, str(got), "OK" if ok else "ECHEC attendu=%s" % (expected,)))

    print(MARKER + " auto-test")
    print()
    print("--- decisions de gouvernance 2026-09-03 ---")
    check("stop_loss / paper", resolve_policy(c, "stop_loss", "paper"), ("block", "config"))
    check("stop_loss / live", resolve_policy(c, "stop_loss", "live"), ("block", "config"))
    check("convergence_forced_exit / paper", resolve_policy(c, "convergence_forced_exit", "paper"), ("block", "config"))
    check("convergence_forced_exit / live", resolve_policy(c, "convergence_forced_exit", "live"), ("block", "config"))

    print()
    print("--- motif inconnu : fail-closed ---")
    check("motif inconnu en live -> block", resolve_policy(c, "nouveau_controle_2027", "live"), ("block", "default_fail_closed"))
    check("motif inconnu en paper -> warn", resolve_policy(c, "nouveau_controle_2027", "paper"), ("warn", "default_fail_closed"))
    check("motif 'unknown' en live -> block", resolve_policy(c, "unknown", "live"), ("block", "default_fail_closed"))

    print()
    print("--- priorite env specifique sur 'both' ---")
    check("correlation / live", resolve_policy(c, "correlation", "live"), ("block", "config"))
    check("correlation / paper", resolve_policy(c, "correlation", "paper"), ("warn", "config"))
    check("broker_mapping_ok / live", resolve_policy(c, "broker_mapping_ok", "live"), ("block", "config"))
    check("broker_mapping_ok / paper", resolve_policy(c, "broker_mapping_ok", "paper"), ("warn", "config"))

    print()
    print("--- comportement conserve ---")
    check("concentration / paper", resolve_policy(c, "concentration", "paper"), ("block", "config"))
    check("var_budget / paper", resolve_policy(c, "var_budget", "paper"), ("warn", "config"))
    check("var_marginal / live", resolve_policy(c, "var_marginal", "live"), ("warn", "config"))

    print()
    print("--- cas limites ---")
    check("blocked_by=None", resolve_policy(c, None, "live"), ("ignore", "no_block"))
    check("blocked_by=''", resolve_policy(c, "", "live"), ("ignore", "no_block"))
    check("env inconnu -> paper", resolve_policy(c, "correlation", "sandbox"), ("warn", "config"))
    check("env=None -> paper", resolve_policy(c, "correlation", None), ("warn", "config"))

    print()
    print("--- idempotence du bootstrap ---")
    ensure_risk_policy_table(c)
    ensure_risk_policy_table(c)
    check("nb lignes apres 3 appels", c.execute("SELECT COUNT(*) FROM risk_policy_config").fetchone()[0], len(_SEED))

    print()
    print("--- set_policy : ajustement a chaud ---")
    set_policy(c, "correlation", "block", "paper", note="durci apres revue")
    check("correlation / paper apres durcissement", resolve_policy(c, "correlation", "paper"), ("block", "config"))
    set_policy(c, "correlation", "warn", "paper", note="retour tolerance simulation")
    check("correlation / paper restaure", resolve_policy(c, "correlation", "paper"), ("warn", "config"))
    check("pas de doublon apres 2 upserts", c.execute("SELECT COUNT(*) FROM risk_policy_config WHERE blocked_by='correlation'").fetchone()[0], 2)

    try:
        set_policy(c, "test", "passer")
        check("mode invalide rejete", "aucune exception", "ValueError")
    except ValueError:
        check("mode invalide rejete", "ValueError", "ValueError")

    print()
    print("--- desactivation -> retour au defaut ---")
    set_policy(c, "var_budget", "warn", "both", active=0)
    check("var_budget desactive / live", resolve_policy(c, "var_budget", "live"), ("block", "default_fail_closed"))
    set_policy(c, "var_budget", "warn", "both", active=1)

    print()
    print("--- politique courante ---")
    for bb, md, sc, ac, nt in list_policies(c):
        print("  %-24s %-6s %-6s active=%d  %s" % (bb, md, sc, ac, nt or ""))

    print()
    total = 24
    if failures == 0:
        print("RESULTAT : tous les tests passent. Fichier utilisable.")
    else:
        print("RESULTAT : %d ECHEC(S). Ne pas patcher execution_engine.py." % failures)
        raise SystemExit(1)
