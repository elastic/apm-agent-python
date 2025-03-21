---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/sanitizing-data.html
---

# Sanitizing data [sanitizing-data]

Sometimes it is necessary to sanitize the data sent to Elastic APM, e.g. remove sensitive data.

To do this with the Elastic APM module, you create a processor. A processor is a function that takes a `client` instance as well as an event (an error, a transaction, a span, or a metricset), and returns the modified event.

To completely drop an event, your processor should return `False` (or any other "falsy" value) instead of the event.

An event will also be dropped if any processor raises an exception while processing it. A log message with level `WARNING` will be issued in this case.

This is an example of a processor that removes the exception stacktrace from an error:

```python
from elasticapm.conf.constants import ERROR
from elasticapm.processors import for_events

@for_events(ERROR)
def my_processor(client, event):
    if 'exception' in event and 'stacktrace' in event['exception']:
        event['exception'].pop('stacktrace')
    return event
```

You can use the `@for_events` decorator to limit for which event type the processor should be called. Possible choices are `ERROR`, `TRANSACTION`, `SPAN` and `METRICSET`, all of which are defined in `elasticapm.conf.constants`.

To use this processor, update your `ELASTIC_APM` settings like this:

```python
ELASTIC_APM = {
    'SERVICE_NAME': '<SERVICE-NAME>',
    'SECRET_TOKEN': '<SECRET-TOKEN>',
    'PROCESSORS': (
        'path.to.my_processor',
        'elasticapm.processors.sanitize_stacktrace_locals',
        'elasticapm.processors.sanitize_http_request_cookies',
        'elasticapm.processors.sanitize_http_headers',
        'elasticapm.processors.sanitize_http_wsgi_env',
        'elasticapm.processors.sanitize_http_request_body',
    ),
}
```

::::{note}
We recommend using the above list of processors that sanitize passwords and secrets in different places of the event object.
::::


The default set of processors sanitize fields based on a set of defaults defined in `elasticapm.conf.constants`. This set can be configured with the `SANITIZE_FIELD_NAMES` configuration option. For example, if your application produces a sensitive field called `My-Sensitive-Field`, the default processors can be used to automatically sanitize this field. You can specify what fields to santize within default processors like this:

```python
ELASTIC_APM = {
    'SERVICE_NAME': '<SERVICE-NAME>',
    'SECRET_TOKEN': '<SECRET-TOKEN>',
    'SANITIZE_FIELD_NAMES': (
        "password",
        "passwd",
        "pwd",
        "secret",
        "*key",
        "*token*",
        "*session*",
        "*credit*",
        "*card*",
        "*auth*",
        "set-cookie",
    ),
}
```

::::{note}
We recommend to use the above list of fields to sanitize various parts of the event object in addition to your specified fields.
::::


When choosing fields names to sanitize, you can specify values that will match certain wildcards. For example, passing `base` as a field name to be sanitized will also sanitize all fields whose names match the regex pattern `\*base*`.

