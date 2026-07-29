from agent_os.models import AgentDecision
from agent_os.safety import SafetyPolicy


def test_blocks_lock_hotkey() -> None:
    decision = AgentDecision(action="hotkey", keys=["win", "l"], reason="lock")
    assessment = SafetyPolicy(confirm_risky=True).assess(decision)
    assert not assessment.allowed


def test_requires_confirmation_for_run_dialog() -> None:
    decision = AgentDecision(action="hotkey", keys=["win", "r"], reason="open Run")
    assessment = SafetyPolicy(confirm_risky=True).assess(decision)
    assert assessment.allowed
    assert assessment.requires_confirmation
