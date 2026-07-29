# uv workflow

Windows Agent uses uv as its only supported Python project manager.

## Why uv

uv owns four responsibilities:

1. selecting or downloading Python 3.12 from `.python-version`;
2. resolving dependencies from `pyproject.toml` into `uv.lock`;
3. synchronizing the isolated project environment;
4. running commands inside that environment without activation.

The environment may exist internally at `.venv`, but users must not create, activate, or modify it manually.

## Install uv on Windows

Using WinGet:

```powershell
winget install --id=astral-sh.uv -e
```

Using the official installer:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

From Git Bash:

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart the terminal and verify:

```bash
uv --version
```

## First setup

```bash
git clone https://github.com/Alidantech/windows-agent.git
cd windows-agent
uv sync
uv run playwright install chromium
uv run windows-agent
```

## Existing checkout

```bash
git pull origin master
uv sync
uv run windows-agent
```

## Reproducible installation

After `uv.lock` exists:

```bash
uv lock --check
uv sync --locked
```

`uv sync --locked` fails instead of silently changing an outdated lockfile.

## Updating dependencies

Add a runtime dependency:

```bash
uv add package-name
```

Add a development dependency:

```bash
uv add --dev package-name
```

Remove a dependency:

```bash
uv remove package-name
```

Upgrade all locked packages within declared constraints:

```bash
uv lock --upgrade
uv sync
```

Inspect the dependency graph:

```bash
uv tree
```

Commit `pyproject.toml` and `uv.lock` together after dependency changes.

## Tests and quality checks

```bash
uv run python -m compileall src tests
uv run pytest
uv run ruff check .
```

## Rules

Do not use these project workflows:

```text
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
python -m pip install ...
```

Do not manually install packages into uv's managed environment. Use `uv add`, `uv remove`, `uv sync`, and `uv run`.
