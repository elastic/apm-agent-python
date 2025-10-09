---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/api.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# API reference [api]

The Elastic APM Python agent has several public APIs. Most of the public API functionality is not needed when using one of our [supported frameworks](/reference/supported-technologies.md#framework-support), but they allow customized usage.


## Client API [client-api]

The public Client API consists of several methods on the `Client` class. This API can be used to track exceptions and log messages, as well as to mark the beginning and end of transactions.


### Instantiation [client-api-init]

```{applies_to}
apm_agent_python: ga 1.0.0
```

To create a `Client` instance, import it and call its constructor:

```python
from elasticapm import Client

client = Client({'SERVICE_NAME': 'example'}, **defaults)
```

* `config`: A dictionary, with key/value configuration. For the possible configuration keys, see [Configuration](/reference/configuration.md).
* `**defaults`: default values for configuration. These can be omitted in most cases, and take the least precedence.

::::{note}
framework integrations like [Django](/reference/django-support.md) and [Flask](/reference/flask-support.md) instantiate the client automatically.
::::



#### `elasticapm.get_client()` [api-get-client]

```{applies_to}
apm_agent_python: ga 6.1.0
```

Retrieves the `Client` singleton. This is useful for many framework integrations, where the client is instantiated automatically.

```python
client = elasticapm.get_client()
client.capture_message('foo')
```


### Errors [error-api]


#### `Client.capture_exception()` [client-api-capture-exception]

```{applies_to}
apm_agent_python: ga 1.0.0
```

`handled` added in v2.0.0.

Captures an exception object:

```python
try:
    x = int("five")
except ValueError:
    client.capture_exception()
```

* `exc_info`: A `(type, value, traceback)` tuple as returned by [`sys.exc_info()`](https://docs.python.org/3/library/sys.html#sys.exc_info). If not provided, it will be captured automatically.
* `date`: A `datetime.datetime` object representing the occurrence time of the error. If left empty, it defaults to `datetime.datetime.utcnow()`.
* `context`: A dictionary with contextual information. This dictionary must follow the [Context](docs-content://solutions/observability/apm/elastic-apm-events-intake-api.md#apm-api-error) schema definition.
* `custom`: A dictionary of custom data you want to attach to the event.
* `handled`: A boolean to indicate if this exception was handled or not.

Returns the id of the error as a string.


#### `Client.capture_message()` [client-api-capture-message]

```{applies_to}
apm_agent_python: ga 1.0.0
```

Captures a message with optional added contextual data. Example:

```python
client.capture_message('Billing process succeeded.')
```

* `message`: The message as a string.
* `param_message`: Alternatively, a parameterized message as a dictionary. The dictionary contains two values: `message`, and `params`. This allows the APM Server to group messages together that share the same parameterized message. Example:

    ```python
    client.capture_message(param_message={
        'message': 'Billing process for %s succeeded. Amount: %s',
        'params': (customer.id, order.total_amount),
    })
    ```

* `stack`: If set to `True` (the default), a stacktrace from the call site will be captured.
* `exc_info`: A `(type, value, traceback)` tuple as returned by [`sys.exc_info()`](https://docs.python.org/3/library/sys.html#sys.exc_info). If not provided, it will be captured automatically, if `capture_message()` was called in an `except` block.
* `date`: A `datetime.datetime` object representing the occurrence time of the error. If left empty, it defaults to `datetime.datetime.utcnow()`.
* `context`: A dictionary with contextual information. This dictionary must follow the [Context](docs-content://solutions/observability/apm/elastic-apm-events-intake-api.md#apm-api-error) schema definition.
* `custom`: A dictionary of custom data you want to attach to the event.

Returns the id of the message as a string.

::::{note}
Either the `message` or the `param_message` argument is required.
::::



### Transactions [transaction-api]


#### `Client.begin_transaction()` [client-api-begin-transaction]

```{applies_to}
apm_agent_python: ga 1.0.0
```

`trace_parent` support added in v5.6.0.

Begin tracking a transaction. Should be called e.g. at the beginning of a request or when starting a background task. Example:

```python
client.begin_transaction('processors')
```

* `transaction_type`: (**required**) A string describing the type of the transaction, e.g. `'request'` or `'celery'`.
* `trace_parent`: (**optional**) A `TraceParent` object. See [TraceParent generation](#traceparent-api).
* `links`: (**optional**) A list of `TraceParent` objects to which this transaction is causally linked.


#### `Client.end_transaction()` [client-api-end-transaction]

```{applies_to}
apm_agent_python: ga 1.0.0
```

End tracking the transaction. Should be called e.g. at the end of a request or when ending a background task. Example:

```python
client.end_transaction('myapp.billing_process', processor.status)
```

* `name`: (**optional**) A string describing the name of the transaction, e.g. `process_order`. This is typically the name of the view/controller that handles the request, or the route name.
* `result`: (**optional**) A string describing the result of the transaction. This is typically the HTTP status code, or e.g. `'success'` for a background task.

::::{note}
if `name` and `result` are not set in the `end_transaction()` call, they have to be set beforehand by calling [`elasticapm.set_transaction_name()`](#api-set-transaction-name) and [`elasticapm.set_transaction_result()`](#api-set-transaction-result) during the transaction.
::::



### `TraceParent` [traceparent-api]

Transactions can be started with a `TraceParent` object. This creates a transaction that is a child of the `TraceParent`, which is essential for distributed tracing.


#### `elasticapm.trace_parent_from_string()` [api-traceparent-from-string]

```{applies_to}
apm_agent_python: ga 5.6.0
```

Create a `TraceParent` object from the string representation generated by `TraceParent.to_string()`:

```python
parent = elasticapm.trace_parent_from_string('00-03d67dcdd62b7c0f7a675424347eee3a-5f0e87be26015733-01')
client.begin_transaction('processors', trace_parent=parent)
```

* `traceparent_string`: (**required**) A string representation of a `TraceParent` object.


#### `elasticapm.trace_parent_from_headers()` [api-traceparent-from-headers]

```{applies_to}
apm_agent_python: ga 5.6.0
```

Create a `TraceParent` object from HTTP headers (usually generated by another Elastic APM agent):

```python
parent = elasticapm.trace_parent_from_headers(headers_dict)
client.begin_transaction('processors', trace_parent=parent)
```

* `headers`: (**required**) HTTP headers formed as a dictionary.


#### `elasticapm.get_trace_parent_header()` [api-traceparent-get-header]

```{applies_to}
apm_agent_python: ga 5.10.0
```

Return the string representation of the current transaction `TraceParent` object:

```python
elasticapm.get_trace_parent_header()
```


## Other APIs [api-other]


### `elasticapm.instrument()` [api-elasticapm-instrument]

```{applies_to}
apm_agent_python: ga 1.0.0
```

Instruments libraries automatically. This includes a wide range of standard library and 3rd party modules. A list of instrumented modules can be found in `elasticapm.instrumentation.register`. This function should be called as early as possible in the startup of your application. For [supported frameworks](/reference/supported-technologies.md#framework-support), this is called automatically. Example:

```python
import elasticapm

elasticapm.instrument()
```


### `elasticapm.set_transaction_name()` [api-set-transaction-name]

```{applies_to}
apm_agent_python: ga 1.0.0
```

Set the name of the current transaction. For supported frameworks, the transaction name is determined automatically, and can be overridden using this function. Example:

```python
import elasticapm

elasticapm.set_transaction_name('myapp.billing_process')
```

* `name`: (**required**) A string describing name of the transaction
* `override`: if `True` (the default), overrides any previously set transaction name. If `False`, only sets the name if the transaction name hasn’t already been set.


### `elasticapm.set_transaction_result()` [api-set-transaction-result]

```{applies_to}
apm_agent_python: ga 2.2.0
```

Set the result of the current transaction. For supported frameworks, the transaction result is determined automatically, and can be overridden using this function. Example:

```python
import elasticapm

elasticapm.set_transaction_result('SUCCESS')
```

* `result`: (**required**) A string describing the result of the transaction, e.g. `HTTP 2xx` or `SUCCESS`
* `override`: if `True` (the default), overrides any previously set result. If `False`, only sets the result if the result hasn’t already been set.


### `elasticapm.set_transaction_outcome()` [api-set-transaction-outcome]

```{applies_to}
apm_agent_python: ga 5.9.0
```

Sets the outcome of the transaction. The value can either be `"success"`, `"failure"` or `"unknown"`. This should only be called at the end of a transaction after the outcome is determined.

The `outcome` is used for error rate calculations. `success` denotes that a transaction has concluded successful, while `failure` indicates that the transaction failed to finish successfully. If the `outcome` is set to `unknown`, the transaction will not be included in error rate calculations.

For supported web frameworks, the transaction outcome is set automatically if it has not been set yet, based on the HTTP status code. A status code below `500` is considered a `success`, while any value of `500` or higher is counted as a `failure`.

If your transaction results in an HTTP response, you can alternatively provide the HTTP status code.

::::{note}
While the `outcome` and `result` field look very similar, they serve different purposes. Other than the `result` field, which canhold an arbitrary string value, `outcome` is limited to three different values, `"success"`, `"failure"` and `"unknown"`. This allows the APM app to perform error rate calculations on these values.
::::


Example:

```python
import elasticapm

elasticapm.set_transaction_outcome("success")

# Using an HTTP status code
elasticapm.set_transaction_outcome(http_status_code=200)

# Using predefined constants:

from elasticapm.conf.constants import OUTCOME

elasticapm.set_transaction_outcome(OUTCOME.SUCCESS)
elasticapm.set_transaction_outcome(OUTCOME.FAILURE)
elasticapm.set_transaction_outcome(OUTCOME.UNKNOWN)
```

* `outcome`: One of `"success"`, `"failure"` or `"unknown"`. Can be omitted if `http_status_code` is provided.
* `http_status_code`: if the transaction represents an HTTP response, its status code can be provided to determine the `outcome` automatically.
* `override`: if `True` (the default), any previously set `outcome` will be overridden. If `False`, the outcome will only be set if it was not set before.


### `elasticapm.get_transaction_id()` [api-get-transaction-id]

```{applies_to}
apm_agent_python: ga 5.2.0
```

Get the id of the current transaction. Example:

```python
import elasticapm

transaction_id = elasticapm.get_transaction_id()
```


### `elasticapm.get_trace_id()` [api-get-trace-id]

```{applies_to}
apm_agent_python: ga 5.2.0
```

Get the `trace_id` of the current transaction’s trace. Example:

```python
import elasticapm

trace_id = elasticapm.get_trace_id()
```


### `elasticapm.get_span_id()` [api-get-span-id]

```{applies_to}
apm_agent_python: ga 5.2.0
```

Get the id of the current span. Example:

```python
import elasticapm

span_id = elasticapm.get_span_id()
```


### `elasticapm.set_custom_context()` [api-set-custom-context]

```{applies_to}
apm_agent_python: ga 2.0.0
```

Attach custom contextual data to the current transaction and errors. Supported frameworks will automatically attach information about the HTTP request and the logged in user. You can attach further data using this function.

::::{tip}
Before using custom context, ensure you understand the different types of [metadata](docs-content://solutions/observability/apm/metadata.md) that are available.
::::


Example:

```python
import elasticapm

elasticapm.set_custom_context({'billing_amount': product.price * item_count})
```

* `data`: (**required**) A dictionary with the data to be attached. This should be a flat key/value `dict` object.

::::{note}
`.`, `*`, and `"` are invalid characters for key names and will be replaced with `_`.
::::


Errors that happen after this call will also have the custom context attached to them. You can call this function multiple times, new context data will be merged with existing data, following the `update()` semantics of Python dictionaries.


### `elasticapm.set_user_context()` [api-set-user-context]

```{applies_to}
apm_agent_python: ga 2.0.0
```

Attach information about the currently logged in user to the current transaction and errors. Example:

```python
import elasticapm

elasticapm.set_user_context(username=user.username, email=user.email, user_id=user.id)
```

* `username`: The username of the logged in user
* `email`: The email of the logged in user
* `user_id`: The unique identifier of the logged in user, e.g. the primary key value

Errors that happen after this call will also have the user context attached to them. You can call this function multiple times, new user data will be merged with existing data, following the `update()` semantics of Python dictionaries.


### `elasticapm.capture_span` [api-capture-span]

```{applies_to}
apm_agent_python: ga 4.1.0
```

Capture a custom span. This can be used either as a function decorator or as a context manager (in a `with` statement). When used as a decorator, the name of the span will be set to the name of the function. When used as a context manager, a name has to be provided.

```python
import elasticapm

@elasticapm.capture_span()
def coffee_maker(strength):
    fetch_water()

    with elasticapm.capture_span('near-to-machine', labels={"type": "arabica"}):
        insert_filter()
        for i in range(strength):
            pour_coffee()

        start_drip()

    fresh_pots()
```

* `name`: The name of the span. Defaults to the function name if used as a decorator.
* `span_type`: (**optional**) The type of the span, usually in a dot-separated hierarchy of `type`, `subtype`, and `action`, e.g. `db.mysql.query`. Alternatively, type, subtype and action can be provided as three separate arguments, see `span_subtype` and `span_action`.
* `skip_frames`: (**optional**) The number of stack frames to skip when collecting stack traces. Defaults to `0`.
* `leaf`: (**optional**) if `True`, all spans nested below this span will be ignored. Defaults to `False`.
* `labels`: (**optional**) a dictionary of labels. Keys must be strings, values can be strings, booleans, or numerical (`int`, `float`, `decimal.Decimal`). Defaults to `None`.
* `span_subtype`: (**optional**) subtype of the span, e.g. name of the database. Defaults to `None`.
* `span_action`: (**optional**) action of the span, e.g. `query`. Defaults to `None`.
* `links`: (**optional**) A list of `TraceParent` objects to which this span is causally linked.


### `elasticapm.async_capture_span` [api-async-capture-span]

```{applies_to}
apm_agent_python: ga 5.4.0
```

Capture a custom async-aware span. This can be used either as a function decorator or as a context manager (in an `async with` statement). When used as a decorator, the name of the span will be set to the name of the function. When used as a context manager, a name has to be provided.

```python
import elasticapm

@elasticapm.async_capture_span()
async def coffee_maker(strength):
    await fetch_water()

    async with elasticapm.async_capture_span('near-to-machine', labels={"type": "arabica"}):
        await insert_filter()
        async for i in range(strength):
            await pour_coffee()

        start_drip()

    fresh_pots()
```

* `name`: The name of the span. Defaults to the function name if used as a decorator.
* `span_type`: (**optional**) The type of the span, usually in a dot-separated hierarchy of `type`, `subtype`, and `action`, e.g. `db.mysql.query`. Alternatively, type, subtype and action can be provided as three separate arguments, see `span_subtype` and `span_action`.
* `skip_frames`: (**optional**) The number of stack frames to skip when collecting stack traces. Defaults to `0`.
* `leaf`: (**optional**) if `True`, all spans nested below this span will be ignored. Defaults to `False`.
* `labels`: (**optional**) a dictionary of labels. Keys must be strings, values can be strings, booleans, or numerical (`int`, `float`, `decimal.Decimal`). Defaults to `None`.
* `span_subtype`: (**optional**) subtype of the span, e.g. name of the database. Defaults to `None`.
* `span_action`: (**optional**) action of the span, e.g. `query`. Defaults to `None`.
* `links`: (**optional**) A list of `TraceParent` objects to which this span is causally linked.

::::{note}
`asyncio` is only supported for Python 3.7+.
::::



### `elasticapm.label()` [api-label]

```{applies_to}
apm_agent_python: ga 5.0.0
```

Attach labels to the the current transaction and errors.

::::{tip}
Before using custom labels, ensure you understand the different types of [metadata](docs-content://solutions/observability/apm/metadata.md) that are available.
::::


Example:

```python
import elasticapm

elasticapm.label(ecommerce=True, dollar_value=47.12)
```

Errors that happen after this call will also have the labels attached to them. You can call this function multiple times, new labels will be merged with existing labels, following the `update()` semantics of Python dictionaries.

Keys must be strings, values can be strings, booleans, or numerical (`int`, `float`, `decimal.Decimal`) `.`, `*`, and `"` are invalid characters for label names and will be replaced with `_`.

::::{warning}
Avoid defining too many user-specified labels. Defining too many unique fields in an index is a condition that can lead to a [mapping explosion](docs-content://manage-data/data-store/mapping.md#mapping-limit-settings).
::::


