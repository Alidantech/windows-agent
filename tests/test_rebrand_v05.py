from pathlib import Path


def test_pyproject_exposes_primary_and_compatibility_commands() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "windows-agent"' in pyproject
    assert 'windows-agent = "agent_os.windows_cli:app"' in pyproject
    assert 'agent-os = "agent_os.cli:app"' in pyproject


def test_primary_environment_prefix_is_windows_agent() -> None:
    example = Path(".env.example").read_text(encoding="utf-8")
    assert "WINDOWS_AGENT_PROVIDER=" in example
    assert "WINDOWS_AGENT_TARGET=" in example
    assert "AGENT_OS_TARGET=" not in example
