"""
Infrastruktur (operational infrastructure) indicators for FMI simulation.

These indicators measure the operational resilience and capacity utilisation
of the payment system infrastructure, including system availability, incident
recovery times, and utilisation rates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Sequence


IncidentStatus = Literal["below_rto", "rto", "mtpd", ">mtpd"]


@dataclass
class IncidentRecord:
    """A single infrastructure incident record.

    Attributes
    ----------
    timestamp:
        Date/time at which the incident started.
    duration_minutes:
        Total duration of the incident in minutes.
    severity:
        Qualitative severity label (e.g. ``'low'``, ``'medium'``, ``'high'``).
    affected_system:
        Name or identifier of the system affected by the incident (e.g.
        ``'rtgs'``, ``'fast'``, ``'raja'``).
    """

    timestamp: datetime
    duration_minutes: float
    severity: str
    affected_system: str


def compute_incidents(
    incidents: Sequence[IncidentRecord],
    rto_minutes: float = 60.0,
    mtpd_minutes: float = 240.0,
) -> dict[str, Any]:
    """Analyse a collection of incident records against RTO and MTPD targets.

    For each incident the worst-case recovery target breached is identified.
    The function also returns aggregate statistics across all incidents.

    Recovery target categories:

    * ``'below_rto'`` — incident resolved within the Recovery Time Objective.
    * ``'rto'``       — incident duration exceeded RTO but within MTPD.
    * ``'mtpd'``      — incident duration is exactly at or very close to MTPD
                        (within a 10-minute tolerance).
    * ``'>mtpd'``     — incident duration exceeded the Maximum Tolerable Period
                        of Disruption.

    Parameters
    ----------
    incidents:
        Sequence of :class:`IncidentRecord` instances to analyse.
    rto_minutes:
        Recovery Time Objective in minutes.  Default 60.
    mtpd_minutes:
        Maximum Tolerable Period of Disruption in minutes. Default 240.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:

        * ``total_incidents``  — int: total number of incidents.
        * ``per_incident``     — list[dict]: per-incident details including
          ``timestamp``, ``duration_minutes``, ``severity``,
          ``affected_system``, and ``status``.
        * ``status_counts``    — dict[str, int]: counts per status category.
        * ``max_duration``     — float: maximum single-incident duration.
        * ``mean_duration``    — float: mean incident duration.
        * ``rto_breach_rate``  — float: proportion of incidents that exceeded
          RTO (0–1).

    Examples
    --------
    >>> from datetime import datetime
    >>> inc = IncidentRecord(datetime(2024, 1, 1), 30.0, 'low', 'rtgs')
    >>> result = compute_incidents([inc])
    >>> result['per_incident'][0]['status']
    'below_rto'
    """
    per_incident: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {
        "below_rto": 0,
        "rto": 0,
        "mtpd": 0,
        ">mtpd": 0,
    }

    durations: list[float] = []

    for inc in incidents:
        dur = inc.duration_minutes
        durations.append(dur)

        if dur > mtpd_minutes:
            status: IncidentStatus = ">mtpd"
        elif dur >= mtpd_minutes - 10:
            # Within 10-minute tolerance window of MTPD boundary
            status = "mtpd"
        elif dur > rto_minutes:
            status = "rto"
        else:
            status = "below_rto"

        status_counts[status] += 1

        per_incident.append(
            {
                "timestamp": inc.timestamp,
                "duration_minutes": dur,
                "severity": inc.severity,
                "affected_system": inc.affected_system,
                "status": status,
            }
        )

    total = len(incidents)
    max_duration = max(durations) if durations else 0.0
    mean_duration = sum(durations) / total if total > 0 else 0.0
    rto_breaches = status_counts["rto"] + status_counts["mtpd"] + status_counts[">mtpd"]
    rto_breach_rate = rto_breaches / total if total > 0 else 0.0

    return {
        "total_incidents": total,
        "per_incident": per_incident,
        "status_counts": status_counts,
        "max_duration": max_duration,
        "mean_duration": mean_duration,
        "rto_breach_rate": rto_breach_rate,
    }


def compute_system_utilization(
    actual_load: float,
    max_capacity: float,
) -> float:
    """Compute the system utilisation rate as a percentage.

    Formula::

        utilization = (actual_load / max_capacity) * 100

    Parameters
    ----------
    actual_load:
        Current system load (transactions per second, message volume, or
        similar throughput measure).
    max_capacity:
        Maximum rated capacity of the system under the same unit as
        ``actual_load``.

    Returns
    -------
    float
        Utilisation percentage (0–100+).  Returns 0.0 if ``max_capacity``
        is zero.

    Notes
    -----
    The threshold direction for ``system_utilization`` is ``'inc'``, meaning
    higher utilisation signals elevated operational risk.

    Examples
    --------
    >>> compute_system_utilization(270, 1000)
    27.0
    """
    if max_capacity == 0.0:
        return 0.0
    return (actual_load / max_capacity) * 100.0


def compute_system_availability(
    uptime_minutes: float,
    total_minutes: float,
) -> float:
    """Compute the system availability percentage.

    Formula::

        availability = (uptime_minutes / total_minutes) * 100

    Parameters
    ----------
    uptime_minutes:
        Total minutes the system was operational and accepting transactions.
    total_minutes:
        Total minutes in the measurement period (e.g. 510 for a standard
        8.5-hour operating day).

    Returns
    -------
    float
        Availability percentage (0–100).  Returns 100.0 if ``total_minutes``
        is zero (no period means no downtime by convention).

    Notes
    -----
    The threshold direction for ``system_availability`` is ``'dec'``, meaning
    lower availability signals greater risk.

    Examples
    --------
    >>> compute_system_availability(505, 510)
    99.01960784313725
    """
    if total_minutes == 0.0:
        return 100.0
    return (uptime_minutes / total_minutes) * 100.0


def compute_all_infrastruktur(
    tick_results: dict[str, Any],
    incidents: Sequence[IncidentRecord],
    capacity: dict[str, float],
) -> dict[str, Any]:
    """Compute all infrastructure indicators for a single simulation tick.

    Parameters
    ----------
    tick_results:
        Dictionary from the simulation tick containing at minimum:

        * ``uptime_minutes`` (float) — system uptime this tick.
        * ``total_minutes`` (float) — total minutes in the tick window.
        * ``actual_load`` (float) — actual transaction load this tick.
    incidents:
        Incident records observed during this tick or aggregated period.
    capacity:
        Dictionary containing:

        * ``max_capacity`` (float) — rated maximum system capacity.

    Returns
    -------
    dict[str, Any]
        Dictionary with keys:

        * ``system_availability`` — float: availability percentage.
        * ``system_utilization`` — float: utilisation percentage.
        * ``incident_analysis`` — dict: output of :func:`compute_incidents`.

    Examples
    --------
    >>> from datetime import datetime
    >>> result = compute_all_infrastruktur(
    ...     {'uptime_minutes': 508, 'total_minutes': 510, 'actual_load': 270},
    ...     [],
    ...     {'max_capacity': 1000},
    ... )
    >>> 'system_availability' in result
    True
    """
    uptime = float(tick_results.get("uptime_minutes", 0.0))
    total_mins = float(tick_results.get("total_minutes", 0.0))
    actual_load = float(tick_results.get("actual_load", 0.0))
    max_cap = float(capacity.get("max_capacity", 1.0))

    availability = compute_system_availability(uptime, total_mins)
    utilization = compute_system_utilization(actual_load, max_cap)
    incident_analysis = compute_incidents(incidents)

    return {
        "system_availability": availability,
        "system_utilization": utilization,
        "incident_analysis": incident_analysis,
    }
