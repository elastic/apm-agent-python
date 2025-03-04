---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/opentelemetry-bridge.html
---

# OpenTelemetry API Bridge [opentelemetry-bridge]

The Elastic APM OpenTelemetry bridge allows you to create Elastic APM `Transactions` and `Spans`, using the OpenTelemetry API. This allows users to utilize the Elastic APM agent’s automatic instrumentations, while keeping custom instrumentations vendor neutral.

If a span is created while there is no transaction active, it will result in an Elastic APM [`Transaction`](docs-content://solutions/observability/apps/transactions.md). Inner spans are mapped to Elastic APM [`Span`](docs-content://solutions/observability/apps/spans.md).


## Getting started [opentelemetry-getting-started]

The first step in getting started with the OpenTelemetry bridge is to install the `opentelemetry` libraries:

```bash
pip install elastic-apm[opentelemetry]
```

Or if you already have installed `elastic-apm`:

```bash
pip install opentelemetry-api opentelemetry-sdk
```


## Usage [opentelemetry-usage]

```python
from elasticapm.contrib.opentelemetry import Tracer

tracer = Tracer(__name__)
with tracer.start_as_current_span("test"):
    # Do some work
```

or

```python
from elasticapm.contrib.opentelemetry import trace

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("test"):
    # Do some work
```

`Tracer` and `get_tracer()` accept the following optional arguments:

* `elasticapm_client`: an already instantiated Elastic APM client
* `config`: a configuration dictionary, which will be used to instantiate a new Elastic APM client, e.g. `{"SERVER_URL": "https://example.org"}`. See [configuration](/reference/configuration.md) for more information.

The `Tracer` object mirrors the upstream interface on the [OpenTelemetry `Tracer` object.](https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html#opentelemetry.trace.Tracer)


## Caveats [opentelemetry-caveats]

Not all features of the OpenTelemetry API are supported.

Processors, exporters, metrics, logs, span events, and span links are not supported.

Additionally, due to implementation details, the global context API only works when a span is included in the activated context, and tokens are not used. Instead, the global context works as a stack, and when a context is detached the previously-active context will automatically be activated.

