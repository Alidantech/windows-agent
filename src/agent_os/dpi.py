from __future__ import annotations


def enable_per_monitor_v2() -> bool:
    """Enable Per Monitor v2 awareness before any Win32 geometry is read."""

    try:
        import ctypes

        result = ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return bool(result)
    except Exception:
        return False
