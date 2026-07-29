from agent_os.lease import TargetLease
from agent_os.models import Rectangle, WindowInfo


def test_monitor_lease_binds_exact_window() -> None:
    lease = TargetLease(
        requested_spec="monitor:3",
        controller_hwnd=10,
        controller_title="Terminal",
        monitor_index=3,
        monitor_rect=Rectangle(left=1920, top=0, width=1920, height=1080),
    )
    target = WindowInfo(
        hwnd=77,
        title="DeFy Tickets - Brave",
        process_name="brave.exe",
        rect=Rectangle(left=1920, top=0, width=1920, height=1080),
    )
    assert lease.bind_window(target, "test discovery")
    assert lease.capture_spec == "hwnd:77"
    assert lease.bound_hwnd == 77
    assert lease.monitor_index == 3
    assert lease.generation == 1


def test_browser_binding_changes_backend_and_capture_spec() -> None:
    lease = TargetLease(requested_spec="monitor:2", controller_hwnd=10, controller_title="Terminal")
    assert lease.bind_browser("DeFy Tickets")
    assert lease.backend == "browser"
    assert lease.capture_spec == "browser-session"
    assert lease.generation == 1


def test_rebinding_same_window_does_not_increment_generation() -> None:
    lease = TargetLease(requested_spec="desktop", controller_hwnd=10, controller_title="Terminal")
    target = WindowInfo(
        hwnd=77,
        title="App",
        process_name="app.exe",
        rect=Rectangle(left=0, top=0, width=800, height=600),
    )
    lease.bind_window(target, "first")
    lease.bind_window(target, "refresh")
    assert lease.generation == 1
