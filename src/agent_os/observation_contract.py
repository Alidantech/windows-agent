from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from agent_os.capture import CapturedObservation
    from agent_os.lease import TargetLease

ObservationStatus = Literal["fresh", "consumed", "expired"]


class ObservationContractError(RuntimeError):
    """Raised when an action is not bound to a current, unused observation."""


@dataclass(frozen=True)
class ObservationIdentity:
    observation_id: str
    generation: int
    lease_id: str | None
    lease_generation: int
    target_fingerprint: str
    captured_monotonic: float

    def as_dict(self) -> dict[str, object]:
        return {
            "observation_id": self.observation_id,
            "generation": self.generation,
            "lease_id": self.lease_id,
            "lease_generation": self.lease_generation,
            "target_fingerprint": self.target_fingerprint,
            "captured_monotonic": self.captured_monotonic,
        }


class ObservationLedger:
    """Issue single-use observation identities and reject stale or replayed actions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generation = 0

    @staticmethod
    def _target_fingerprint(observation: CapturedObservation) -> str:
        target = observation.target
        window = next(
            (item for item in observation.windows if item.hwnd == target.hwnd),
            None,
        )
        payload = {
            "backend": target.backend,
            "identity": target.identity,
            "url": target.url,
            "hwnd": target.hwnd,
            "process_id": window.process_id if window else None,
            "process_name": window.process_name if window else None,
            "rect": target.rect.model_dump(),
            "lease_id": target.lease_id,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:24]

    def stamp(
        self,
        observation: CapturedObservation,
        *,
        lease_generation: int = 0,
    ) -> ObservationIdentity:
        with self._lock:
            self._generation += 1
            generation = self._generation
        identity = ObservationIdentity(
            observation_id=f"obs-{generation:06d}-{uuid.uuid4().hex[:8]}",
            generation=generation,
            lease_id=observation.target.lease_id,
            lease_generation=lease_generation,
            target_fingerprint=self._target_fingerprint(observation),
            captured_monotonic=time.monotonic(),
        )
        observation.state["observation_contract"] = {
            **identity.as_dict(),
            "status": "fresh",
            "consumed_by": None,
            "consumed_monotonic": None,
        }
        return identity

    @staticmethod
    def context(observation: CapturedObservation) -> dict[str, object]:
        contract = observation.state.get("observation_contract")
        return dict(contract) if isinstance(contract, dict) else {}

    @classmethod
    def observation_id(cls, observation: CapturedObservation) -> str | None:
        value = cls.context(observation).get("observation_id")
        return str(value) if value else None

    @classmethod
    def assert_fresh(
        cls,
        observation: CapturedObservation,
        lease: TargetLease,
        *,
        requested_observation_id: str | None = None,
    ) -> dict[str, object]:
        contract = observation.state.get("observation_contract")
        if not isinstance(contract, dict):
            raise ObservationContractError(
                "The action has no observation contract. Capture a fresh state before acting."
            )
        observation_id = str(contract.get("observation_id") or "")
        if requested_observation_id and requested_observation_id != observation_id:
            raise ObservationContractError(
                f"Action observation {requested_observation_id!r} does not match current "
                f"observation {observation_id!r}. Replan from the fresh state."
            )
        if contract.get("status") != "fresh":
            raise ObservationContractError(
                f"Observation {observation_id or '<unknown>'} was already consumed. "
                "Element indexes, screenshot coordinates, focus, and modal state must be "
                "re-observed before another action."
            )
        if contract.get("lease_id") != lease.lease_id:
            raise ObservationContractError(
                "Observation/control lease mismatch. No input was sent."
            )
        if int(contract.get("lease_generation") or 0) != int(lease.generation):
            raise ObservationContractError(
                "The target lease changed after this observation. Capture the newly bound target."
            )
        target_fingerprint = cls._target_fingerprint(observation)
        if contract.get("target_fingerprint") != target_fingerprint:
            raise ObservationContractError(
                "The observed target identity changed before execution. Re-observe the target."
            )
        return contract

    @classmethod
    def consume(
        cls,
        observation: CapturedObservation,
        lease: TargetLease,
        *,
        action: str,
        requested_observation_id: str | None = None,
    ) -> str:
        contract = cls.assert_fresh(
            observation,
            lease,
            requested_observation_id=requested_observation_id,
        )
        observation_id = str(contract["observation_id"])
        contract["status"] = "consumed"
        contract["consumed_by"] = action
        contract["consumed_monotonic"] = time.monotonic()
        return observation_id


STATE_CHANGING_ACTIONS = {
    "click",
    "double_click",
    "right_click",
    "click_element",
    "fill_element",
    "select_option",
    "type_text",
    "press_key",
    "hotkey",
    "scroll",
    "launch_app",
    "open_url",
    "activate_window",
    "smoke_test_site",
}


def is_state_changing(action: str) -> bool:
    return action in STATE_CHANGING_ACTIONS
