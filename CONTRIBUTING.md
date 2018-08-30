# Contributing to the Python APM Agent

The APM Agent is open source and we love to receive contributions from our community — you!

There are many ways to contribute,
from writing tutorials or blog posts,
improving the documentation,
submitting bug reports and feature requests or writing code.

You can get in touch with us through [Discuss](https://discuss.elastic.co/c/apm),
feedback and ideas are always welcome.

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

1. Sign the Contributor License Agreement

    Please make sure you have signed our [Contributor License Agreement](https://www.elastic.co/contributor-agreement/).
    We are not asking you to assign copyright to us,
    but to give us the right to distribute your code without restriction.
    We ask this of all contributors in order to assure our users of the origin and continuing existence of the code.
    You only need to sign the CLA once.

1. Code style

    This project uses several tools to maintain a consistent code style:
    
     * the automatic code formatter [black](https://black.readthedocs.io/en/stable/)
     * sorting of imports via [isort](https://isort.readthedocs.io/en/latest/)
     * [flake8](http://flake8.pycqa.org/en/latest/)
     
    The easiest way to make sure your pull request adheres to the the code style
    is to install [pre-commit](https://pre-commit.com/).

1. Test your changes

    Run the test suite to make sure that nothing is broken.
    See [testing](#testing) for details.

1. Rebase your changes

    Update your local repository with the most recent code from the main repo,
    and rebase your branch on top of the latest master branch.
    We prefer your initial changes to be squashed into a single commit.
    Later,
    if we ask you to make changes,
    add them as separate commits.
    This makes them easier to review.
    As a final step before merging we will either ask you to squash all commits yourself or we'll do it for you.

1. Submit a pull request

    Push your local changes to your forked copy of the repository and [submit a pull request](https://help.github.com/articles/using-pull-requests).
    In the pull request,
    choose a title which sums up the changes that you have made,
    and in the body provide more details about what your changes do.
    Also mention the number of the issue where discussion has taken place,
    eg "Closes #123".

1. Be patient

    We might not be able to review your code as fast as we would like to,
    but we'll do our best to dedicate it the attention it deserves.
    Your effort is much appreciated!

### Testing

To run the full test suite,
you need to install several databases (Elasticsearch, PostgreSQL, MySQL, Cassandra, Redis).
This can be quite a hassle, so we recommend to use our dockerized test setup.
See [Running tests](https://www.elastic.co/guide/en/apm/agent/python/master/run-tests-locally.html) for detailed instructions.


### Workflow

All feature development and most bug fixes hit the master branch first.
Pull requests should be reviewed by someone with commit access.
Once approved, the author of the pull request,
or reviewer if the author does not have commit access,
should "Squash and merge".

### Releasing

If you have commit access, the process is as follows:

1. Update the version in `elasticapm/version.py` according to the scale of the change. (major, minor or patch)
1. Update `CHANGELOG.md`
1. Commit changes with message `update CHANGELOG and bump version to x.y.z` where `x.y.z` is the version in `elasticapm/version.py`
1. Tag the commit with `git tag vx.y.x`, for example `git tag v1.2.3`
1. Reset the current major branch (`1.x`, `2.x` etc) to point to the current master, e.g. `git branch -f 1.x master`
1. Push commits and tags upstream with `git push upstream master && git push upstream --tags` (and optionally to your own fork as well)
1. Update major branch, e.g. `1.x` on upstream with `git push upstream 1.x`
1. After tests pass, TravisCI will automatically push a source package, as well as binary wheels, to PyPI.
