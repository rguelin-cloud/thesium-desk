# -*- coding: utf-8 -*-
"""
bridge_config.py
NEXTONES <-> ActivTrades bridge configuration.
Cree par nextones-bridge-config-phase3.py
"""

# [NEXTONES-BRIDGE-CONFIG-PHASE3-V2]
# Phase 3 broker flags
BROKER_SHADOW_ENABLED = True  # Phase 2.5+ : shadow executor en parallele de PineConnector
BROKER_LIVE_ENABLED = False  # Phase 3C : bascule live (False = simu uniquement)
MAX_LIVE_NAV = 300.0  # Phase 3C: downgrade de 100000.0 a 300.0 (compte test 800 EUR)
BROKER_LIVE_ACCOUNT = "ACTIVTRADES"  # Broker live cible (FTMO desactive)

# [NEXTONES-BRIDGE-CONFIG-PHASE3C-V1]
# Phase 3C live router flags
LIVE_DRY_RUN = True  # Phase 3C: True=route 'live' loggee mais ordre PAS envoye au broker
MAX_LIVE_NOTIONAL_PER_ORDER = 100.0  # Phase 3C: plafond notional par ordre en EUR
LIVE_INSTRUMENTS = set()  # Phase 3C: whitelist thesium_ticker autorises en live (vide=tous shadow)
