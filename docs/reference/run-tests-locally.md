---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/run-tests-locally.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
products:
  - id: cloud-serverless
  - id: observability
  - id: apm
---

# Run Tests Locally [run-tests-locally]

To run tests locally you can make use of the docker images also used when running the whole test suite with Jenkins. Running the full test suite first does some linting and then runs the actual tests with different versions of Python and different web frameworks. For a full overview of the test matrix and supported versions have a look at [Jenkins Configuration](https://github.com/elastic/apm-agent-python/blob/main/Jenkinsfile).


### Pre Commit [pre-commit]

We run our git hooks on every commit to automatically point out issues in code. Those issues are also detected within the GitHub actions. Please follow the installation steps stated in [https://pre-commit.com/#install](https://pre-commit.com/#install).


### Code Linter [coder-linter]

We run two code linters `isort` and `flake8`. You can trigger each single one locally by running:

```bash
$ pre-commit run -a isort
```

```bash
$ pre-commit run -a flake8
```


### Code Formatter [coder-formatter]

We test that the code is formatted using `black`. You can trigger this check by running:

```bash
$ pre-commit run -a black
```


### Test Documentation [test-documentation]

We test that the documentation can be generated without errors. You can trigger this check by running:

```bash
$ ./tests/scripts/docker/docs.sh
```


### Running Tests [running-tests]

We run the test suite on different combinations of Python versions and web frameworks. For triggering the test suite for a specific combination locally you can run:

```bash
$ ./tests/scripts/docker/run_tests.sh python-version framework-version <pip-cache-dir>
```

::::{note}
The `python-version` must be of format `python-version`, e.g. `python-3.6` or `pypy-2`. The `framework` must be of format `framework-version`, e.g. `django-1.10` or `flask-0.12`.
::::


You can also run the unit tests outside of docker, by installing the relevant [requirements file](https://github.com/elastic/apm-agent-python/tree/main/tests/requirements) and then running `py.test` from the project root.

## Integration testing [_integration_testing]

Check out [https://github.com/elastic/apm-integration-testing](https://github.com/elastic/apm-integration-testing) for resources for setting up full end-to-end testing environments. For example, to spin up an environment with the [opbeans Django app](https://github.com/basepi/opbeans-python), with version 7.3 of the elastic stack and the apm-python-agent from your local checkout, you might do something like this:

```bash
$ ./scripts/compose.py start 7.3 \
    --with-agent-python-django --with-opbeans-python \
    --opbeans-python-agent-local-repo=~/elastic/apm-agent-python
```


