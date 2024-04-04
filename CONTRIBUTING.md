# Contributing to the Python APM Agent

The APM Agent is open source and we love to receive contributions from our community — you!

There are many ways to contribute,
from writing tutorials or blog posts,
improving the documentation,
submitting bug reports and feature requests or writing code.

You can get in touch with us through [Discuss](https://discuss.elastic.co/c/apm).
Feedback and ideas are always welcome.

Please note that this repository is covered by the [Elastic Community Code of Conduct](https://www.elastic.co/community/codeofconduct).

## Code contributions

If you have a bugfix or new feature that you would like to contribute,
please find or open an issue about it first.
Talk about what you would like to do.
It may be that somebody is already working on it,
or that there are particular issues that you should know about before implementing the change.

### Submitting your changes

Generally, we require that you test any code you are adding or modifying.
Once your changes are ready to submit for review:

1.  Sign the Contributor License Agreement

    Please make sure you have signed our [Contributor License Agreement](https://www.elastic.co/contributor-agreement/).
    We are not asking you to assign copyright to us,
    but to give us the right to distribute your code without restriction.
    We ask this of all contributors in order to assure our users of the origin and continuing existence of the code.
    You only need to sign the CLA once.

1.  Code style

    This project uses several tools to maintain a consistent code style:

    -   the automatic code formatter [black](https://black.readthedocs.io/en/stable/)
    -   sorting of imports via [isort](https://isort.readthedocs.io/en/latest/)
    -   [flake8](http://flake8.pycqa.org/en/latest/)
    -   License header check via custom script

    The easiest way to make sure your pull request adheres to the code style
    is to install [pre-commit](https://pre-commit.com/).

        pip install pre-commit # or "brew install pre-commit" if you use Homebrew

        pre-commit install

1.  Test your changes

    Run the test suite to make sure that nothing is broken.
    See [testing](#testing) for details. (Note, only unit tests are expected
    to be run before submitting a PR.)

1.  Rebase your changes

    Update your local repository with the most recent code from the main repo,
    and rebase your branch on top of the latest main branch.
    When we merge your PR, we will squash all of your commits into a single
    commit on the main branch.

1.  Submit a pull request

    Push your local changes to your forked copy of the repository and [submit a pull request](https://help.github.com/articles/using-pull-requests) to the `main` branch.
    In the pull request,
    choose a title which sums up the changes that you have made,
    and in the body provide more details about what your changes do.
    Also mention the number of the issue where discussion has taken place,
    eg "Closes #123".

1.  Be patient

    We might not be able to review your code as fast as we would like to,
    but we'll do our best to dedicate it the attention it deserves.
    Your effort is much appreciated!

### Testing

To run local unit tests, you can install the relevant
[requirements files](https://github.com/elastic/apm-agent-python/tree/main/tests/requirements)
and then run `make test` from the project root:

    pip install -r tests/requirements/reqs-flask-1.1.txt
    make test

Pytest will automatically discover all the tests and skip the ones for which
dependencies are not met.

If you want to go above and beyond and run the full test suite,
you need to install several databases (Elasticsearch, PostgreSQL, MySQL, Cassandra, Redis).
This can be quite a hassle, so we recommend to use our dockerized test setup.
See [Running tests](https://www.elastic.co/guide/en/apm/agent/python/main/run-tests-locally.html) for detailed instructions.

#### Pytest

This project uses [pytest](https://docs.pytest.org/en/latest/) for all of its
testing needs. Note that pytest can be a bit confusing at first, due to its
dynamic discovery features. In particular,
[fixtures](https://docs.pytest.org/en/stable/fixture.html) can be confusing
and hard to discover, due to the fact that they do not need to be imported to
be used. For example, whenever a test has `elasticapm_client` as an argument,
that is a fixture which is defined
[here](https://github.com/elastic/apm-agent-python/blob/ed4ce5fd5db3cc091a54d3328384fbce62635bbb/tests/fixtures.py#L150).

#### Adding new instrumentations to the matrix build

For tests that require external dependencies like databases, or for testing different versions of the same library,
we use a matrix build that leverages Docker.

The setup requires a little bit of boilerplate to get started.
In this example, we will create an instrumentation for the "foo" database, by instrumenting its Python driver, `foodriver`.

1.  mark your tests with a pytest marker that describes the new instrumentation at the top of your tests file:

        pytestmark = pytest.mark.foo

    `pytestmark` can also be a list if you need to define more than one mark (e.g. to mark tests as integration tests):

        pytestmark = [pytest.mark.foo, pytest.mark.integrationtest]

1.  make sure to use `pytest.importorskip` to import any dependencies that are only required by your tests:

    foodriver = pytest.importorskip("foodriver")

1.  Create one or more requirements files in `tests/requirements` that list the dependencies that are to be installed specifically for your tests:
    To only test the newest version of the library, create a file `tests/requirements/reqs-foo-newest.txt` and add something like this to it:

        foodriver
        -r reqs-base.txt

    This tells the matrix runner to install the newest version of `foodriver`, as well as the base requirements needed to run the test suite.
    To test more than one version of the library, create additional `reqs-foo-X.Y.txt` files with specific versions of your instrumented package.

1.  Create a file called `foo.sh` in `tests/scripts/envs/foo.sh`.
    Here you can define environment variables that are required to run your tests.
    As a minimum, you'll have to set the `PYTEST_MARKER` variable to the same value you used above for the pytest marker, e.g.

        export PYTEST_MARKER="-m foo"

1.  Add entries in `.ci/matrix_framework.yml` (for pull requests) and `.ci/matrix_framework_full.yml` (for nightly builds).
    Generally, we only test the newest version of an instrumentation with every pull request:

        - foo-newest

    To test other versions in the nightly build, add them to `.ci/matrix_framework_full.yml`.

1.  OPTIONAL: If you need a real service to test against (e.g. an actual foo database), add an entry in `tests/docker-compose.yml` under `services`:

          foo:
             image: foobase:latest

    You'll also have to add a `DOCKER_DEPS` environment variable to `tests/scripts/envs/foo.sh` which tells the matrix
    to spin up the given Docker compose service before running your tests.
    You may also need to add things like hostname configuration here.

        DOCKER_DEPS="foo"
        FOO_CONNECTION_URL="http://foo:4711"

1.  OPTIONAL: If your instrumented package does not support all Python versions we test with, you can exclude certain combinations by adding them to `.ci/matrix_exclude.yml`:

    -   PYTHON_VERSION: python-3.5 # foo doesn't support Python 3.5
        FRAMEWORK: foo-newest

### Workflow

All feature development and most bug fixes hit the main branch first.
Pull requests should be reviewed by someone with commit access.
Once approved, the author of the pull request,
or reviewer if the author does not have commit access,
should "Squash and merge".

### Releasing

Releases tags are signed so you need to have a PGP key set up, you can follow Github documentation on [creating a key](https://docs.github.com/en/authentication/managing-commit-signature-verification/generating-a-new-gpg-key) and
on [telling git about it](https://docs.github.com/en/authentication/managing-commit-signature-verification/telling-git-about-your-signing-key). Alternatively you can sign with a SSH key, remember you have to upload your key
again even if you want to use the same key you are using for authorization.
Then make sure you have SSO figured out for the key you are using to push to github, see [Github documentation](https://docs.github.com/articles/authenticating-to-a-github-organization-with-saml-single-sign-on/).

If you have commit access, the process is as follows:

1. Update the version in `elasticapm/version.py` according to the scale of the change. (major, minor or patch)
1. Update `CHANGELOG.asciidoc`. Rename the `Unreleased` section to the correct version (`vX.X.X`), and nest under the appropriate sub-heading, e.g., `Python Agent version 5.x`.
1. For Majors: [Create an issue](https://github.com/elastic/website-requests/issues/new) to request an update of the [EOL table](https://www.elastic.co/support/eol).
1. For Majors: Add the new major version to `conf.yaml` in the [elastic/docs](https://github.com/elastic/docs) repo.
1. Commit changes with message `update CHANGELOG and bump version to X.Y.Z`
   where `X.Y.Z` is the version in `elasticapm/version.py`
1. Open a PR against `main` with these changes leaving the body empty
1. Once the PR is merged, fetch and checkout `upstream/main`
1. Tag the commit with `git tag -s vX.Y.Z`, for example `git tag -s v1.2.3`.
   Copy the changelog for the release to the tag message, removing any leading `#`.
1. Push tag upstream with `git push upstream --tags` (and optionally to your own fork as well)
1. Open a PR from `main` to the major branch, e.g. `1.x` to update it. In order to keep history create a
   branch from the `main` branch, rebase it on top of the major branch to drop duplicated commits and then
   merge with the `rebase` strategy. It is crucial that `main` and the major branch have the same content.
1. After tests pass, Github Actions will automatically build and push the new release to PyPI.
1. Edit and publish the [draft Github release](https://github.com/elastic/apm-agent-python/releases)
   created by Github Actions. Substitute the generated changelog with one hand written into the body of the
   release and move the agent layer ARNs under a `<details>` block with a `summary`.
