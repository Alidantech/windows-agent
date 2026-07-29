from pathlib import Path

from agent_os.skills import SkillLoader


def test_smoke_test_skill_selected() -> None:
    root = Path(__file__).resolve().parents[1]
    selected = SkillLoader(root / "skills").select(
        "Open defytickets.com and smoke test every navigation link"
    )
    names = {skill.name for skill in selected}
    assert "smoke-testing" in names
    assert "browser" in names
