# Repository Guidelines

## Project Structure & Module Organization
Core agent code lives in `elasticapm/`, with feature areas split into packages such as `contrib/`, `instrumentation/`, `transport/`, `metrics/`, and `utils/`. Tests live under `tests/` and are grouped by subsystem, for example `tests/instrumentation/`, `tests/contrib/`, and `tests/config/`. Test-only helpers and dependency sets are in `tests/fixtures.py`, `tests/requirements/`, and `tests/scripts/`. CI matrix files are under `.ci/`, and end-user documentation is in `docs/`.

## Build, Test, and Development Commands
Use the repo `Makefile` for the standard workflow:

- `make test`: clears Python caches, then runs `pytest -v --showlocals`.
- `make coverage`: runs the test suite with branch coverage enabled.
- `make flake8`: runs lint checks.
- `make isort`: sorts imports across the repository.
- `make docs`: builds docs from `docs/` into `build/`.

For local setup, install the dependency set relevant to your area first, for example `pip install -r tests/requirements/reqs-flask-1.1.txt`. Install hooks with `pre-commit install`.

## Coding Style & Naming Conventions
Python uses 4-space indentation, LF line endings, and UTF-8 per `.editorconfig`; YAML and `.feature` files use 2 spaces. Format with `black` and keep lines at 120 characters. Keep imports ordered with `isort`, then run `flake8`. Module and function names use `snake_case`; classes use `PascalCase`. Follow existing test file patterns such as `*_tests.py` and `test_*.py`.

## Testing Guidelines
Pytest is the test runner, with random ordering enabled by default. Favor focused runs while developing, for example `pytest tests/instrumentation/httpx_tests.py -m httpx`. Mark integration-heavy cases with the existing pytest markers from `setup.cfg`, and use `pytest.importorskip()` for optional dependencies. Add new dependency-specific requirements in `tests/requirements/` and matching environment scripts in `tests/scripts/envs/` when expanding the matrix.

## Commit & Pull Request Guidelines
Recent history follows concise, Conventional Commit-style subjects such as `fix: ...` and `build(deps): ...`; keep commit messages short and scoped. Open PRs against `main`, link the related issue (`Closes #123`), summarize behavior changes, and note any test coverage added. Expect maintainers to squash-merge, so keep branch history clean and rebased.
