from pathlib import Path

from agent_os.skills import SkillLoader


def test_start_menu_skill_selected() -> None:
    root = Path(__file__).resolve().parents[1]
    skills = SkillLoader(root / "skills").select("Open the Windows Start menu")
    names = {skill.name for skill in skills}
    assert "start-menu" in names
    assert "core" in names
    assert "safety" in names
