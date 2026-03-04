"""
FMI Simulation Engine — Contagion package.

Public API::

    from fmi_sim.contagion import DebtRankEngine, CascadeSimulator, ContagionResult

The contagion package provides:

* :class:`DebtRankEngine` — DebtRank algorithm for systemic importance scoring.
* :class:`ContagionResult` — result container for DebtRank simulations.
* :class:`CascadeSimulator` — round-by-round cascade failure propagation.
* :class:`CascadeRound` — single-round result for cascade simulations.
"""

from .debtrank import DebtRankEngine, ContagionResult
from .cascade import CascadeSimulator, CascadeRound

__all__ = [
    "DebtRankEngine",
    "ContagionResult",
    "CascadeSimulator",
    "CascadeRound",
]
