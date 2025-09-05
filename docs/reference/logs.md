---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/logs.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# Logs [logs]

Elastic Python APM Agent provides the following log features:

* [Log correlation](#log-correlation-ids) : Automatically inject correlation IDs that allow navigation between logs, traces and services.
* [Log reformatting (experimental)](#log-reformatting) : Automatically reformat plaintext logs in [ECS logging](ecs-logging://reference/intro.md) format.

::::{note}
Elastic Python APM Agent does not send the logs to Elasticsearch. It only injects correlation IDs and reformats the logs. You must use another ingestion strategy.  We recommend [Filebeat](https://www.elastic.co/beats/filebeat) for that purpose.
::::


Those features are part of [Application log ingestion strategies](docs-content://solutions/observability/logs/stream-application-logs.md).

The [`ecs-logging-python`](ecs-logging-python://reference/index.md) library can also be used to use the [ECS logging](ecs-logging://reference/intro.md) format without an APM agent. When deployed with the Python APM agent, the agent will provide [log correlation](#log-correlation-ids) IDs.


## Log correlation [log-correlation-ids]

[Log correlation](docs-content://solutions/observability/logs/stream-application-logs.md) allows you to navigate to all logs belonging to a particular trace and vice-versa: for a specific log, see in which context it has been logged and which parameters the user provided.

The Agent provides integrations with both the default Python logging library, as well as [`structlog`](http://www.structlog.org/en/stable/).

* [Logging integrations](#logging-integrations)
* [Log correlation in Elasticsearch](#log-correlation-in-es)


### Logging integrations [logging-integrations]


#### `logging` [logging]

We use [`logging.setLogRecordFactory()`](https://docs.python.org/3/library/logging.html#logging.setLogRecordFactory) to decorate the default LogRecordFactory to automatically add new attributes to each LogRecord object:

* `elasticapm_transaction_id`
* `elasticapm_trace_id`
* `elasticapm_span_id`

This factory also adds these fields to a dictionary attribute, `elasticapm_labels`, using the official ECS [tracing fields](ecs://reference/ecs-tracing.md).

You can disable this automatic behavior by using the [`disable_log_record_factory`](/reference/configuration.md#config-generic-disable-log-record-factory) setting in your configuration.


#### `structlog` [structlog]

We provide a [processor](http://www.structlog.org/en/stable/processors.html) for [`structlog`](http://www.structlog.org/en/stable/) which will add three new keys to the event_dict of any processed event:

* `transaction.id`
* `trace.id`
* `span.id`

```python
from structlog import PrintLogger, wrap_logger
from structlog.processors import JSONRenderer
from elasticapm.handlers.structlog import structlog_processor

wrapped_logger = PrintLogger()
logger = wrap_logger(wrapped_logger, processors=[structlog_processor, JSONRenderer()])
log = logger.new()
log.msg("some_event")
```


#### Use structlog for agent-internal logging [_use_structlog_for_agent_internal_logging]

The Elastic APM Python agent uses logging to log internal events and issues. By default, it will use a `logging` logger. If your project uses structlog, you can tell the agent to use a structlog logger by setting the environment variable `ELASTIC_APM_USE_STRUCTLOG` to `true`.


## Log correlation in Elasticsearch [log-correlation-in-es]

In order to correlate logs from your app with transactions captured by the Elastic APM Python Agent, your logs must contain one or more of the following identifiers:

* `transaction.id`
* `trace.id`
* `span.id`

If you’re using structured logging, either [with a custom solution](https://docs.python.org/3/howto/logging-cookbook.html#implementing-structured-logging) or with [structlog](http://www.structlog.org/en/stable/) (recommended), then this is fairly easy. Throw the [JSONRenderer](http://www.structlog.org/en/stable/api.html#structlog.processors.JSONRenderer) in, and use [Filebeat](https://www.elastic.co/blog/structured-logging-filebeat) to pull these logs into Elasticsearch.

Without structured logging the task gets a little trickier. Here we recommend first making sure your LogRecord objects have the elasticapm attributes (see [`logging`](#logging)), and then you’ll want to combine some specific formatting with a Grok pattern, either in Elasticsearch using [the grok processor](elasticsearch://reference/enrich-processor/grok-processor.md), or in [logstash with a plugin](logstash-docs-md://lsr/plugins-filters-grok.md).

Say you have a [Formatter](https://docs.python.org/3/library/logging.html#logging.Formatter) that looks like this:

```python
import logging

fh = logging.FileHandler('spam.log')
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
```

You can add the APM identifiers by simply switching out the `Formatter` object for the one that we provide:

```python
import logging
from elasticapm.handlers.logging import Formatter

fh = logging.FileHandler('spam.log')
formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
```

This will automatically append apm-specific fields to your format string:

```python
formatstring = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
formatstring = formatstring + " | elasticapm " \
                              "transaction.id=%(elasticapm_transaction_id)s " \
                              "trace.id=%(elasticapm_trace_id)s " \
                              "span.id=%(elasticapm_span_id)s"
```

Then, you could use a grok pattern like this (for the [Elasticsearch Grok Processor](elasticsearch://reference/enrich-processor/grok-processor.md)):

```json
{
  "description" : "...",
  "processors": [
    {
      "grok": {
        "field": "message",
        "patterns": ["%{GREEDYDATA:msg} | elasticapm transaction.id=%{DATA:transaction.id} trace.id=%{DATA:trace.id} span.id=%{DATA:span.id}"]
      }
    }
  ]
}
```


## Log reformatting (experimental) [log-reformatting]

Starting in version 6.16.0, the agent can automatically reformat application logs to ECS format with no changes to dependencies. Prior versions must install the `ecs_logging` dependency.

Log reformatting is controlled by the [`log_ecs_reformatting`](/reference/configuration.md#config-log_ecs_reformatting) configuration option, and is disabled by default.

The reformatted logs will include both the [trace and service correlation](#log-correlation-ids) IDs.

