from agent_os.targeting import task_allows_controller


def test_normal_app_task_protects_controller() -> None:
    assert not task_allows_controller(
        "Send a message in ChatGPT",
        "active-window",
        "760473218/17028",
    )


def test_terminal_task_allows_controller() -> None:
    assert task_allows_controller(
        "Type python --version in the terminal",
        "active-window",
        "760473218/17028",
    )
