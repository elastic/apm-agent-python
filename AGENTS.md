# Working in this repository

## Scope and local workspace

- This repository contains the Elastic APM Python agent. Read `CONTRIBUTING.md` for contribution guidance.
- Preserve existing user changes and untracked files. This checkout contains local virtual environments and unrelated reproduction scripts; keep searches, formatting, and test discovery scoped to repository source and tests.
- Use `git ls-files` to distinguish repository files from local experiments. Do not recreate or remove existing environments as part of routine test setup.

## Python and dependencies

- Test dependencies live in `tests/requirements/reqs-base.txt` and framework-specific `tests/requirements/reqs-<framework>.txt` files.
- For CI reproductions, inspect the job log for the actual installed versions, Python version, command, environment variables, and random-order seed. A `newest` requirement does not identify the version used by an earlier run.
- The package supports Python 3.6 and later according to `setup.cfg`; keep production code compatible with supported versions and follow surrounding compatibility patterns.

## Running tests

- Run pytest from the repository root, naming the relevant test file or directory. For example:

  ```sh
  venv312/bin/python -m pytest tests/instrumentation/pymongo_tests.py -vv
  ```

- Pytest configuration is in `setup.cfg`. Tests include `*_tests.py` and `tests.py`, and ordering is randomized by default. Reuse a reported seed with `--random-order-seed=<seed>` when reproducing a failure.
- Shared fixtures live in `tests/fixtures.py`; framework fixtures are loaded by `tests/conftest.py` when their dependencies are installed. Missing optional dependencies or service environment variables can cause skips; inspect the results before treating a run as validation.
- Inspect `tests/scripts/envs/<framework>.sh` for the framework marker, service names, and connection variables. These scripts normally use Docker network hostnames; use the published localhost port when running pytest on the host.
- Services are defined in `tests/docker-compose.yml`. Resolve the required service from the framework environment script and start only that service, preserving existing containers and volumes:

  ```sh
  docker compose -f tests/docker-compose.yml up -d <service>
  ```

  Inspect the Compose port mappings and test fixtures before connecting. Integration tests may create and drop databases; point them at dedicated test services.

- The CI entry points are `tests/scripts/docker/run_tests.sh` and `tests/scripts/run_tests.sh`. The Docker runner limits the test command to five minutes; exit code 124 indicates a timeout. Enable `PYTHONFAULTHANDLER=1` when investigating suspected interpreter crashes.
- `make test` recursively deletes Python bytecode caches and invokes broad test discovery. Prefer a scoped direct pytest command in this workspace. For coverage, use the options from `make coverage`: `--cov --cov-context=test --cov-config=setup.cfg --cov-branch`; set `COVERAGE_FILE` to a temporary path for experiments.
- If the execution sandbox blocks a required network or local database connection, rerun with the required permission; distinguish sandbox connection failures from application failures.

## Troubleshooting CI and service failures

- Compare failing and passing matrix entries across interpreter, driver, service image, and environment settings. Failures isolated to one integration may reflect its service or network setup rather than agent code.
- A container reported as `Started` may not be ready or remain running. Inspect its healthcheck and the framework's readiness configuration; a listening port alone does not guarantee the service can handle requests.
- Repeated failures at regular intervals can indicate connection or retry timeouts. Inspect the first test traceback and fixture teardown separately: both may attempt to access the same unavailable service. Confirm the cause from errors and logs rather than timing alone.
- Capture service logs and container state before CI cleanup removes containers and volumes. From the repository root, substitute the service identified in the framework environment script:

  ```sh
  docker compose -f tests/docker-compose.yml ps -a <service>
  docker compose -f tests/docker-compose.yml logs --no-color <service>
  ```

  Inspect the container state for its exit code, error, and OOM status when investigating a possible service crash.
- Check connectivity from the environment running the tests. A successful host connection does not establish connectivity from a test container; verify hostnames, ports, and Docker networks there.
- A passing scoped local run validates that local combination. Before ruling out a CI-specific problem, compare Python patch versions, resolved dependencies, service images, coverage settings, full test collection, and ordering. Reusing a random seed with a different collected suite may produce a different order.

## Code changes and validation

- Agent code is under `elasticapm/`; synchronous instrumentation is under `elasticapm/instrumentation/packages/`, and asynchronous instrumentation is under its `asyncio/` directory. Instrumentation tests are under `tests/instrumentation/`.
- Keep compatibility fixes focused and add regression coverage for changed behavior. Follow existing optional dependency skips, markers, fixtures, and instrumentation patterns.
- Formatting and lint configuration is in `pyproject.toml`, `setup.cfg`, and `.pre-commit-config.yaml`: Black, isort, Flake8, and a Python license-header check. Preserve license headers and use the configured 120-character formatter line length.
- Report the exact reproduction command, dependency versions, test outcome, and any differences from CI. Clearly distinguish a reproduced failure from a passing local run or an unverified hypothesis.
