---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/sanic-support.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# Sanic Support [sanic-support]

Incorporating Elastic APM into your Sanic project only requires a few easy steps.


## Installation [sanic-installation]

Install the Elastic APM agent using pip:

```bash
$ pip install elastic-apm
```

or add `elastic-apm` to your project’s `requirements.txt` file.


## Setup [sanic-setup]

To set up the agent, you need to initialize it with appropriate settings.

The settings are configured either via environment variables, or as initialization arguments.

You can find a list of all available settings in the [Configuration](/reference/configuration.md) page.

To initialize the agent for your application using environment variables:

```python
from sanic import Sanic
from elasticapm.contrib.sanic import ElasticAPM

app = Sanic(name="elastic-apm-sample")
apm = ElasticAPM(app=app)
```

To configure the agent using initialization arguments and Sanic’s Configuration infrastructure:

```python
# Create a file named external_config.py in your application
# If you want this module based configuration to be used for APM, prefix them with ELASTIC_APM_
ELASTIC_APM_SERVER_URL = "https://serverurl.apm.com:443"
ELASTIC_APM_SECRET_TOKEN = "sometoken"
```

```python
from sanic import Sanic
from elasticapm.contrib.sanic import ElasticAPM

app = Sanic(name="elastic-apm-sample")
app.config.update_config("path/to/external_config.py")
apm = ElasticAPM(app=app)
```


## Usage [sanic-usage]

Once you have configured the agent, it will automatically track transactions and capture uncaught exceptions within sanic.

Capture an arbitrary exception by calling [`capture_exception`](/reference/api-reference.md#client-api-capture-exception):

```python
from sanic import Sanic
from elasticapm.contrib.sanic import ElasticAPM

app = Sanic(name="elastic-apm-sample")
apm = ElasticAPM(app=app)

try:
    1 / 0
except ZeroDivisionError:
    apm.capture_exception()
```

Log a generic message with [`capture_message`](/reference/api-reference.md#client-api-capture-message):

```python
from sanic import Sanic
from elasticapm.contrib.sanic import ElasticAPM

app = Sanic(name="elastic-apm-sample")
apm = ElasticAPM(app=app)

apm.capture_message('hello, world!')
```


## Performance metrics [sanic-performance-metrics]

If you’ve followed the instructions above, the agent has installed our instrumentation middleware which will process all requests through your app. This will measure response times, as well as detailed performance data for all supported technologies.

::::{note}
Due to the fact that `asyncio` drivers are usually separate from their synchronous counterparts, specific instrumentation is needed for all drivers. The support for asynchronous drivers is currently quite limited.
::::



### Ignoring specific routes [sanic-ignoring-specific-views]

You can use the [`TRANSACTIONS_IGNORE_PATTERNS`](/reference/configuration.md#config-transactions-ignore-patterns) configuration option to ignore specific routes. The list given should be a list of regular expressions which are matched against the transaction name:

```python
from sanic import Sanic
from elasticapm.contrib.sanic import ElasticAPM

app = Sanic(name="elastic-apm-sample")
apm = ElasticAPM(app=app, config={
    'TRANSACTIONS_IGNORE_PATTERNS': ['^GET /secret', '/extra_secret'],
})
```

This would ignore any requests using the `GET /secret` route and any requests containing `/extra_secret`.


## Extended Sanic APM Client Usage [extended-sanic-usage]

Sanic’s contributed APM client also provides a few extendable way to configure selective behaviors to enhance the information collected as part of the transactions being tracked by the APM.

In order to enable this behavior, the APM Client middleware provides a few callback functions that you can leverage in order to simplify the process of generating additional contexts into the traces being collected.

| Callback Name | Callback Invocation Format | Expected Return Format | Is Async |
| --- | --- | --- | --- |
| transaction_name_callback | transaction_name_callback(request) | string | false |
| user_context_callback | user_context_callback(request) | (username_string, user_email_string, userid_string) | true |
| custom_context_callback | custom_context_callback(request) or custom_context_callback(response) | dict(str=str) | true |
| label_info_callback | label_info_callback() | dict(str=str) | true |


## Supported Sanic and Python versions [supported-stanic-and-python-versions]

A list of supported [Sanic](/reference/supported-technologies.md#supported-sanic) and [Python](/reference/supported-technologies.md#supported-python) versions can be found on our [Supported Technologies](/reference/supported-technologies.md) page.

::::{note}
Elastic APM only supports `asyncio` when using Python 3.7+
::::


