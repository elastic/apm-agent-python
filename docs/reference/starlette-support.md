---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/starlette-support.html
---

# Starlette/FastAPI Support [starlette-support]

Incorporating Elastic APM into your Starlette project only requires a few easy steps.


## Installation [starlette-installation]

Install the Elastic APM agent using pip:

```bash
$ pip install elastic-apm
```

or add `elastic-apm` to your project’s `requirements.txt` file.


## Setup [starlette-setup]

To set up the agent, you need to initialize it with appropriate settings.

The settings are configured either via environment variables, or as initialization arguments.

You can find a list of all available settings in the [Configuration](/reference/configuration.md) page.

To initialize the agent for your application using environment variables, add the ElasticAPM middleware to your Starlette application:

```python
from starlette.applications import Starlette
from elasticapm.contrib.starlette import ElasticAPM

app = Starlette()
app.add_middleware(ElasticAPM)
```

::::{warning}
`BaseHTTPMiddleware` breaks `contextvar` propagation, as noted [here](https://www.starlette.io/middleware/#limitations). This means the ElasticAPM middleware must be above any `BaseHTTPMiddleware` in the final middleware list. If you’re calling `add_middleware` repeatedly, add the ElasticAPM middleware last. If you’re passing in a list of middleware, ElasticAPM should be first on that list.
::::


To configure the agent using initialization arguments:

```python
from starlette.applications import Starlette
from elasticapm.contrib.starlette import make_apm_client, ElasticAPM

apm = make_apm_client({
    'SERVICE_NAME': '<SERVICE-NAME>',
    'SECRET_TOKEN': '<SECRET-TOKEN>',
    'SERVER_URL': '<SERVER-URL>',
})
app = Starlette()
app.add_middleware(ElasticAPM, client=apm)
```


## FastAPI [starlette-fastapi]

Because FastAPI supports Starlette middleware, using the agent with FastAPI is almost exactly the same as with Starlette:

```python
from fastapi import FastAPI
from elasticapm.contrib.starlette import ElasticAPM

app = FastAPI()
app.add_middleware(ElasticAPM)
```


## Usage [starlette-usage]

Once you have configured the agent, it will automatically track transactions and capture uncaught exceptions within starlette.

Capture an arbitrary exception by calling [`capture_exception`](/reference/api-reference.md#client-api-capture-exception):

```python
try:
    1 / 0
except ZeroDivisionError:
    apm.capture_exception()
```

Log a generic message with [`capture_message`](/reference/api-reference.md#client-api-capture-message):

```python
apm.capture_message('hello, world!')
```


## Performance metrics [starlette-performance-metrics]

If you’ve followed the instructions above, the agent has installed our instrumentation middleware which will process all requests through your app. This will measure response times, as well as detailed performance data for all supported technologies.

::::{note}
Due to the fact that `asyncio` drivers are usually separate from their synchronous counterparts, specific instrumentation is needed for all drivers. The support for asynchronous drivers is currently quite limited.
::::



### Ignoring specific routes [starlette-ignoring-specific-views]

You can use the [`TRANSACTIONS_IGNORE_PATTERNS`](/reference/configuration.md#config-transactions-ignore-patterns) configuration option to ignore specific routes. The list given should be a list of regular expressions which are matched against the transaction name:

```python
apm = make_apm_client({
    # ...
    'TRANSACTIONS_IGNORE_PATTERNS': ['^GET /secret', '/extra_secret']
    # ...
})
```

This would ignore any requests using the `GET /secret` route and any requests containing `/extra_secret`.


## Supported Starlette and Python versions [supported-starlette-and-python-versions]

A list of supported [Starlette](/reference/supported-technologies.md#supported-starlette) and [Python](/reference/supported-technologies.md#supported-python) versions can be found on our [Supported Technologies](/reference/supported-technologies.md) page.

::::{note}
Elastic APM only supports `asyncio` when using Python 3.7+
::::


