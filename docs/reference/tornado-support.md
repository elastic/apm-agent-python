---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/tornado-support.html
---

# Tornado Support [tornado-support]

Incorporating Elastic APM into your Tornado project only requires a few easy steps.


## Installation [tornado-installation]

Install the Elastic APM agent using pip:

```bash
$ pip install elastic-apm
```

or add `elastic-apm` to your project’s `requirements.txt` file.


## Setup [tornado-setup]

To set up the agent, you need to initialize it with appropriate settings.

The settings are configured either via environment variables, the application’s settings, or as initialization arguments.

You can find a list of all available settings in the [Configuration](/reference/configuration.md) page.

To initialize the agent for your application using environment variables:

```python
import tornado.web
from elasticapm.contrib.tornado import ElasticAPM

app = tornado.web.Application()
apm = ElasticAPM(app)
```

To configure the agent using `ELASTIC_APM` in your application’s settings:

```python
import tornado.web
from elasticapm.contrib.tornado import ElasticAPM

app = tornado.web.Application()
app.settings['ELASTIC_APM'] = {
    'SERVICE_NAME': '<SERVICE-NAME>',
    'SECRET_TOKEN': '<SECRET-TOKEN>',
}
apm = ElasticAPM(app)
```


## Usage [tornado-usage]

Once you have configured the agent, it will automatically track transactions and capture uncaught exceptions within tornado.

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


## Performance metrics [tornado-performance-metrics]

If you’ve followed the instructions above, the agent has installed our instrumentation within the base RequestHandler class in tornado.web. This will measure response times, as well as detailed performance data for all supported technologies.

::::{note}
Due to the fact that `asyncio` drivers are usually separate from their synchronous counterparts, specific instrumentation is needed for all drivers. The support for asynchronous drivers is currently quite limited.
::::



### Ignoring specific routes [tornado-ignoring-specific-views]

You can use the [`TRANSACTIONS_IGNORE_PATTERNS`](/reference/configuration.md#config-transactions-ignore-patterns) configuration option to ignore specific routes. The list given should be a list of regular expressions which are matched against the transaction name:

```python
app.settings['ELASTIC_APM'] = {
    # ...
    'TRANSACTIONS_IGNORE_PATTERNS': ['^GET SecretHandler', 'MainHandler']
    # ...
}
```

This would ignore any requests using the `GET SecretHandler` route and any requests containing `MainHandler`.


## Supported tornado and Python versions [supported-tornado-and-python-versions]

A list of supported [tornado](/reference/supported-technologies.md#supported-tornado) and [Python](/reference/supported-technologies.md#supported-python) versions can be found on our [Supported Technologies](/reference/supported-technologies.md) page.

::::{note}
Elastic APM only supports `asyncio` when using Python 3.7+
::::


