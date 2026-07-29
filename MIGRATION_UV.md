# Migration from manual virtual environments to uv

Windows Agent no longer documents or supports manual virtual-environment activation and pip-based project installation.

## Install uv

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen Git Bash, then verify:

```bash
uv --version
```

## Replace the old local environment

From the repository:

```bash
cd ~/Projects/windows-agent
deactivate 2>/dev/null || true
rm -rf .venv
git pull origin master
uv sync
uv run playwright install chromium
```

You do not activate the new environment. Start the application with:

```bash
uv run windows-agent
```

## New command mapping

| Old workflow | uv workflow |
|---|---|
| `python -m venv .venv` | `uv sync` |
| `source .venv/Scripts/activate` | Not needed |
| `python -m pip install -e .` | `uv sync` |
| `python -m pip install -e ".[dev]"` | `uv sync` |
| `python -m playwright install chromium` | `uv run playwright install chromium` |
| `windows-agent` after activation | `uv run windows-agent` |
| `pytest` | `uv run pytest` |
| `ruff check .` | `uv run ruff check .` |

## Lockfile

The first successful `uv sync` creates `uv.lock` automatically. Commit it:

```bash
git add uv.lock pyproject.toml .python-version
git commit -m "Lock Windows Agent dependencies with uv"
git push origin master
```

Afterward, use `uv sync --locked` when you want installation to fail rather than modify an outdated lockfile.
