---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/tuning-and-overhead.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
products:
  - id: cloud-serverless
  - id: observability
  - id: apm
---

# Performance tuning [tuning-and-overhead]

Using an APM solution comes with certain trade-offs, and the Python agent for Elastic APM is no different. Instrumenting your code, measuring timings, recording context data, etc., all need resources:

* CPU time
* memory
* bandwidth use
* Elasticsearch storage

We invested and continue to invest a lot of effort to keep the overhead of using Elastic APM as low as possible. But because every deployment is different, there are some knobs you can turn to adapt it to your specific needs.


## Transaction Sample Rate [tuning-sample-rate]

The easiest way to reduce the overhead of the agent is to tell the agent to do less. If you set the [`transaction_sample_rate`](/reference/configuration.md#config-transaction-sample-rate) to a value below `1.0`, the agent will randomly sample only a subset of transactions. Unsampled transactions only record the name of the transaction, the overall transaction time, and the result:

| Field | Sampled | Unsampled |
| --- | --- | --- |
| Transaction name | yes | yes |
| Duration | yes | yes |
| Result | yes | yes |
| Context | yes | no |
| Tags | yes | no |
| Spans | yes | no |

Reducing the sample rate to a fraction of all transactions can make a huge difference in all four of the mentioned resource types.


## Transaction Queue [tuning-queue]

To reduce the load on the APM Server, the agent does not send every transaction up as it happens. Instead, it queues them up and flushes the queue periodically, or when it reaches a maximum size, using a background thread.

While this reduces the load on the APM Server (and to a certain extent on the agent), holding on to the transaction data in a queue uses memory. If you notice that using the Python agent results in a large increase of memory use, you can use these settings:

* [`api_request_time`](/reference/configuration.md#config-api-request-time) to reduce the time between queue flushes
* [`api_request_size`](/reference/configuration.md#config-api-request-size) to reduce the maximum size of the queue

The first setting, `api_request_time`, is helpful if you have a sustained high number of transactions. The second setting, `api_request_size`, can help if you experience peaks of transactions (a large number of transactions in a short period of time).

Keep in mind that reducing the value of either setting will cause the agent to send more HTTP requests to the APM Server, potentially causing a higher load.


## Spans per transaction [tuning-max-spans]

The average amount of spans per transaction can influence how much time the agent spends in each transaction collecting contextual data for each span, and the storage space needed in Elasticsearch. In our experience, most *usual* transactions should have well below 100 spans. In some cases, however, the number of spans can explode:

* long-running transactions
* unoptimized code, e.g. doing hundreds of SQL queries in a loop

To avoid these edge cases overloading both the agent and the APM Server, the agent stops recording spans when a specified limit is reached. You can configure this limit by changing the [`transaction_max_spans`](/reference/configuration.md#config-transaction-max-spans) setting.


## Span Stack Trace Collection [tuning-span-stack-trace-collection]

Collecting stack traces for spans can be fairly costly from a performance standpoint. Stack traces are very useful for pinpointing which part of your code is generating a span; however, these stack traces are less useful for very short spans (as problematic spans tend to be longer).

You can define a minimal threshold for span duration using the [`span_stack_trace_min_duration`](/reference/configuration.md#config-span-stack-trace-min-duration) setting. If a span’s duration is less than this config value, no stack frames will be collected for this span.


## Collecting Frame Context [tuning-frame-context]

When a stack trace is captured, the agent will also capture several lines of source code around each frame location in the stack trace. This allows the APM app to give greater insight into where exactly the error or span happens.

There are four settings you can modify to control this behavior:

* [`source_lines_error_app_frames`](/reference/configuration.md#config-source-lines-error-app-frames)
* [`source_lines_error_library_frames`](/reference/configuration.md#config-source-lines-error-library-frames)
* [`source_lines_span_app_frames`](/reference/configuration.md#config-source-lines-span-app-frames)
* [`source_lines_span_library_frames`](/reference/configuration.md#config-source-lines-span-library-frames)

As you can see, these settings are divided between app frames, which represent your application code, and library frames, which represent the code of your dependencies. Each of these categories are also split into separate error and span settings.

Reading source files inside a running application can cause a lot of disk I/O, and sending up source lines for each frame will have a network and storage cost that is quite high. Turning down these limits will help prevent excessive memory usage.


## Collecting headers and request body [tuning-body-headers]

You can configure the Elastic APM agent to capture headers of both requests and responses ([`capture_headers`](/reference/configuration.md#config-capture-headers)), as well as request bodies ([`capture_body`](/reference/configuration.md#config-capture-body)). By default, capturing request bodies is disabled. Enabling it for transactions may introduce noticeable overhead, as well as increased storage use, depending on the nature of your POST requests. In most scenarios, we advise against enabling request body capturing for transactions, and only enable it if necessary for errors.

Capturing request/response headers has less overhead on the agent, but can have an impact on storage use. If storage use is a problem for you, it might be worth disabling.

