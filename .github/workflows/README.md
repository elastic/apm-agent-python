## CI/CD

There are 5 main stages that run on GitHub actions:

* Linting
* Test
* Packaging
* Benchmarking
* Release

The whole process should look like:

`Checkout` -> `Linting` -> `Test` -> `Packaging` -> `Benchmark` -> `Release`

### Scenarios

* Full matrix compatibility should be triggered on a daily basis or manually.
* Subset matrix compatibility runs on branches, tags and PRs basis.
* Automated release in the CI gets triggered when a tag release is created.
* Pull Requests that are only affecting the docs files should not trigger any test or similar stages that are not required.
* Builds do not get triggered automatically for Pull Requests from contributors that are not Elasticians when need to access to any GitHub Secrets.

### Compatibility matrix

Python agent supports compatibility to different python versions and frameworks, those are defined in:

* [frameworks](https://github.com/elastic/apm-agent-python/blob/main/.ci/.matrix_framework.yml) for all the PRs.
* [frameworks](https://github.com/elastic/apm-agent-python/blob/main/.ci/.matrix_framework_full.yml) for the `daily` builds.
* Python [versions](https://github.com/elastic/apm-agent-python/blob/main/.ci/.matrix_python_full.yml) for all the `daily` builds.
* Python [versions](https://github.com/elastic/apm-agent-python/blob/main/.ci/.matrix_python.yml) for all the `*nix` builds.
* Python [versions](https://github.com/elastic/apm-agent-python/blob/1e38ec53115edc70c36c6485259733a8cde02ed9/.github/workflows/test.yml#L88-L101) for all the `windows` builds.
* [Exclude list](https://github.com/elastic/apm-agent-python/blob/main/.ci/.matrix_exclude.yml) for the above entries.

### How to interact with the CI?

#### On a PR basis

Once a PR has been opened then there are two different ways you can trigger builds in the CI:

1. Commit based
1. UI based, any Elasticians can force a build through the GitHub UI

#### Branches

Every time there is a merge to main or any release branches the whole workflow will compile and test every entry in the compatibility matrix for Linux and Windows.

### Release process

This process has been fully automated and it gets triggered when a tag release has been created.

### OpenTelemetry

There is a GitHub workflow in charge to populate what the workflow run in terms of jobs and steps. Those details can be seen in [here](https://ela.st/oblt-ci-cd-stats) (**NOTE**: only available for Elasticians).
