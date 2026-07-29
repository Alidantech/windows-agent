from agent_os.repeat import RepeatDetector


def test_repeat_detector_counts_consecutive_actions() -> None:
    detector = RepeatDetector(limit=3)
    assert detector.add("a") == 1
    assert detector.add("a") == 2
    assert detector.add("a") == 3


def test_repeat_detector_resets_sequence_on_different_action() -> None:
    detector = RepeatDetector(limit=3)
    detector.add("a")
    detector.add("a")
    assert detector.add("b") == 1
