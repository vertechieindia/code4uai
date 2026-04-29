"""Chaos Agent — Resilience Testing via Controlled Disruption.

Implements chaos engineering for the AI Swarm by injecting:
- Process termination (SIGTERM to worker PIDs)
- Latency injection (artificial delays in stage execution)
- Memory pressure simulation
- Network partition simulation

The GauntletOrchestrator detects these "System Faults" and retries
without losing validation state.
"""

from __future__ import annotations

import os
import random
import signal
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("chaos_agent")


class FaultType(str, Enum):
    """Types of chaos faults that can be injected."""
    PROCESS_KILL = "process_kill"
    LATENCY_INJECTION = "latency_injection"
    MEMORY_PRESSURE = "memory_pressure"
    STAGE_CORRUPTION = "stage_corruption"
    NETWORK_PARTITION = "network_partition"


@dataclass
class ChaosEvent:
    """Record of a single chaos event."""
    event_id: str
    fault_type: FaultType
    target: str
    injected_at: float
    resolved_at: Optional[float] = None
    recovered: bool = False
    recovery_time_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eventId": self.event_id,
            "faultType": self.fault_type.value,
            "target": self.target,
            "injectedAt": self.injected_at,
            "resolvedAt": self.resolved_at,
            "recovered": self.recovered,
            "recoveryTimeMs": round(self.recovery_time_ms, 2),
            "details": self.details,
        }


@dataclass
class ChaosReport:
    """Aggregated chaos test report."""
    total_faults: int = 0
    recovered: int = 0
    failed: int = 0
    avg_recovery_ms: float = 0.0
    max_recovery_ms: float = 0.0
    events: List[ChaosEvent] = field(default_factory=list)
    resilience_score: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "totalFaults": self.total_faults,
            "recovered": self.recovered,
            "failed": self.failed,
            "avgRecoveryMs": round(self.avg_recovery_ms, 2),
            "maxRecoveryMs": round(self.max_recovery_ms, 2),
            "resilienceScore": round(self.resilience_score, 1),
            "events": [e.to_dict() for e in self.events],
        }


