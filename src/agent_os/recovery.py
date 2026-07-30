from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecoveryBudget:
    max_repeated_strategy: int = 2
    max_unknown_outcomes: int = 1
    max_locator_recoveries: int = 2
    max_coordinate_fallbacks: int = 3
    max_consecutive_no_change: int = 2


@dataclass
class RecoveryTracker:
    budget: RecoveryBudget = field(default_factory=RecoveryBudget)
    action_signatures: dict[str, int] = field(default_factory=dict)
    unknown_outcomes: int = 0
    locator_recoveries: int = 0
    coordinate_fallbacks: int = 0
    consecutive_no_change: int = 0

    def reset(self) -> None:
        self.action_signatures.clear()
        self.unknown_outcomes = 0
        self.locator_recoveries = 0
        self.coordinate_fallbacks = 0
        self.consecutive_no_change = 0

    def before_action(self, signature: str, *, coordinate: bool) -> str | None:
        count = self.action_signatures.get(signature, 0) + 1
        self.action_signatures[signature] = count
        if count > self.budget.max_repeated_strategy:
            return (
                f"The same strategy was attempted {count} times. Stop repeating it; "
                "re-observe and choose a different semantic action or ask for guidance."
            )
        if coordinate:
            self.coordinate_fallbacks += 1
            if self.coordinate_fallbacks > self.budget.max_coordinate_fallbacks:
                return (
                    "Coordinate fallback budget was exhausted. Continue only with a semantic "
                    "element, keyboard strategy, or explicit user guidance."
                )
        return None

    def after_action(
        self,
        *,
        status: str,
        changed: bool | None,
        locator_recovered: bool = False,
    ) -> str | None:
        if status == "unknown_outcome":
            self.unknown_outcomes += 1
            if self.unknown_outcomes > self.budget.max_unknown_outcomes:
                return (
                    "Too many actions have unknown outcomes. Stop acting until the target can be "
                    "captured and verified reliably."
                )
        if locator_recovered:
            self.locator_recoveries += 1
            if self.locator_recoveries > self.budget.max_locator_recoveries:
                return (
                    "The page is replacing target elements repeatedly. Capture a fresh semantic map "
                    "and change strategy instead of continuing stale recovery."
                )
        if changed is False:
            self.consecutive_no_change += 1
        elif changed is True:
            self.consecutive_no_change = 0
        if self.consecutive_no_change > self.budget.max_consecutive_no_change:
            return (
                "Repeated actions produced no observable state change. Stop repeating them and "
                "inspect validation, focus, modality, or another target."
            )
        return None

    def snapshot(self) -> dict[str, object]:
        return {
            "unknown_outcomes": self.unknown_outcomes,
            "locator_recoveries": self.locator_recoveries,
            "coordinate_fallbacks": self.coordinate_fallbacks,
            "consecutive_no_change": self.consecutive_no_change,
            "distinct_strategies": len(self.action_signatures),
            "budget": {
                "max_repeated_strategy": self.budget.max_repeated_strategy,
                "max_unknown_outcomes": self.budget.max_unknown_outcomes,
                "max_locator_recoveries": self.budget.max_locator_recoveries,
                "max_coordinate_fallbacks": self.budget.max_coordinate_fallbacks,
                "max_consecutive_no_change": self.budget.max_consecutive_no_change,
            },
        }
