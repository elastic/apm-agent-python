---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/configuration.html
---

# Configuration [configuration]

To adapt the Elastic APM agent to your needs, configure it using environment variables or framework-specific configuration.

You can either configure the agent by setting environment variables:

```bash
ELASTIC_APM_SERVICE_NAME=foo python manage.py runserver
```

or with inline configuration:

```python
apm_client = Client(service_name="foo")
```

or by using framework specific configuration e.g. in your Django `settings.py` file:

```python
ELASTIC_APM = {
    "SERVICE_NAME": "foo",
}
```

The precedence is as follows:

* [Central configuration](#config-central_config) (supported options are marked with [![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration))
* Environment variables
* Inline configuration
* Framework-specific configuration
* Default value


## Dynamic configuration [dynamic-configuration]

Configuration options marked with the ![dynamic config](/reference/images/dynamic-config.svg "") badge can be changed at runtime when set from a supported source.

The Python Agent supports [Central configuration](docs-content://solutions/observability/apps/apm-agent-central-configuration.md), which allows you to fine-tune certain configurations from in the APM app. This feature is enabled in the Agent by default with [`central_config`](#config-central_config).


## Django [django-configuration]

To configure Django, add an `ELASTIC_APM` dictionary to your `settings.py`:

```python
ELASTIC_APM = {
    'SERVICE_NAME': 'my-app',
    'SECRET_TOKEN': 'changeme',
}
```


## Flask [flask-configuration]

To configure Flask, add an `ELASTIC_APM` dictionary to your `app.config`:

```python
app.config['ELASTIC_APM'] = {
    'SERVICE_NAME': 'my-app',
    'SECRET_TOKEN': 'changeme',
}

apm = ElasticAPM(app)
```


## Core options [core-options]


### `service_name` [config-service-name]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_SERVICE_NAME` | `SERVICE_NAME` | `unknown-python-service` | `my-app` |

The name of your service. This is used to keep all the errors and transactions of your service together and is the primary filter in the Elastic APM user interface.

While a default is provided, it is essential that you override this default with something more descriptive and unique across your infrastructure.

::::{note}
The service name must conform to this regular expression: `^[a-zA-Z0-9 _-]+$`. In other words, the service name must only contain characters from the ASCII alphabet, numbers, dashes, underscores, and spaces. It cannot be an empty string or whitespace-only.
::::



### `server_url` [config-server-url]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SERVER_URL` | `SERVER_URL` | `'http://127.0.0.1:8200'` |

The URL for your APM Server. The URL must be fully qualified, including protocol (`http` or `https`) and port. Note: Do not set this if you are using APM in an AWS lambda function. APM Agents are designed to proxy their calls to the APM Server through the lambda extension. Instead, set `ELASTIC_APM_LAMBDA_APM_SERVER`. For more info, see [AWS Lambda](/reference/lambda-support.md).


## `enabled` [config-enabled]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_ENABLED` | `ENABLED` | `true` |

Enable or disable the agent. When set to false, the agent will not collect any data or start any background threads.


## `recording` [config-recording]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_RECORDING` | `RECORDING` | `true` |

Enable or disable recording of events. If set to false, then the Python agent does not send any events to the Elastic APM server, and instrumentation overhead is minimized. The agent will continue to poll the server for configuration changes.


## Logging Options [logging-options]


### `log_level` [config-log_level]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_LOG_LEVEL` | `LOG_LEVEL` |  |

The `logging.logLevel` at which the `elasticapm` logger will log. The available options are:

* `"off"` (sets `logging.logLevel` to 1000)
* `"critical"`
* `"error"`
* `"warning"`
* `"info"`
* `"debug"`
* `"trace"` (sets `logging.log_level` to 5)

Options are case-insensitive

Note that this option doesn’t do anything with logging handlers. In order for any logs to be visible, you must either configure a handler ([`logging.basicConfig`](https://docs.python.org/3/library/logging.html#logging.basicConfig) will do this for you) or set [`log_file`](#config-log_file). This will also override any log level your app has set for the `elasticapm` logger.


### `log_file` [config-log_file]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_LOG_FILE` | `LOG_FILE` | `""` | `"/var/log/elasticapm/log.txt"` |

This enables the agent to log to a file. This is disabled by default. The agent will log at the `logging.logLevel` configured with [`log_level`](#config-log_level). Use [`log_file_size`](#config-log_file_size) to configure the maximum size of the log file. This log file will automatically rotate.

Note that setting [`log_level`](#config-log_level) is required for this setting to do anything.

If [`ecs_logging`](https://github.com/elastic/ecs-logging-python) is installed, the logs will automatically be formatted as ecs-compatible json.


### `log_file_size` [config-log_file_size]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_LOG_FILE_SIZE` | `LOG_FILE_SIZE` | `"50mb"` | `"100mb"` |

The size of the log file if [`log_file`](#config-log_file) is set.

The agent always keeps one backup file when rotating, so the maximum space that the log files will consume is twice the value of this setting.


### `log_ecs_reformatting` [config-log_ecs_reformatting]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_LOG_ECS_REFORMATTING` | `LOG_ECS_REFORMATTING` | `"off"` |

::::{warning}
This functionality is in technical preview and may be changed or removed in a future release. Elastic will work to fix any issues, but features in technical preview are not subject to the support SLA of official GA features.
::::


Valid options:

* `"off"`
* `"override"`

If [`ecs_logging`](https://github.com/elastic/ecs-logging-python) is installed, setting this to `"override"` will cause the agent to automatically attempt to enable ecs-formatted logging.

For base `logging` from the standard library, the agent will get the root logger, find any attached handlers, and for each, set the formatter to `ecs_logging.StdlibFormatter()`.

If `structlog` is installed, the agent will override any configured processors with `ecs_logging.StructlogFormatter()`.

Note that this is a very blunt instrument that could have unintended side effects. If problems arise, please apply these formatters manually and leave this setting as `"off"`. See the [`ecs_logging` docs](ecs-logging-python://reference/installation.md) for more information about using these formatters.

Also note that this setting does not facilitate shipping logs to Elasticsearch. We recommend [Filebeat](https://www.elastic.co/beats/filebeat) for that purpose.


## Other options [other-options]


### `transport_class` [config-transport-class]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_TRANSPORT_CLASS` | `TRANSPORT_CLASS` | `elasticapm.transport.http.Transport` |

The transport class to use when sending events to the APM Server.


### `service_node_name` [config-service-node-name]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_SERVICE_NODE_NAME` | `SERVICE_NODE_NAME` | `None` | `"redis1"` |

The name of the given service node. This is optional and if omitted, the APM Server will fall back on `system.container.id` if available, and `host.name` if necessary.

This option allows you to set the node name manually to ensure it is unique and meaningful.


### `environment` [config-environment]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_ENVIRONMENT` | `ENVIRONMENT` | `None` | `"production"` |

The name of the environment this service is deployed in, e.g. "production" or "staging".

Environments allow you to easily filter data on a global level in the APM app. It’s important to be consistent when naming environments across agents. See [environment selector](docs-content://solutions/observability/apps/filter-application-data.md#apm-filter-your-data-service-environment-filter) in the APM app for more information.

::::{note}
This feature is fully supported in the APM app in Kibana versions >= 7.2. You must use the query bar to filter for a specific environment in versions prior to 7.2.
::::



### `cloud_provider` [config-cloud-provider]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_CLOUD_PROVIDER` | `CLOUD_PROVIDER` | `"auto"` | `"aws"` |

This config value allows you to specify which cloud provider should be assumed for metadata collection. By default, the agent will attempt to detect the cloud provider or, if that fails, will use trial and error to collect the metadata.

Valid options are `"auto"`, `"aws"`, `"gcp"`, and `"azure"`. If this config value is set to `"none"`, then no cloud metadata will be collected.


### `secret_token` [config-secret-token]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_SECRET_TOKEN` | `SECRET_TOKEN` | `None` | A random string |

This string is used to ensure that only your agents can send data to your APM Server. Both the agents and the APM Server have to be configured with the same secret token. An example to generate a secure secret token is:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

::::{warning}
Secret tokens only provide any security if your APM Server uses TLS.
::::



### `api_key` [config-api-key]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_API_KEY` | `API_KEY` | `None` | A base64-encoded string |

::::{warning}
This functionality is in technical preview and may be changed or removed in a future release. Elastic will work to fix any issues, but features in technical preview are not subject to the support SLA of official GA features.
::::


This base64-encoded string is used to ensure that only your agents can send data to your APM Server. The API key must be created using the [APM server command-line tool](docs-content://solutions/observability/apps/api-keys.md).

::::{warning}
API keys only provide any real security if your APM Server uses TLS.
::::



### `service_version` [config-service-version]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_SERVICE_VERSION` | `SERVICE_VERSION` | `None` | A string indicating the version of the deployed service |

A version string for the currently deployed version of the service. If youre deploys are not versioned, the recommended value for this field is the commit identifier of the deployed revision, e.g. the output of `git rev-parse HEAD`.


### `framework_name` [config-framework-name]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_FRAMEWORK_NAME` | `FRAMEWORK_NAME` | Depending on framework |

The name of the used framework. For Django and Flask, this defaults to `django` and `flask` respectively, otherwise, the default is `None`.


### `framework_version` [config-framework-version]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_FRAMEWORK_VERSION` | `FRAMEWORK_VERSION` | Depending on framework |

The version number of the used framework. For Django and Flask, this defaults to the used version of the framework, otherwise, the default is `None`.


### `filter_exception_types` [config-filter-exception-types]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_FILTER_EXCEPTION_TYPES` | `FILTER_EXCEPTION_TYPES` | `[]` | `['OperationalError', 'mymodule.SomeoneElsesProblemError']` |
| multiple values separated by commas, without spaces |  |  |  |

A list of exception types to be filtered. Exceptions of these types will not be sent to the APM Server.


### `transaction_ignore_urls` [config-transaction-ignore-urls]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_TRANSACTION_IGNORE_URLS` | `TRANSACTION_IGNORE_URLS` | `[]` | `['/api/ping', '/static/*']` |
| multiple values separated by commas, without spaces |  |  |  |

A list of URLs for which the agent should not capture any transaction data.

Optionally, `*` can be used to match multiple URLs at once.


### `transactions_ignore_patterns` [config-transactions-ignore-patterns]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_TRANSACTIONS_IGNORE_PATTERNS` | `TRANSACTIONS_IGNORE_PATTERNS` | `[]` | `['^OPTIONS ', 'myviews.Healthcheck']` |
| multiple values separated by commas, without spaces |  |  |  |

A list of regular expressions. Transactions with a name that matches any of the configured patterns will be ignored and not sent to the APM Server.

::::{note}
as the the name of the transaction can only be determined at the end of the transaction, the agent might still cause overhead for transactions ignored through this setting. If agent overhead is a concern, we recommend [`transaction_ignore_urls`](#config-transaction-ignore-urls) instead.
::::



### `server_timeout` [config-server-timeout]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SERVER_TIMEOUT` | `SERVER_TIMEOUT` | `"5s"` |

A timeout for requests to the APM Server. The setting has to be provided in **[duration format](#config-format-duration)**. If a request to the APM Server takes longer than the configured timeout, the request is cancelled and the event (exception or transaction) is discarded. Set to `None` to disable timeouts.

::::{warning}
If timeouts are disabled or set to a high value, your app could experience memory issues if the APM Server times out.
::::



### `hostname` [config-hostname]

| Environment | Django/Flask | Default | Example |
| --- | --- | --- | --- |
| `ELASTIC_APM_HOSTNAME` | `HOSTNAME` | `socket.gethostname()` | `app-server01.example.com` |

The host name to use when sending error and transaction data to the APM Server.


### `auto_log_stacks` [config-auto-log-stacks]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_AUTO_LOG_STACKS` | `AUTO_LOG_STACKS` | `True` |
| set to `"true"` / `"false"` |  |  |

If set to `True` (the default), the agent will add a stack trace to each log event, indicating where the log message has been issued.

This setting can be overridden on an individual basis by setting the `extra`-key `stack`:

```python
logger.info('something happened', extra={'stack': False})
```


### `collect_local_variables` [config-collect-local-variables]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_COLLECT_LOCAL_VARIABLES` | `COLLECT_LOCAL_VARIABLES` | `errors` |

Possible values: `errors`, `transactions`, `all`, `off`

The Elastic APM Python agent can collect local variables for stack frames. By default, this is only done for errors.

::::{note}
Collecting local variables has a non-trivial overhead. Collecting local variables for transactions in production environments can have adverse effects for the performance of your service.
::::



### `local_var_max_length` [config-local-var-max-length]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_LOCAL_VAR_MAX_LENGTH` | `LOCAL_VAR_MAX_LENGTH` | `200` |

When collecting local variables, they will be converted to strings. This setting allows you to limit the length of the resulting string.


### `local_var_list_max_length` [config-local-list-var-max-length]

|     |     |     |
| --- | --- | --- |
| Environment | Django/Flask | Default |
| `ELASTIC_APM_LOCAL_VAR_LIST_MAX_LENGTH` | `LOCAL_VAR_LIST_MAX_LENGTH` | `10` |

This setting allows you to limit the length of lists in local variables.


### `local_var_dict_max_length` [config-local-dict-var-max-length]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_LOCAL_VAR_DICT_MAX_LENGTH` | `LOCAL_VAR_DICT_MAX_LENGTH` | `10` |

This setting allows you to limit the length of dicts in local variables.


### `source_lines_error_app_frames` [config-source-lines-error-app-frames]


### `source_lines_error_library_frames` [config-source-lines-error-library-frames]


### `source_lines_span_app_frames` [config-source-lines-span-app-frames]


### `source_lines_span_library_frames` [config-source-lines-span-library-frames]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SOURCE_LINES_ERROR_APP_FRAMES` | `SOURCE_LINES_ERROR_APP_FRAMES` | `5` |
| `ELASTIC_APM_SOURCE_LINES_ERROR_LIBRARY_FRAMES` | `SOURCE_LINES_ERROR_LIBRARY_FRAMES` | `5` |
| `ELASTIC_APM_SOURCE_LINES_SPAN_APP_FRAMES` | `SOURCE_LINES_SPAN_APP_FRAMES` | `0` |
| `ELASTIC_APM_SOURCE_LINES_SPAN_LIBRARY_FRAMES` | `SOURCE_LINES_SPAN_LIBRARY_FRAMES` | `0` |

By default, the APM agent collects source code snippets for errors. This setting allows you to modify the number of lines of source code that are being collected.

We differ between errors and spans, as well as library frames and app frames.

::::{warning}
Especially for spans, collecting source code can have a large impact on storage use in your Elasticsearch cluster.
::::



### `capture_body` [config-capture-body]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_CAPTURE_BODY` | `CAPTURE_BODY` | `off` |

For transactions that are HTTP requests, the Python agent can optionally capture the request body (e.g. `POST` variables).

Possible values: `errors`, `transactions`, `all`, `off`.

If the request has a body and this setting is disabled, the body will be shown as `[REDACTED]`.

For requests with a content type of `multipart/form-data`, any uploaded files will be referenced in a special `_files` key. It contains the name of the field and the name of the uploaded file, if provided.

::::{warning}
Request bodies often contain sensitive values like passwords and credit card numbers. If your service handles data like this, we advise to only enable this feature with care.
::::



### `capture_headers` [config-capture-headers]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_CAPTURE_HEADERS` | `CAPTURE_HEADERS` | `true` |

For transactions and errors that happen due to HTTP requests, the Python agent can optionally capture the request and response headers.

Possible values: `true`, `false`

::::{warning}
Request headers often contain sensitive values like session IDs and cookies. See [sanitizing data](/reference/sanitizing-data.md) for more information on how to filter out sensitive data.
::::



### `transaction_max_spans` [config-transaction-max-spans]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_TRANSACTION_MAX_SPANS` | `TRANSACTION_MAX_SPANS` | `500` |

This limits the amount of spans that are recorded per transaction. This is helpful in cases where a transaction creates a very high amount of spans (e.g. thousands of SQL queries). Setting an upper limit will prevent edge cases from overloading the agent and the APM Server.


### `stack_trace_limit` [config-stack-trace-limit]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_STACK_TRACE_LIMIT` | `STACK_TRACE_LIMIT` | `50` |

This limits the number of frames captured for each stack trace.

Setting the limit to `0` will disable stack trace collection, while any positive integer value will be used as the maximum number of frames to collect. To disable the limit and always capture all frames, set the value to `-1`.


### `span_stack_trace_min_duration` [config-span-stack-trace-min-duration]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SPAN_STACK_TRACE_MIN_DURATION` | `SPAN_STACK_TRACE_MIN_DURATION` | `"5ms"` |

By default, the APM agent collects a stack trace with every recorded span that has a duration equal to or longer than this configured threshold.  While stack traces are very helpful to find the exact place in your code from which a span originates, collecting this stack trace does have some overhead. Tune this threshold to ensure that you only collect stack traces for spans that could be problematic.

To collect traces for all spans, regardless of their length, set the value to `0`.

To disable stack trace collection for spans completely, set the value to `-1`.

Except for the special values `-1` and `0`, this setting should be provided in **[duration format](#config-format-duration)**.


### `span_frames_min_duration` [config-span-frames-min-duration]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SPAN_FRAMES_MIN_DURATION` | `SPAN_FRAMES_MIN_DURATION` | `"5ms"` |

::::{note}
This config value is being deprecated. Use [`span_stack_trace_min_duration`](#config-span-stack-trace-min-duration) instead.
::::



### `span_compression_enabled` [config-span-compression-enabled]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SPAN_COMPRESSION_ENABLED` | `SPAN_COMPRESSION_ENABLED` | `True` |

Enable/disable span compression.

If enabled, the agent will compress very short, repeated spans into a single span, which is beneficial for storage and processing requirements. Some information is lost in this process, e.g. exact durations of each compressed span.


### `span_compression_exact_match_max_duration` [config-span-compression-exact-match-max_duration]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SPAN_COMPRESSION_EXACT_MATCH_MAX_DURATION` | `SPAN_COMPRESSION_EXACT_MATCH_MAX_DURATION` | `"50ms"` |

Consecutive spans that are exact match and that are under this threshold will be compressed into a single composite span. This reduces the collection, processing, and storage overhead, and removes clutter from the UI. The tradeoff is that the DB statements of all the compressed spans will not be collected.

Two spans are considered exact matches if the following attributes are identical: * span name * span type * span subtype * destination resource (e.g. the Database name)


### `span_compression_same_kind_max_duration` [config-span-compression-same-kind-max-duration]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SPAN_COMPRESSION_SAME_KIND_MAX_DURATION` | `SPAN_COMPRESSION_SAME_KIND_MAX_DURATION` | `"0ms"` (disabled) |

Consecutive spans to the same destination that are under this threshold will be compressed into a single composite span. This reduces the collection, processing, and storage overhead, and removes clutter from the UI. The tradeoff is that metadata such as database statements of all the compressed spans will not be collected.

Two spans are considered to be of the same kind if the following attributes are identical: * span type * span subtype * destination resource (e.g. the Database name)


### `exit_span_min_duration` [config-exit-span-min-duration]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_EXIT_SPAN_MIN_DURATION` | `EXIT_SPAN_MIN_DURATION` | `"0ms"` |

Exit spans are spans that represent a call to an external service, like a database. If such calls are very short, they are usually not relevant and can be ignored.

This feature is disabled by default.

::::{note}
if a span propagates distributed tracing IDs, it will not be ignored, even if it is shorter than the configured threshold. This is to ensure that no broken traces are recorded.
::::



### `api_request_size` [config-api-request-size]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_API_REQUEST_SIZE` | `API_REQUEST_SIZE` | `"768kb"` |

The maximum queue length of the request buffer before sending the request to the APM Server. A lower value will increase the load on your APM Server, while a higher value can increase the memory pressure of your app. A higher value also impacts the time until data is indexed and searchable in Elasticsearch.

This setting is useful to limit memory consumption if you experience a sudden spike of traffic. It has to be provided in **[size format](#config-format-size)**.

::::{note}
Due to internal buffering of gzip, the actual request size can be a few kilobytes larger than the given limit. By default, the APM Server limits request payload size to `1 MByte`.
::::



### `api_request_time` [config-api-request-time]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_API_REQUEST_TIME` | `API_REQUEST_TIME` | `"10s"` |

The maximum queue time of the request buffer before sending the request to the APM Server. A lower value will increase the load on your APM Server, while a higher value can increase the memory pressure of your app. A higher value also impacts the time until data is indexed and searchable in Elasticsearch.

This setting is useful to limit memory consumption if you experience a sudden spike of traffic. It has to be provided in **[duration format](#config-format-duration)**.

::::{note}
The actual time will vary between 90-110% of the given value, to avoid stampedes of instances that start at the same time.
::::



### `processors` [config-processors]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_PROCESSORS` | `PROCESSORS` | `['elasticapm.processors.sanitize_stacktrace_locals',                                              'elasticapm.processors.sanitize_http_request_cookies',                                              'elasticapm.processors.sanitize_http_headers',                                              'elasticapm.processors.sanitize_http_wsgi_env',                                              'elasticapm.processors.sanitize_http_request_body']` |

A list of processors to process transactions and errors. For more information, see [Sanitizing Data](/reference/sanitizing-data.md).

::::{warning}
We recommend always including the default set of validators if you customize this setting.
::::



### `sanitize_field_names` [config-sanitize-field-names]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SANITIZE_FIELD_NAMES` | `SANITIZE_FIELD_NAMES` | `["password",                                                                  "passwd",                                                                  "pwd",                                                                  "secret",                                                                  "*key",                                                                  "*token*",                                                                  "*session*",                                                                  "*credit*",                                                                  "*card*",                                                                  "*auth*",                                                                  "*principal*",                                                                  "set-cookie"]` |

A list of glob-matched field names to match and mask when using processors. For more information, see [Sanitizing Data](/reference/sanitizing-data.md).

::::{warning}
We recommend always including the default set of field name matches if you customize this setting.
::::



### `transaction_sample_rate` [config-transaction-sample-rate]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_TRANSACTION_SAMPLE_RATE` | `TRANSACTION_SAMPLE_RATE` | `1.0` |

By default, the agent samples every transaction (e.g. request to your service). To reduce overhead and storage requirements, set the sample rate to a value between `0.0` and `1.0`. We still record overall time and the result for unsampled transactions, but no context information, labels, or spans.

::::{note}
This setting will be automatically rounded to 4 decimals of precision.
::::



### `include_paths` [config-include-paths]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_INCLUDE_PATHS` | `INCLUDE_PATHS` | `[]` |
| multiple values separated by commas, without spaces |  |  |

A set of paths, optionally using shell globs (see [`fnmatch`](https://docs.python.org/3/library/fnmatch.html) for a description of the syntax). These are matched against the absolute filename of every frame, and if a pattern matches, the frame is considered to be an "in-app frame".

`include_paths` **takes precedence** over `exclude_paths`.


### `exclude_paths` [config-exclude-paths]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_EXCLUDE_PATHS` | `EXCLUDE_PATHS` | Varies on Python version and implementation |
| multiple values separated by commas, without spaces |  |  |

A set of paths, optionally using shell globs (see [`fnmatch`](https://docs.python.org/3/library/fnmatch.html) for a description of the syntax). These are matched against the absolute filename of every frame, and if a pattern matches, the frame is considered to be a "library frame".

`include_paths` **takes precedence** over `exclude_paths`.

The default value varies based on your Python version and implementation, e.g.:

* PyPy3: `['\*/lib-python/3/*', '\*/site-packages/*']`
* CPython 2.7: `['\*/lib/python2.7/*', '\*/lib64/python2.7/*']`


### `debug` [config-debug]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_DEBUG` | `DEBUG` | `False` |

If your app is in debug mode (e.g. in Django with `settings.DEBUG = True` or in Flask with `app.debug = True`), the agent won’t send any data to the APM Server. You can override it by changing this setting to `True`.


### `disable_send` [config-disable-send]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_DISABLE_SEND` | `DISABLE_SEND` | `False` |

If set to `True`, the agent won’t send any events to the APM Server, independent of any debug state.


### `instrument` [config-instrument]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_INSTRUMENT` | `INSTRUMENT` | `True` |

If set to `False`, the agent won’t instrument any code. This disables most of the tracing functionality, but can be useful to debug possible instrumentation issues.


### `verify_server_cert` [config-verify-server-cert]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_VERIFY_SERVER_CERT` | `VERIFY_SERVER_CERT` | `True` |

By default, the agent verifies the SSL certificate if an HTTPS connection to the APM Server is used. Verification can be disabled by changing this setting to `False`. This setting is ignored when [`server_cert`](#config-server-cert) is set.


### `server_cert` [config-server-cert]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SERVER_CERT` | `SERVER_CERT` | `None` |

If you have configured your APM Server with a self-signed TLS certificate, or you just wish to pin the server certificate, you can specify the path to the PEM-encoded certificate via the `ELASTIC_APM_SERVER_CERT` configuration.

::::{note}
If this option is set, the agent only verifies that the certificate provided by the APM Server is identical to the one configured here. Validity of the certificate is not checked.
::::



### `server_ca_cert_file` [config-server-ca-cert-file]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_SERVER_CA_CERT_FILE` | `SERVER_CA_CERT_FILE` | `None` |

By default, the agent will validate the TLS/SSL certificate of the APM Server using the well-known CAs curated by Mozilla, and provided by the [`certifi`](https://pypi.org/project/certifi/) package.

You can set this option to the path of a file containing a CA certificate that will be used instead.

Specifying this option is required when using self-signed certificates, unless server certificate validation is disabled.


### `use_certifi` [config-use-certifi]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_USE_CERTIFI` | `USE_CERTIFI` | `True` |

By default, the Python Agent uses the [`certifi`](https://pypi.org/project/certifi/) certificate store. To use Python’s default mechanism for finding certificates, set this option to `False`.


### `metrics_interval` [config-metrics_interval]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_METRICS_INTERVAL` | `METRICS_INTERVAL` | `30s` |

The interval in which the agent collects metrics. A shorter interval increases the granularity of metrics, but also increases the overhead of the agent, as well as storage requirements.

It has to be provided in **[duration format](#config-format-duration)**.


### `disable_metrics` [config-disable_metrics]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_DISABLE_METRICS` | `DISABLE_METRICS` | `None` |

A comma-separated list of dotted metrics names that should not be sent to the APM Server. You can use `*` to match multiple metrics; for example, to disable all CPU-related metrics, as well as the "total system memory" metric, set `disable_metrics` to:

```
"*.cpu.*,system.memory.total"
```
::::{note}
This setting only disables the **sending** of the given metrics, not collection.
::::



### `breakdown_metrics` [config-breakdown_metrics]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_BREAKDOWN_METRICS` | `BREAKDOWN_METRICS` | `True` |

Enable or disable the tracking and collection of breakdown metrics. Setting this to `False` disables the tracking of breakdown metrics, which can reduce the overhead of the agent.

::::{note}
This feature requires APM Server and Kibana >= 7.3.
::::



### `prometheus_metrics` (Beta) [config-prometheus_metrics]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_PROMETHEUS_METRICS` | `PROMETHEUS_METRICS` | `False` |

Enable/disable the tracking and collection of metrics from `prometheus_client`.

See [Prometheus metric set (beta)](/reference/metrics.md#prometheus-metricset) for more information.

::::{note}
This feature is currently in beta status.
::::



### `prometheus_metrics_prefix` (Beta) [config-prometheus_metrics_prefix]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_PROMETHEUS_METRICS_PREFIX` | `PROMETHEUS_METRICS_PREFIX` | `prometheus.metrics.` |

A prefix to prepend to Prometheus metrics names.

See [Prometheus metric set (beta)](/reference/metrics.md#prometheus-metricset) for more information.

::::{note}
This feature is currently in beta status.
::::



### `metrics_sets` [config-metrics_sets]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_METRICS_SETS` | `METRICS_SETS` | ["elasticapm.metrics.sets.cpu.CPUMetricSet"] |

List of import paths for the MetricSets that should be used to collect metrics.

See [Custom Metrics](/reference/metrics.md#custom-metrics) for more information.


### `central_config` [config-central_config]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_CENTRAL_CONFIG` | `CENTRAL_CONFIG` | `True` |

When enabled, the agent will make periodic requests to the APM Server to fetch updated configuration.

See [Dynamic configuration](#dynamic-configuration) for more information.

::::{note}
This feature requires APM Server and Kibana >= 7.3.
::::



### `global_labels` [config-global_labels]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_GLOBAL_LABELS` | `GLOBAL_LABELS` | `None` |

Labels added to all events, with the format `key=value[,key=value[,...]]`. Any labels set by application via the API will override global labels with the same keys.

::::{note}
This feature requires APM Server >= 7.2.
::::



### `disable_log_record_factory` [config-generic-disable-log-record-factory]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_DISABLE_LOG_RECORD_FACTORY` | `DISABLE_LOG_RECORD_FACTORY` | `False` |

By default in python 3, the agent installs a [LogRecord factory](/reference/logs.md#logging) that automatically adds tracing fields to your log records. Disable this behavior by setting this to `True`.


### `use_elastic_traceparent_header` [config-use-elastic-traceparent-header]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_USE_ELASTIC_TRACEPARENT_HEADER` | `USE_ELASTIC_TRACEPARENT_HEADER` | `True` |

To enable [distributed tracing](docs-content://solutions/observability/apps/traces.md), the agent sets a number of HTTP headers to outgoing requests made with [instrumented HTTP libraries](/reference/supported-technologies.md#automatic-instrumentation-http). These headers (`traceparent` and `tracestate`) are defined in the [W3C Trace Context](https://www.w3.org/TR/trace-context-1/) specification.

Additionally, when this setting is set to `True`, the agent will set `elasticapm-traceparent` for backwards compatibility.


### `trace_continuation_strategy` [config-trace-continuation-strategy]

[![dynamic config](/reference/images/dynamic-config.svg "") ](#dynamic-configuration)

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_TRACE_CONTINUATION_STRATEGY` | `TRACE_CONTINUATION_STRATEGY` | `continue` |

This option allows some control on how the APM agent handles W3C trace-context headers on incoming requests. By default, the `traceparent` and `tracestate` headers are used per W3C spec for distributed tracing. However, in certain cases it can be helpful to **not** use the incoming `traceparent` header. Some example use cases:

* An Elastic-monitored service is receiving requests with `traceparent` headers from **unmonitored** services.
* An Elastic-monitored service is publicly exposed, and does not want tracing data (trace-ids, sampling decisions) to possibly be spoofed by user requests.

Valid values are:

* `'continue'`: The default behavior. An incoming `traceparent` value is used to continue the trace and determine the sampling decision.
* `'restart'`: Always ignores the `traceparent` header of incoming requests. A new trace-id will be generated and the sampling decision will be made based on [`transaction_sample_rate`](#config-transaction-sample-rate). A **span link** will be made to the incoming traceparent.
* `'restart_external'`: If an incoming request includes the `es` vendor flag in `tracestate`, then any *traceparent* will be considered internal and will be handled as described for `'continue'` above. Otherwise, any `'traceparent'` is considered external and will be handled as described for `'restart'` above.

Starting with Elastic Observability 8.2, span links will be visible in trace views.


### `use_elastic_excepthook` [config-use-elastic-excepthook]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_USE_ELASTIC_EXCEPTHOOK` | `USE_ELASTIC_EXCEPTHOOK` | `False` |

If set to `True`, the agent will intercept the default `sys.excepthook`, which allows the agent to collect all uncaught exceptions.


### `include_process_args` [config-include-process-args]

| Environment | Django/Flask | Default |
| --- | --- | --- |
| `ELASTIC_APM_INCLUDE_PROCESS_ARGS` | `INCLUDE_PROCESS_ARGS` | `False` |

Whether each transaction should have the process arguments attached. Disabled by default to save disk space.


## Django-specific configuration [config-django-specific]


### `django_transaction_name_from_route` [config-django-transaction-name-from-route]

| Environment | Django | Default |
| --- | --- | --- |
| `ELASTIC_APM_DJANGO_TRANSACTION_NAME_FROM_ROUTE` | `DJANGO_TRANSACTION_NAME_FROM_ROUTE` | `False` |

By default, we use the function or class name of the view as the transaction name. Starting with Django 2.2, Django makes the route (e.g. `users/<int:user_id>/`) available on the `request.resolver_match` object. If you want to use the route instead of the view name as the transaction name, set this config option to `true`.

::::{note}
in versions previous to Django 2.2, changing this setting will have no effect.
::::



### `django_autoinsert_middleware` [config-django-autoinsert-middleware]

| Environment | Django | Default |
| --- | --- | --- |
| `ELASTIC_APM_DJANGO_AUTOINSERT_MIDDLEWARE` | `DJANGO_AUTOINSERT_MIDDLEWARE` | `True` |

To trace Django requests, the agent uses a middleware, `elasticapm.contrib.django.middleware.TracingMiddleware`. By default, this middleware is inserted automatically as the first item in `settings.MIDDLEWARES`. To disable the automatic insertion of the middleware, change this setting to `False`.


## Generic Environment variables [config-generic-environment]

Some environment variables that are not specific to the APM agent can be used to configure the agent.


### `HTTP_PROXY` and `HTTPS_PROXY` [config-generic-http-proxy]

By using `HTTP_PROXY` and `HTTPS_PROXY`, the agent can be instructed to use a proxy to connect to the APM Server. If both are set, `HTTPS_PROXY` takes precedence.

::::{note}
The environment variables are case-insensitive.
::::



### `NO_PROXY` [config-generic-no-proxy]

To instruct the agent to **not** use a proxy, you can use the `NO_PROXY` environment variable. You can either set it to a comma-separated list of hosts for which no proxy should be used (e.g. `localhost,example.com`) or use `*` to match any host.

This is useful if `HTTP_PROXY` / `HTTPS_PROXY` is set for other reasons than agent / APM Server communication.


### `SSL_CERT_FILE` and `SSL_CERT_DIR` [config-ssl-cert-file]

To tell the agent to use a different SSL certificate, you can use these environment variables. See also [OpenSSL docs](https://www.openssl.org/docs/manmaster/man7/openssl-env.html#SSL_CERT_DIR-SSL_CERT_FILE).

Please note that these variables may apply to other SSL/TLS communication in your service, not just related to the APM agent.

::::{note}
These environment variables only take effect if [`use_certifi`](#config-use-certifi) is set to `False`.
::::



## Configuration formats [config-formats]

Some options require a unit, either duration or size. These need to be provided in a specific format.


### Duration format [config-format-duration]

The *duration* format is used for options like timeouts. The unit is provided as a suffix directly after the number–without any separation by whitespace.

**Example**: `5ms`

**Supported units**

* `us` (microseconds)
* `ms` (milliseconds)
* `s` (seconds)
* `m` (minutes)


### Size format [config-format-size]

The *size* format is used for options like maximum buffer sizes. The unit is provided as suffix directly after the number, without and separation by whitespace.

**Example**: `10kb`

**Supported units**:

* `b` (bytes)
* `kb` (kilobytes)
* `mb` (megabytes)
* `gb` (gigabytes)

::::{note}
We use the power-of-two sizing convention, e.g. `1 kilobyte == 1024 bytes`
::::


