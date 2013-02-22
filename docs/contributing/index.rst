Contributing
============

Want to contribute back to Opbeat? This page describes the general development flow,
our philosophy, the test suite, and issue tracking.

(Though it actually doesn't describe all of that, yet)

Setting up an Environment
-------------------------

Opbeat is designed to run off of setuptools with minimal work. Because of this
setting up a development environment for Opbeat requires only a few steps.

The first thing you're going to want to do, is build a virtualenv and install
any base dependancies.

.. code-block:: bash

    virtualenv ~/.virtualenvs/opbeat
    source ~/.virtualenvs/opbeat/bin/activate
    python setup.py develop

Running the Test Suite
----------------------

The test suite is also powered off of setuptools, and can be run in two fashions. The
easiest is to simply use setuptools and it's ``test`` command. This will handle installing
any dependancies you're missing automatically.

.. code-block:: bash

    python setup.py test

If you've already installed the dependencies, or don't care about certain tests which will
be skipped without them, you can also run tests in a more verbose way.

.. code-block:: bash

    python runtests.py

The ``runtests.py`` command has several options, and if you're familiar w/ Django you should feel
right at home.

.. code-block:: bash

    # Stop immediately on a failure
    python runtests.py --failfast


Contributing Back Code
----------------------

Ideally all patches should be sent as a pull request on GitHub, and include tests. If you're fixing a bug or making a large change the patch **must** include test coverage.

You can see a list of open pull requests (pending changes) by visiting https://github.com/opbeat/opbeat_python/pulls

