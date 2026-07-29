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


def test_blocks_non_http_url() -> None:
    decision = AgentDecision(action="open_url", url="file:///C:/secret.txt", reason="open file")
    assessment = SafetyPolicy(confirm_risky=True).assess(decision)
    assert not assessment.allowed


def test_allows_https_url() -> None:
    decision = AgentDecision(action="open_url", url="https://chatgpt.com", reason="open site")
    assessment = SafetyPolicy(confirm_risky=True).assess(decision)
    assert assessment.allowed


def test_blocks_non_http_smoke_target() -> None:
    decision = AgentDecision(action="smoke_test_site", url="file:///C:/", reason="test")
    assessment = SafetyPolicy(confirm_risky=True).assess(decision)
    assert not assessment.allowed
