from agent_os.models import Rectangle, WindowInfo
from agent_os.targeting import best_window_match, window_match_score


def window(title: str, process: str, hwnd: int = 1) -> WindowInfo:
    return WindowInfo(
        hwnd=hwnd,
        title=title,
        process_name=process,
        rect=Rectangle(left=0, top=0, width=1200, height=800),
    )


def test_cross_browser_title_fallback_matches_meaningful_page_title() -> None:
    brave = window("DeFy Tickets - Brave", "brave.exe")
    match = best_window_match("DeFy Tickets.*Google Chrome", [brave])
    assert match is brave


def test_exact_process_match_scores_highly() -> None:
    chrome = window("Some page - Google Chrome", "chrome.exe")
    assert window_match_score("chrome", chrome) >= 96


def test_unrelated_window_is_not_selected() -> None:
    vscode = window("main.py - Visual Studio Code", "Code.exe")
    assert best_window_match("DeFy Tickets", [vscode]) is None
