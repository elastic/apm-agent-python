---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/aiohttp-server-support.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# Aiohttp Server support [aiohttp-server-support]

Getting Elastic APM set up for your Aiohttp Server project is easy, and there are various ways you can tweak it to fit to your needs.


## Installation [aiohttp-server-installation]

Install the Elastic APM agent using pip:

```bash
$ pip install elastic-apm
```

or add `elastic-apm` to your project’s `requirements.txt` file.


## Setup [aiohttp-server-setup]

To set up the agent, you need to initialize it with appropriate settings.

The settings are configured either via environment variables, the application’s settings, or as initialization arguments.

You can find a list of all available settings in the [Configuration](/reference/configuration.md) page.

To initialize the agent for your application using environment variables:

```python
from aiohttp import web

from elasticapm.contrib.aiohttp import ElasticAPM

app = web.Application()

apm = ElasticAPM(app)
```

To configure the agent using `ELASTIC_APM` in your application’s settings:

```python
from aiohttp import web

from elasticapm.contrib.aiohttp import ElasticAPM

app = web.Application()

app['ELASTIC_APM'] = {
    'SERVICE_NAME': '<SERVICE-NAME>',
    'SECRET_TOKEN': '<SECRET-TOKEN>',
}
apm = ElasticAPM(app)
```


## Usage [aiohttp-server-usage]

Once you have configured the agent, it will automatically track transactions and capture uncaught exceptions within aiohttp.

Capture an arbitrary exception by calling [`capture_exception`](/reference/api-reference.md#client-api-capture-exception):

```python
try:
    1 / 0
except ZeroDivisionError:
    apm.client.capture_exception()
```

Log a generic message with [`capture_message`](/reference/api-reference.md#client-api-capture-message):

```python
apm.client.capture_message('hello, world!')
```


## Performance metrics [aiohttp-server-performance-metrics]

If you’ve followed the instructions above, the agent has already installed our middleware. This will measure response times, as well as detailed performance data for all supported technologies.

::::{note}
due to the fact that `asyncio` drivers are usually separate from their synchronous counterparts, specific instrumentation is needed for all drivers. The support for asynchronous drivers is currently quite limited.
::::



### Ignoring specific routes [aiohttp-server-ignoring-specific-views]

You can use the [`TRANSACTIONS_IGNORE_PATTERNS`](/reference/configuration.md#config-transactions-ignore-patterns) configuration option to ignore specific routes. The list given should be a list of regular expressions which are matched against the transaction name:

```python
app['ELASTIC_APM'] = {
    # ...
    'TRANSACTIONS_IGNORE_PATTERNS': ['^OPTIONS ', '/api/']
    # ...
}
```

This would ignore any requests using the `OPTIONS` method and any requests containing `/api/`.


## Supported aiohttp and Python versions [supported-aiohttp-and-python-versions]

A list of supported [aiohttp](/reference/supported-technologies.md#supported-aiohttp) and [Python](/reference/supported-technologies.md#supported-python) versions can be found on our [Supported Technologies](/reference/supported-technologies.md) page.

::::{note}
Elastic APM only supports `asyncio` when using Python 3.7+
::::


