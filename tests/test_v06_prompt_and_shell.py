from __future__ import annotations

from pathlib import Path

from agent_os.cancellation import CancellationToken
from agent_os.prompts import PromptBuilder
from agent_os.session import QuestionBroker, SessionMemory
from agent_os.shell import COMMANDS


class Launcher:
    def available_aliases(self):
        return ["notepad"]


class Dummy:
    capture_source = "screen"

    def model_dump(self):
        return {}


class Observation:
    capture_token = "token"
    target = Dummy()
    monitors = []
    windows = []
    state = {}
    uia = type("U", (), {"elements": []})()


class Lease:
    def as_dict(self):
        return {"lease": "x"}


def test_prompt_includes_persistent_session_context(tmp_path: Path) -> None:
    (tmp_path / "system.md").write_text("system", encoding="utf-8")
    (tmp_path / "verifier.md").write_text("verify", encoding="utf-8")
    builder = PromptBuilder(tmp_path, Launcher())
    prompt = builder.build_step_prompt(
        "continue", 1, Observation(), Lease(), [], [], None, [],
        type("W", (), {"hwnd": 1, "title": "x", "process_name": "p"})(),
        True, {}, [{"task": "open site", "summary": "site opened"}],
    )
    assert "persistent_session_context" in prompt
    assert "site opened" in prompt


def test_session_memory_is_bounded() -> None:
    memory = SessionMemory(limit=2)
    memory.add("one", True, "1", "r1")
    memory.add("two", True, "2", "r2")
    memory.add("three", True, "3", "r3")
    assert [item["task"] for item in memory.context()] == ["two", "three"]


def test_shell_exposes_required_commands() -> None:
    for command in ("/models", "/model", "/key", "/queue", "/cancel", "/set"):
        assert command in COMMANDS


def test_question_broker_does_not_leave_stop_for_future_question() -> None:
    broker = QuestionBroker(CancellationToken())
    broker.cancel()
    assert broker.pending_question is None
    assert broker._answer.empty()
