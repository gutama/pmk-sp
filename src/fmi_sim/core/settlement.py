"""Settlement engine for FMI payment simulation."""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

import networkx as nx
import numpy as np

from .agents import Payment, PaymentStatus, PaymentUrgency


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclass
class SettlementConfig:
    """Configuration for the FMI settlement engine.

    Attributes:
        mode:                     Settlement mode: ``'rtgs'``, ``'fast'``, or ``'raja'``.
        gridlock_check_interval:  Interval in ticks between gridlock resolution runs.
        max_queue_size:           Maximum payments held across all bank queues.
        operating_start_min:      Start of operating window in minutes from midnight (default 06:00).
        operating_end_min:        End of operating window in minutes from midnight (default 17:00).
        zona1_cutoff_min:         End of Zona 1 in minutes from trading start (default 10:00).
        zona2_cutoff_min:         End of Zona 2 in minutes from trading start (default 14:00).
    """

    mode: str = "rtgs"
    gridlock_check_interval: int = 30
    max_queue_size: int = 10_000
    operating_start_min: int = 360    # 06:00
    operating_end_min: int = 1_020    # 17:00
    zona1_cutoff_min: int = 600       # 10:00
    zona2_cutoff_min: int = 840       # 14:00


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class TickResult:
    """Output of a single settlement tick.

    Attributes:
        tick:                 Tick index within the day (0-based).
        day:                  Simulation day index (1-based).
        settled_count:        Number of payments settled this tick.
        failed_count:         Number of payments that could not be settled.
        queued_count:         Number of payments remaining in the queue.
        total_value_settled:  Total IDR-billions settled this tick.
        total_value_failed:   Total IDR-billions in failed payments this tick.
        zona1_value:          Cumulative value settled in Zona 1 today.
        zona2_value:          Cumulative value settled in Zona 2 today.
        zona3_value:          Cumulative value settled in Zona 3 today.
        bank_balances:        Snapshot of each bank's balance after this tick.
    """

    tick: int
    day: int
    settled_count: int = 0
    failed_count: int = 0
    queued_count: int = 0
    total_value_settled: float = 0.0
    total_value_failed: float = 0.0
    zona1_value: float = 0.0
    zona2_value: float = 0.0
    zona3_value: float = 0.0
    bank_balances: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Priority queue entry (for heap usage)
# ---------------------------------------------------------------------------


@dataclass(order=True)
class PaymentQueueEntry:
    """Heap entry wrapping a :class:`Payment` with a numeric priority.

    ``priority`` determines ordering in the min-heap (lower = higher priority).
    ``payment`` carries the actual payment object.
    """

    priority: float
    payment: Payment = field(compare=False)


# ---------------------------------------------------------------------------
# Internal per-bank FIFO/priority queue
# ---------------------------------------------------------------------------

_URGENCY_RANK: dict[str, int] = {
    PaymentUrgency.HIGH.value: 0,
    PaymentUrgency.NORMAL.value: 1,
    PaymentUrgency.LOW.value: 2,
}


