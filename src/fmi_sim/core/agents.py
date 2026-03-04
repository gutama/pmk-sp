"""
Bank agent definitions for FMI simulation.

Each BankAgent models a participant in a wholesale payment system and:
  - Generates payment orders following zona-distribution timing.
  - Decides queue management strategy (pay, hold, split, request_credit).
  - Responds to stress events.

Zona distribution (proportion of daily transactions):
  Zona 1:  00:00–03:00 (approx. first 180 min of trading)  → 25–30 %
  Zona 2:  03:00–06:00 (minutes 180–360)                   → 40–45 %
  Zona 3:  06:00+      (minutes 360+)                      → ≤ 40 %
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Enumerations & simple value types
# ---------------------------------------------------------------------------


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"
    QUEUED = "queued"
    CANCELLED = "cancelled"


class PaymentUrgency(str, Enum):
    HIGH = "high"       # time-critical (e.g. SBI, monetary policy)
    NORMAL = "normal"   # standard interbank
    LOW = "low"         # deferred / batch


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BankParams:
    """Parameters that define a bank agent's behaviour.

    Attributes:
        bank_id:              Unique numeric identifier.
        bank_type:            ``'core'`` or ``'periphery'``.
        initial_liquidity:    Opening balance in IDR billions.
        credit_limit:         Intraday credit facility in IDR billions.
        payment_frequency:    Mean payments generated per tick.
        avg_payment_size:     Mean single-payment size in IDR billions.
        payment_size_std:     Standard deviation of payment size.
        urgency_dist:         Probability mass for (high, normal, low) urgency.
        risk_appetite:        0–1 willingness to hold vs settle immediately.
        stress_sensitivity:   0–1 response intensity to stress events.
        seed:                 Per-agent random seed.
    """

    bank_id: int = 0
    bank_type: str = "periphery"  # 'core' | 'periphery'
    initial_liquidity: float = 1_000.0   # IDR bn
    credit_limit: float = 500.0          # IDR bn
    payment_frequency: float = 5.0       # mean payments / tick
    avg_payment_size: float = 50.0       # IDR bn
    payment_size_std: float = 20.0       # IDR bn
    urgency_dist: tuple[float, float, float] = (0.10, 0.75, 0.15)  # high/normal/low
    risk_appetite: float = 0.5           # 0 = conservative, 1 = aggressive
    stress_sensitivity: float = 0.5      # 0 = immune, 1 = highly reactive
    seed: int = 0


@dataclass
class Payment:
    """Represents a single payment instruction.

    Attributes:
        id:           UUID string, globally unique.
        sender_id:    Bank-ID of the paying bank.
        receiver_id:  Bank-ID of the receiving bank.
        amount:       Payment amount in IDR billions.
        timestamp:    Simulation time (minutes from start of day).
        urgency:      ``'high'``, ``'normal'``, or ``'low'``.
        system:       Payment rail: ``'rtgs'``, ``'fast'``, or ``'raja'``.
        status:       Current lifecycle state (see :class:`PaymentStatus`).
        zona:         Time zone (1, 2, or 3) derived from timestamp.
        metadata:     Arbitrary extra fields.
    """

    id: str
    sender_id: int
    receiver_id: int
    amount: float
    timestamp: float
    urgency: str
    system: str
    status: str = PaymentStatus.PENDING.value
    zona: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.zona = _timestamp_to_zona(self.timestamp)


@dataclass
class QueueAction:
    """Action decision returned by :meth:`BankAgent.decide_queue_strategy`.

    Attributes:
        action:  One of ``'pay'``, ``'hold'``, ``'split'``, ``'request_credit'``.
        params:  Action-specific parameters dict.
    """

    action: str  # 'pay' | 'hold' | 'split' | 'request_credit'
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class StressEvent:
    """External shock applied to the simulation.

    Attributes:
        event_type:      Category: ``'liquidity_shock'``, ``'credit_event'``,
                         ``'operational_outage'``, ``'market_panic'``.
        magnitude:       Severity on a 0–1 scale.
        affected_banks:  List of bank IDs directly impacted.
        timestamp:       Simulation time (minutes) when the event occurs.
        metadata:        Additional event-specific data.
    """

    event_type: str
    magnitude: float
    affected_banks: list[int]
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketState:
    """Snapshot of macro-level market conditions at a given tick.

    Attributes:
        system_liquidity:  Aggregate available liquidity across all banks (IDR bn).
        stress_level:      Current stress index on 0–1 scale.
        time_of_day_zone:  1, 2, or 3 – current zona.
        active_stress_events: List of currently active stress events.
    """

    system_liquidity: float
    stress_level: float
    time_of_day_zone: int
    active_stress_events: list[StressEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _timestamp_to_zona(timestamp: float) -> int:
    """Map a simulation minute offset to a zona (1, 2, or 3).

    Assumes a trading day starts at minute 0.
    Zona 1: minutes   0 – 179
    Zona 2: minutes 180 – 359
    Zona 3: minutes 360+
    """
    if timestamp < 180:
        return 1
    if timestamp < 360:
        return 2
    return 3


# ---------------------------------------------------------------------------
# BankAgent
# ---------------------------------------------------------------------------


class BankAgent:
    """Agent representing a single bank in the payment network.

    Parameters
    ----------
    params:
        :class:`BankParams` instance with agent configuration.
    system:
        Payment system this agent participates in: ``'rtgs'``, ``'fast'``, ``'raja'``.
    """

    # Zona share targets (proportion of daily volume generated in each zone)
    _ZONA_SHARES: dict[int, tuple[float, float]] = {
        1: (0.25, 0.30),   # 25–30 %
        2: (0.40, 0.45),   # 40–45 %
        3: (0.25, 0.35),   # remainder, ≤ 40 %
    }

    def __init__(self, params: BankParams, system: str = "rtgs") -> None:
        self.params = params
        self.system = system.lower()
        self.bank_id = params.bank_id
        self.bank_type = params.bank_type

        # Mutable state
        self.liquidity: float = params.initial_liquidity
        self.credit_used: float = 0.0
        self._stress_multiplier: float = 1.0  # altered by stress events
        self._holding_back: float = 0.0       # fraction of payments withheld

        # Random state
        self._rng = np.random.default_rng(params.seed)

        # Payment counter for unique IDs
        self._payment_counter: int = 0

        # Daily volume tracking (reset each day)
        self._daily_generated: float = 0.0
        self._zona_generated: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def available_liquidity(self) -> float:
        """Total funds available: own cash + unused credit line."""
        credit_remaining = max(0.0, self.params.credit_limit - self.credit_used)
        return self.liquidity + credit_remaining

    # ------------------------------------------------------------------
    # Payment generation
    # ------------------------------------------------------------------

    def generate_payments(
        self,
        t: float,
        market_state: MarketState,
        counterparties: list[int] | None = None,
    ) -> list[Payment]:
        """Generate a list of payment orders at simulation time *t*.

        The number of payments per tick follows a Poisson distribution
        scaled by the current stress multiplier and zona targets.

        Parameters
        ----------
        t:
            Current simulation time in minutes.
        market_state:
            Current macro state.
        counterparties:
            List of valid receiver bank IDs.  When ``None`` a dummy set is used.

        Returns
        -------
        list[Payment]
        """
        if counterparties is None or len(counterparties) == 0:
            return []

        zona = _timestamp_to_zona(t)

        # Zona-aware scaling: how intense should payment generation be right now?
        zona_scale = self._zona_intensity_scale(zona, market_state)

        # Poisson-distributed count with stress suppression
        mean_count = (
            self.params.payment_frequency
            * zona_scale
            * max(0.1, 1.0 - self._holding_back)
        )
        n_payments = int(self._rng.poisson(lam=mean(mean_count, 0)))

        payments: list[Payment] = []
        for _ in range(n_payments):
            receiver = int(self._rng.choice(counterparties))
            if receiver == self.bank_id:
                continue  # skip self-payments

            amount = self._sample_payment_size()
            urgency = self._sample_urgency()

            pid = f"B{self.bank_id:04d}_T{int(t):06d}_{self._payment_counter:04d}"
            self._payment_counter += 1

            pmt = Payment(
                id=pid,
                sender_id=self.bank_id,
                receiver_id=receiver,
                amount=amount,
                timestamp=t,
                urgency=urgency,
                system=self.system,
                status=PaymentStatus.PENDING.value,
            )
            payments.append(pmt)

            # Track daily volume
            self._daily_generated += amount
            self._zona_generated[zona] = self._zona_generated.get(zona, 0.0) + amount

        return payments

    # ------------------------------------------------------------------
    # Queue management decision
    # ------------------------------------------------------------------

    def decide_queue_strategy(
        self,
        queue: list[Payment],
        available_liquidity: float | None = None,
    ) -> QueueAction:
        """Decide how to handle queued payments given current liquidity.

        Logic
        -----
        1. If liquidity is ample (> 150 % of total queue value): pay all.
        2. If liquidity is tight (50–150 %): settle high-urgency only, hold rest.
        3. If liquidity is low (< 50 %): request credit or split.
        4. If no queue: no-op.

        Parameters
        ----------
        queue:
            List of pending :class:`Payment` objects.
        available_liquidity:
            Override for available funds.  Defaults to :attr:`available_liquidity`.

        Returns
        -------
        QueueAction
        """
        if available_liquidity is None:
            available_liquidity = self.available_liquidity

        if not queue:
            return QueueAction(action="pay", params={"payment_ids": []})

        total_queue_value = sum(p.amount for p in queue)
        high_urgency_total = sum(
            p.amount for p in queue if p.urgency == PaymentUrgency.HIGH.value
        )

        # Comfortable liquidity: settle everything
        if available_liquidity >= 1.5 * total_queue_value:
            return QueueAction(
                action="pay",
                params={
                    "payment_ids": [p.id for p in queue],
                    "reason": "ample_liquidity",
                },
            )

        # Tight liquidity: pay high-urgency, hold normal/low
        if available_liquidity >= 0.5 * total_queue_value:
            high_ids = [
                p.id for p in queue if p.urgency == PaymentUrgency.HIGH.value
            ]
            hold_ids = [
                p.id for p in queue if p.urgency != PaymentUrgency.HIGH.value
            ]
            return QueueAction(
                action="hold",
                params={
                    "pay_ids": high_ids,
                    "hold_ids": hold_ids,
                    "reason": "tight_liquidity",
                },
            )

        # Very low liquidity: request credit if possible
        credit_available = self.params.credit_limit - self.credit_used
        if credit_available >= high_urgency_total * 0.5:
            return QueueAction(
                action="request_credit",
                params={
                    "amount_needed": max(0.0, total_queue_value - available_liquidity),
                    "priority_ids": [
                        p.id for p in queue if p.urgency == PaymentUrgency.HIGH.value
                    ],
                    "reason": "insufficient_liquidity",
                },
            )

        # Last resort: split the largest payment
        largest = max(queue, key=lambda p: p.amount, default=None)
        if largest and largest.amount > 5.0:
            return QueueAction(
                action="split",
                params={
                    "payment_id": largest.id,
                    "split_amount": available_liquidity * 0.8,
                    "reason": "last_resort_split",
                },
            )

        # Cannot do anything
        return QueueAction(
            action="hold",
            params={
                "hold_ids": [p.id for p in queue],
                "reason": "no_funds",
            },
        )

    # ------------------------------------------------------------------
    # Stress response
    # ------------------------------------------------------------------

    def respond_to_stress(self, stress_event: StressEvent) -> None:
        """Update internal state in response to an external stress event.

        The agent reacts based on its :attr:`BankParams.stress_sensitivity`
        and the event type and magnitude.

        Parameters
        ----------
        stress_event:
            The :class:`StressEvent` to respond to.
        """
        if self.bank_id not in stress_event.affected_banks:
            # Indirect contagion: weaker response
            indirect_factor = 0.2
        else:
            indirect_factor = 1.0

        impact = stress_event.magnitude * self.params.stress_sensitivity * indirect_factor

        event_type = stress_event.event_type.lower()

        if event_type == "liquidity_shock":
            # Immediate liquidity drain
            shock_amount = self.liquidity * impact * 0.5
            self.liquidity = max(0.0, self.liquidity - shock_amount)
            # Precautionary hoarding
            self._holding_back = min(0.9, self._holding_back + impact * 0.4)

        elif event_type == "credit_event":
            # Counterparty fear reduces willingness to send
            self._holding_back = min(0.9, self._holding_back + impact * 0.5)
            # Reduce effective credit line
            self.credit_used += self.params.credit_limit * impact * 0.2

        elif event_type == "operational_outage":
            # Cannot generate/process payments during outage
            if impact > 0.5:
                self._holding_back = min(1.0, self._holding_back + impact * 0.8)
            else:
                self._holding_back = min(0.9, self._holding_back + impact * 0.3)

        elif event_type == "market_panic":
            # General risk-off: hoard liquidity
            self._holding_back = min(0.9, self._holding_back + impact * 0.6)
            self._stress_multiplier = max(0.1, 1.0 - impact * 0.5)

        else:
            # Unknown event: mild general impact
            self._holding_back = min(0.9, self._holding_back + impact * 0.2)

    # ------------------------------------------------------------------
    # Accounting helpers
    # ------------------------------------------------------------------

    def debit(self, amount: float) -> bool:
        """Deduct *amount* from liquidity (own funds first, then credit).

        Returns True if the debit was successful.
        """
        if self.liquidity >= amount:
            self.liquidity -= amount
            return True
        shortfall = amount - self.liquidity
        if shortfall <= (self.params.credit_limit - self.credit_used):
            self.credit_used += shortfall
            self.liquidity = 0.0
            return True
        return False

    def credit(self, amount: float) -> None:
        """Receive *amount* of funds; repay credit line first."""
        if self.credit_used > 0:
            repay = min(self.credit_used, amount)
            self.credit_used -= repay
            amount -= repay
        self.liquidity += amount

    def reset_daily_counters(self) -> None:
        """Reset daily accumulation counters (call at start of each simulated day)."""
        self._daily_generated = 0.0
        self._zona_generated = {1: 0.0, 2: 0.0, 3: 0.0}
        # Gradually reduce holding-back over time (recovery)
        self._holding_back = max(0.0, self._holding_back * 0.7)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _zona_intensity_scale(self, zona: int, market_state: MarketState) -> float:
        """Return a scaling factor based on zona timing targets.

        Ensures that the proportion of payments in each zona roughly matches
        the target shares defined in :attr:`_ZONA_SHARES`.
        """
        # Target shares define relative intensity: zona2 busiest
        intensity_map = {1: 0.27, 2: 0.42, 3: 0.31}
        base = intensity_map.get(zona, 0.33)

        # Stress level suppresses activity
        stress_suppression = max(0.1, 1.0 - market_state.stress_level * 0.5)
        return base * stress_suppression

    def _sample_payment_size(self) -> float:
        """Sample a payment amount from a lognormal distribution."""
        mu = self.params.avg_payment_size
        sigma = self.params.payment_size_std
        # Lognormal parameters from mean and std
        if sigma <= 0 or mu <= 0:
            return max(0.1, mu)
        cv = sigma / mu
        log_sigma = np.sqrt(np.log(1 + cv ** 2))
        log_mu = np.log(mu) - 0.5 * log_sigma ** 2
        return float(self._rng.lognormal(mean=log_mu, sigma=log_sigma))

    def _sample_urgency(self) -> str:
        """Sample a payment urgency level from configured distribution."""
        p_high, p_normal, p_low = self.params.urgency_dist
        draw = self._rng.uniform()
        if draw < p_high:
            return PaymentUrgency.HIGH.value
        if draw < p_high + p_normal:
            return PaymentUrgency.NORMAL.value
        return PaymentUrgency.LOW.value

    def __repr__(self) -> str:
        return (
            f"BankAgent(id={self.bank_id}, type={self.bank_type}, "
            f"liquidity={self.liquidity:.1f}, system={self.system})"
        )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def mean(a: float, b: float) -> float:
    """Return max(a, b) – used to avoid negative Poisson lambda."""
    return a if a > b else b