class ChaosAgent:
    """Injects controlled chaos into the AI swarm to test resilience."""

    def __init__(self, enabled: bool = False, intensity: float = 0.3) -> None:
        self.enabled = enabled
        self.intensity = max(0.0, min(1.0, intensity))
        self._events: List[ChaosEvent] = []
        self._event_counter = 0

    def _next_id(self) -> str:
        self._event_counter += 1
        return f"chaos-{self._event_counter}-{int(time.time() * 1000) % 100000}"

    def should_inject(self) -> bool:
        """Decide probabilistically whether to inject a fault."""
        if not self.enabled:
            return False
        return random.random() < self.intensity

    def inject_latency(self, target: str = "stage_execution", min_ms: int = 500, max_ms: int = 3000) -> ChaosEvent:
        """Inject artificial latency into a process."""
        delay_ms = random.randint(min_ms, max_ms)
        event = ChaosEvent(
            event_id=self._next_id(),
            fault_type=FaultType.LATENCY_INJECTION,
            target=target,
            injected_at=time.time(),
            details={"delayMs": delay_ms},
        )
        logger.info("chaos_latency_injected", target=target, delay_ms=delay_ms)
        time.sleep(delay_ms / 1000.0)
        event.resolved_at = time.time()
        event.recovered = True
        event.recovery_time_ms = delay_ms
        self._events.append(event)
        return event

    def inject_process_kill(self, pid: Optional[int] = None, target: str = "worker") -> ChaosEvent:
        """Simulate process termination. If pid is None, records a simulated kill."""
        event = ChaosEvent(
            event_id=self._next_id(),
            fault_type=FaultType.PROCESS_KILL,
            target=target,
            injected_at=time.time(),
            details={"pid": pid, "signal": "SIGTERM"},
        )

        if pid and pid != os.getpid():
            try:
                os.kill(pid, signal.SIGTERM)
                logger.warning("chaos_process_killed", pid=pid, target=target)
                event.details["actualKill"] = True
            except (ProcessLookupError, PermissionError) as e:
                logger.info("chaos_process_kill_skipped", pid=pid, error=str(e))
                event.details["actualKill"] = False
                event.details["error"] = str(e)
        else:
            event.details["actualKill"] = False
            event.details["simulated"] = True
            logger.info("chaos_process_kill_simulated", target=target)

        event.resolved_at = time.time()
        event.recovery_time_ms = (event.resolved_at - event.injected_at) * 1000
        self._events.append(event)
        return event

    def inject_stage_corruption(self, stage_name: str) -> ChaosEvent:
        """Simulate a stage returning corrupted/partial results."""
        event = ChaosEvent(
            event_id=self._next_id(),
            fault_type=FaultType.STAGE_CORRUPTION,
            target=stage_name,
            injected_at=time.time(),
            details={"corruptionType": random.choice(["partial_result", "timeout", "invalid_output"])},
        )
        logger.info("chaos_stage_corruption", stage=stage_name, corruption=event.details["corruptionType"])
        event.resolved_at = time.time()
        self._events.append(event)
        return event

    def inject_memory_pressure(self, target: str = "system", mb_to_allocate: int = 50) -> ChaosEvent:
        """Simulate memory pressure by recording a simulated allocation."""
        event = ChaosEvent(
            event_id=self._next_id(),
            fault_type=FaultType.MEMORY_PRESSURE,
            target=target,
            injected_at=time.time(),
            details={"simulatedMB": mb_to_allocate, "simulated": True},
        )
        logger.info("chaos_memory_pressure", target=target, mb=mb_to_allocate)
        event.resolved_at = time.time()
        event.recovered = True
        event.recovery_time_ms = 0
        self._events.append(event)
        return event

    def inject_network_partition(self, target: str = "llm_provider", duration_ms: int = 2000) -> ChaosEvent:
        """Simulate network partition by sleeping (simulating unavailable service)."""
        event = ChaosEvent(
            event_id=self._next_id(),
            fault_type=FaultType.NETWORK_PARTITION,
            target=target,
            injected_at=time.time(),
            details={"durationMs": duration_ms, "simulated": True},
        )
        logger.info("chaos_network_partition", target=target, duration_ms=duration_ms)
        time.sleep(min(duration_ms / 1000.0, 5.0))
        event.resolved_at = time.time()
        event.recovered = True
        event.recovery_time_ms = duration_ms
        self._events.append(event)
        return event

    def run_chaos_round(self, targets: Optional[List[str]] = None) -> List[ChaosEvent]:
        """Run a round of random chaos injections."""
        if not self.enabled:
            return []

        targets = targets or ["stage_core", "stage_functional", "stage_system", "stage_nonfunctional", "stage_security", "llm_provider", "worker_1", "worker_2"]
        events: List[ChaosEvent] = []
        fault_types = list(FaultType)

        for target in targets:
            if random.random() < self.intensity:
                fault = random.choice(fault_types)
                if fault == FaultType.LATENCY_INJECTION:
                    events.append(self.inject_latency(target, 200, 1500))
                elif fault == FaultType.PROCESS_KILL:
                    events.append(self.inject_process_kill(None, target))
                elif fault == FaultType.STAGE_CORRUPTION:
                    events.append(self.inject_stage_corruption(target))
                elif fault == FaultType.MEMORY_PRESSURE:
                    events.append(self.inject_memory_pressure(target))
                elif fault == FaultType.NETWORK_PARTITION:
                    events.append(self.inject_network_partition(target, 1000))

        return events

    def get_report(self) -> ChaosReport:
        """Generate aggregated chaos report."""
        events = list(self._events)
        total = len(events)
        recovered = sum(1 for e in events if e.recovered)
        failed = total - recovered
        recovery_times = [e.recovery_time_ms for e in events if e.recovered and e.recovery_time_ms > 0]
        avg_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 0.0
        max_recovery = max(recovery_times) if recovery_times else 0.0
        resilience = (recovered / total * 100) if total > 0 else 100.0

        return ChaosReport(
            total_faults=total,
            recovered=recovered,
            failed=failed,
            avg_recovery_ms=avg_recovery,
            max_recovery_ms=max_recovery,
            events=events,
            resilience_score=resilience,
        )

    def get_events(self) -> List[ChaosEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
        self._event_counter = 0

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        logger.info("chaos_mode_toggled", enabled=enabled)

    def set_intensity(self, intensity: float) -> None:
        self.intensity = max(0.0, min(1.0, intensity))


_chaos_singleton: Optional[ChaosAgent] = None


def get_chaos_agent() -> ChaosAgent:
    global _chaos_singleton
    if _chaos_singleton is None:
        _chaos_singleton = ChaosAgent()
    return _chaos_singleton