class _BankQueue:
    """Min-heap priority queue for a single bank's pending payments."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, float, str, Payment]] = []
        self._present: set[str] = set()
        self._removed: set[str] = set()
        self._counter: int = 0

    def enqueue(self, payment: Payment) -> None:
        if payment.id in self._present:
            return
        rank = _URGENCY_RANK.get(payment.urgency, 1)
        entry = (rank, payment.timestamp, payment.id, payment)
        heapq.heappush(self._heap, entry)
        self._present.add(payment.id)

    def dequeue(self) -> Payment | None:
        while self._heap:
            rank, ts, pid, pmt = heapq.heappop(self._heap)
            self._present.discard(pid)
            if pid in self._removed:
                self._removed.discard(pid)
                continue
            return pmt
        return None

    def peek(self) -> Payment | None:
        while self._heap:
            rank, ts, pid, pmt = self._heap[0]
            if pid in self._removed:
                heapq.heappop(self._heap)
                self._present.discard(pid)
                self._removed.discard(pid)
                continue
            return pmt
        return None

    def remove(self, payment_id: str) -> None:
        if payment_id in self._present:
            self._removed.add(payment_id)
            self._present.discard(payment_id)

    @property
    def pending(self) -> list[Payment]:
        result = []
        seen: set[str] = set()
        for rank, ts, pid, pmt in sorted(self._heap):
            if pid not in self._removed and pid not in seen:
                result.append(pmt)
                seen.add(pid)
        return result

    def __len__(self) -> int:
        return len(self._present)

    def is_empty(self) -> bool:
        return len(self) == 0


# ---------------------------------------------------------------------------
# Settlement Engine
# ---------------------------------------------------------------------------


class SettlementEngine:
    """Processes intraday payment batches each tick.

    Parameters
    ----------
    config:
        :class:`SettlementConfig` defining settlement behaviour.
    bank_balances:
        Mapping of bank_id (str) to opening balance in IDR billions.
        The engine maintains and mutates these balances during settlement.
    """

    def __init__(
        self,
        config: SettlementConfig,
        bank_balances: dict[str, float],
    ) -> None:
        self.config = config
        # Working copy of balances (mutated in-place during simulation)
        self._balances: dict[str, float] = dict(bank_balances)

        # Per-bank queues keyed by bank_id (str)
        self._queues: dict[str, _BankQueue] = defaultdict(_BankQueue)

        # Daily accumulators
        self._daily_settled_count: int = 0
        self._daily_failed_count: int = 0
        self._daily_value_settled: float = 0.0
        self._daily_zona_value: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}
        self._daily_submitted_value: float = 0.0

        # Tick counter within day (used to trigger gridlock checks)
        self._ticks_since_gridlock: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_tick(
        self,
        tick: int,
        day: int,
        payments: list[Payment],
        network: Any,
    ) -> TickResult:
        """Process one simulation tick.

        Parameters
        ----------
        tick:
            Current tick index within the day (0-based minutes offset).
        day:
            Current simulation day (1-based).
        payments:
            New payment orders arriving this tick.
        network:
            The :class:`~fmi_sim.core.network.PaymentNetwork` graph (used for
            adjacency lookups in gridlock resolution).

        Returns
        -------
        TickResult
        """
        # 1. Enqueue incoming payments
        for pmt in payments:
            sender_key = str(pmt.sender_id)
            pmt.status = PaymentStatus.QUEUED.value
            self._queues[sender_key].enqueue(pmt)
            self._daily_submitted_value += pmt.amount

        # 2. Bilateral offset (FAST / RAJA modes)
        if self.config.mode in ("fast", "raja"):
            self._try_offsetting_all()

        # 3. Settle according to mode
        settled_pmts, failed_pmts = self._settle_tick()

        # 4. Gridlock resolution (RTGS / RAJA modes, periodic)
        self._ticks_since_gridlock += 1
        if (
            self.config.mode in ("rtgs", "raja")
            and self._ticks_since_gridlock >= self.config.gridlock_check_interval
        ):
            self._resolve_gridlock()
            self._ticks_since_gridlock = 0
            # Drain any newly unlocked payments
            extra_settled, _ = self._settle_tick()
            settled_pmts.extend(extra_settled)

        # 5. Update accumulators
        zona = self._get_zone(tick)
        settled_value = sum(p.amount for p in settled_pmts)
        failed_value = sum(p.amount for p in failed_pmts)

        self._daily_settled_count += len(settled_pmts)
        self._daily_failed_count += len(failed_pmts)
        self._daily_value_settled += settled_value
        self._daily_zona_value[zona] = self._daily_zona_value.get(zona, 0.0) + settled_value

        # 6. Build result
        total_queued = sum(len(q) for q in self._queues.values())
        result = TickResult(
            tick=tick,
            day=day,
            settled_count=len(settled_pmts),
            failed_count=len(failed_pmts),
            queued_count=total_queued,
            total_value_settled=settled_value,
            total_value_failed=failed_value,
            zona1_value=self._daily_zona_value.get(1, 0.0),
            zona2_value=self._daily_zona_value.get(2, 0.0),
            zona3_value=self._daily_zona_value.get(3, 0.0),
            bank_balances=dict(self._balances),
        )
        return result

    def get_daily_stats(self) -> dict[str, Any]:
        """Return end-of-day statistics for the current simulation day.

        Returns
        -------
        dict with keys:
            ``settled_count``, ``failed_count``, ``value_settled``,
            ``submitted_value``, ``zona1_value``, ``zona2_value``,
            ``zona3_value``, ``throughput_zona3_pct``, ``queue_ratio``,
            ``total_queued``, ``bank_balances``.
        """
        total_queued = sum(len(q) for q in self._queues.values())
        zona3_val = self._daily_zona_value.get(3, 0.0)
        total_val = self._daily_value_settled
        tp_zona3 = (zona3_val / total_val * 100.0) if total_val > 0 else 0.0

        queued_value = sum(
            p.amount
            for q in self._queues.values()
            for p in q.pending
        )
        submitted = self._daily_submitted_value
        queue_ratio = (
            (submitted - queued_value) / submitted * 100.0
            if submitted > 0
            else 100.0
        )

        return {
            "settled_count": self._daily_settled_count,
            "failed_count": self._daily_failed_count,
            "value_settled": self._daily_value_settled,
            "submitted_value": submitted,
            "zona1_value": self._daily_zona_value.get(1, 0.0),
            "zona2_value": self._daily_zona_value.get(2, 0.0),
            "zona3_value": zona3_val,
            "throughput_zona3_pct": tp_zona3,
            "queue_ratio": queue_ratio,
            "total_queued": total_queued,
            "bank_balances": dict(self._balances),
        }

    def reset_day(self) -> None:
        """Reset daily accumulators for a new simulation day.

        Does not reset bank balances — closing balances become the opening
        balances for the next day.
        """
        self._daily_settled_count = 0
        self._daily_failed_count = 0
        self._daily_value_settled = 0.0
        self._daily_zona_value = {1: 0.0, 2: 0.0, 3: 0.0}
        self._daily_submitted_value = 0.0
        self._ticks_since_gridlock = 0
        # Clear queues (all unsettled payments are abandoned at end of day)
        self._queues = defaultdict(_BankQueue)

    # ------------------------------------------------------------------
    # Settlement primitives
    # ------------------------------------------------------------------

    def _settle(self, payment: Payment) -> bool:
        """Attempt to settle a single payment gross (debit sender, credit receiver).

        Returns True on success, False if sender has insufficient funds.
        """
        sender_key = str(payment.sender_id)
        receiver_key = str(payment.receiver_id)

        sender_balance = self._balances.get(sender_key, 0.0)
        if sender_balance < payment.amount:
            payment.status = PaymentStatus.QUEUED.value
            return False

        self._balances[sender_key] = sender_balance - payment.amount
        self._balances[receiver_key] = self._balances.get(receiver_key, 0.0) + payment.amount
        payment.status = PaymentStatus.SETTLED.value
        return True

    def _try_offsetting(self, payment: Payment) -> bool:
        """Attempt bilateral netting between a payment and its mirror in the reverse queue.

        If the receiver has a pending payment back to the original sender,
        the two payments are netted: only the positive net difference is settled,
        saving liquidity for both parties.

        Returns True if the payment was fully netted (cancelled), False otherwise.
        """
        sender_key = str(payment.sender_id)
        receiver_key = str(payment.receiver_id)
        recv_queue = self._queues.get(receiver_key)
        if recv_queue is None or recv_queue.is_empty():
            return False

        for reverse in recv_queue.pending:
            if str(reverse.receiver_id) != sender_key:
                continue

            net = payment.amount - reverse.amount

            if abs(net) < 0.01:
                # Perfect bilateral cancel — remove both
                recv_queue.remove(reverse.id)
                reverse.status = PaymentStatus.SETTLED.value
                payment.status = PaymentStatus.SETTLED.value
                # No actual balance movement needed for a perfect net-zero
                return True

            elif net > 0:
                # Sender owes more net — settle reverse at face value, reduce payment
                recv_queue.remove(reverse.id)
                reverse.status = PaymentStatus.SETTLED.value
                # Credit the net-settled reverse side
                r_sender = self._balances.get(receiver_key, 0.0)
                self._balances[receiver_key] = r_sender - reverse.amount
                self._balances[sender_key] = self._balances.get(sender_key, 0.0) + reverse.amount
                payment.amount = net
                return False  # original payment still needs settlement (at reduced amount)

            else:
                # Receiver owes more net — settle original at face value, reduce reverse
                recv_queue.remove(reverse.id)
                reverse.amount = -net
                recv_queue.enqueue(reverse)
                payment.status = PaymentStatus.SETTLED.value
                sender_bal = self._balances.get(sender_key, 0.0)
                self._balances[sender_key] = sender_bal - payment.amount
                self._balances[receiver_key] = self._balances.get(receiver_key, 0.0) + payment.amount
                return True

        return False

    def _try_offsetting_all(self) -> int:
        """Run bilateral offsetting across all pending queues.

        Returns the number of payments fully netted.
        """
        offset_count = 0
        for bank_key, queue in list(self._queues.items()):
            for pmt in list(queue.pending):
                netted = self._try_offsetting(pmt)
                if netted:
                    queue.remove(pmt.id)
                    offset_count += 1
        return offset_count

    def _settle_tick(self) -> tuple[list[Payment], list[Payment]]:
        """Execute per-tick settlement for all banks.

        Dispatches to the mode-specific algorithm.

        Returns
        -------
        tuple[list[Payment], list[Payment]]
            (settled, failed) payment lists for this tick.
        """
        if self.config.mode == "fast":
            return self._settle_fast()
        if self.config.mode == "raja":
            return self._settle_raja()
        return self._settle_rtgs()

    def _settle_rtgs(self) -> tuple[list[Payment], list[Payment]]:
        """RTGS: one-by-one gross settlement in priority order per bank."""
        settled: list[Payment] = []
        failed: list[Payment] = []
        for bank_key, queue in self._queues.items():
            while not queue.is_empty():
                pmt = queue.peek()
                if pmt is None:
                    break
                ok = self._settle(pmt)
                if ok:
                    queue.dequeue()
                    settled.append(pmt)
                else:
                    if pmt.urgency == PaymentUrgency.LOW.value:
                        # Re-queue low-urgency at tail; try next
                        queue.dequeue()
                        queue.enqueue(pmt)
                    break  # stop for this bank (preserve FIFO for high/normal)
        return settled, failed

    def _settle_fast(self) -> tuple[list[Payment], list[Payment]]:
        """BI-FAST: continuous net settlement; drain all queues each tick."""
        settled: list[Payment] = []
        failed: list[Payment] = []
        for bank_key, queue in self._queues.items():
            while not queue.is_empty():
                pmt = queue.dequeue()
                if pmt is None:
                    break
                ok = self._settle(pmt)
                if ok:
                    settled.append(pmt)
                else:
                    pmt.status = PaymentStatus.QUEUED.value
                    queue.enqueue(pmt)
                    break  # cannot process more for this bank this tick
        return settled, failed

    def _settle_raja(self) -> tuple[list[Payment], list[Payment]]:
        """RAJA: collateral-backed settlement with a small credit boost."""
        settled: list[Payment] = []
        failed: list[Payment] = []
        # RAJA allows a fraction of the current balance as intraday collateral
        collateral_pct = 0.20
        for bank_key, queue in self._queues.items():
            while not queue.is_empty():
                pmt = queue.peek()
                if pmt is None:
                    break
                ok = self._settle(pmt)
                if ok:
                    queue.dequeue()
                    settled.append(pmt)
                else:
                    # Temporary collateral boost
                    boost = self._balances.get(bank_key, 0.0) * collateral_pct
                    self._balances[bank_key] = self._balances.get(bank_key, 0.0) + boost
                    ok2 = self._settle(pmt)
                    self._balances[bank_key] = max(
                        0.0, self._balances.get(bank_key, 0.0) - boost
                    )
                    if ok2:
                        queue.dequeue()
                        settled.append(pmt)
                    else:
                        break
        return settled, failed

    # ------------------------------------------------------------------
    # Gridlock resolution
    # ------------------------------------------------------------------

    def _resolve_gridlock(self) -> None:
        """Detect and resolve payment gridlock using cycle detection.

        Algorithm:
        1. Build an obligation graph: edge (i -> j) means bank i has a pending
           payment to bank j.
        2. Find all strongly-connected components (SCCs) with ≥ 2 members.
        3. For each cycle, compute net positions and attempt simultaneous
           multilateral settlement if every net-debtor has sufficient balance.
        """
        # Build obligation graph
        obligation_graph: dict[str, set[str]] = defaultdict(set)
        payment_map: dict[tuple[str, str], list[Payment]] = defaultdict(list)

        for bank_key, queue in self._queues.items():
            for pmt in queue.pending:
                sender_k = str(pmt.sender_id)
                recv_k = str(pmt.receiver_id)
                obligation_graph[sender_k].add(recv_k)
                payment_map[(sender_k, recv_k)].append(pmt)

        if not payment_map:
            return

        # Tarjan-style SCC via networkx on a lightweight DiGraph
        try:
            import networkx as nx

            G = nx.DiGraph()
            for src, dsts in obligation_graph.items():
                for dst in dsts:
                    G.add_edge(src, dst)

            sccs = [scc for scc in nx.strongly_connected_components(G) if len(scc) >= 2]
        except Exception:
            return

        for scc in sccs:
            cycle_payments: list[Payment] = []
            for u in scc:
                for v in scc:
                    if u != v:
                        cycle_payments.extend(payment_map.get((u, v), []))

            if not cycle_payments:
                continue

            # Net positions within this cycle
            outflows: dict[str, float] = defaultdict(float)
            inflows: dict[str, float] = defaultdict(float)
            for pmt in cycle_payments:
                sk = str(pmt.sender_id)
                rk = str(pmt.receiver_id)
                outflows[sk] += pmt.amount
                inflows[rk] += pmt.amount

            # Check feasibility: every net-debtor must have sufficient balance
            feasible = True
            for bank_k in scc:
                net_out = outflows.get(bank_k, 0.0) - inflows.get(bank_k, 0.0)
                if net_out > 0:
                    if self._balances.get(bank_k, 0.0) < net_out:
                        feasible = False
                        break

            if not feasible:
                continue

            # Execute simultaneously
            for pmt in cycle_payments:
                sk = str(pmt.sender_id)
                rk = str(pmt.receiver_id)
                self._balances[sk] = self._balances.get(sk, 0.0) - pmt.amount
                self._balances[rk] = self._balances.get(rk, 0.0) + pmt.amount
                pmt.status = PaymentStatus.SETTLED.value
                self._queues[sk].remove(pmt.id)
                # Track in daily accumulators
                zona = self._get_zone(int(pmt.timestamp))
                self._daily_settled_count += 1
                self._daily_value_settled += pmt.amount
                self._daily_zona_value[zona] = self._daily_zona_value.get(zona, 0.0) + pmt.amount

    # ------------------------------------------------------------------
    # Zone helper
    # ------------------------------------------------------------------

    def _get_zone(self, tick_minutes: int) -> int:
        """Map a tick offset (minutes from trading start) to a Zona (1, 2, or 3).

        Zona 1:  start_min  – zona1_cutoff_min  (e.g. 06:00–10:00)
        Zona 2:  zona1_cutoff – zona2_cutoff_min (e.g. 10:00–14:00)
        Zona 3:  zona2_cutoff – end              (e.g. 14:00–17:00)

        Parameters
        ----------
        tick_minutes:
            Minutes offset from the start of the trading day (tick 0 = operating_start_min).

        Returns
        -------
        int
            1, 2, or 3.
        """
        abs_min = self.config.operating_start_min + tick_minutes
        if abs_min < self.config.zona1_cutoff_min:
            return 1
        if abs_min < self.config.zona2_cutoff_min:
            return 2
        return 3
