from __future__ import annotations

import inspect

from agent_os.shell_v3 import WindowsAgentShell, parse_submission


def test_multiline_slash_commands_are_split_into_entries() -> None:
    mode, entries = parse_submission(
        "/set control browser\n"
        "/set physical deny\n"
        "/set cursor virtual\n"
        "/set overlay on\n"
    )

    assert mode == "entries"
    assert entries == [
        "/set control browser",
        "/set physical deny",
        "/set cursor virtual",
        "/set overlay on",
    ]


def test_multiline_task_without_commands_remains_one_task() -> None:
    text = "Open the event page.\nSelect the timezone.\nStop after selection."

    mode, entries = parse_submission(text)

    assert mode == "task"
    assert entries == [text]


def test_mixed_paste_keeps_command_and_task_order() -> None:
    mode, entries = parse_submission(
        "/set control browser\n"
        "Open app.defytickets.co\n"
        "/status\n"
    )

    assert mode == "entries"
    assert entries == [
        "/set control browser",
        "Open app.defytickets.co",
        "/status",
    ]


def test_blank_lines_are_ignored_for_command_blocks() -> None:
    mode, entries = parse_submission("\n/set physical deny\n\n/set overlay on\n")

    assert mode == "entries"
    assert entries == ["/set physical deny", "/set overlay on"]


def test_shell_enables_multiline_prompt_and_custom_enter_binding() -> None:
    source = inspect.getsource(WindowsAgentShell.run)

    assert "multiline=True" in source
    assert "key_bindings=self._input_bindings" in source
