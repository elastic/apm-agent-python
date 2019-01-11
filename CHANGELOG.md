# Changelog

## Unreleased
[Check the diff](https://github.com/elastic/apm-agent-python/compare/v4.0.3...master)

 * Added support for collecting system and process metrics (#361)
 * Added `transaction.sampled` to errors (#371)
 * Added parsing of `/proc/self/cgroup` to capture container meta data (#352)
 * Added option to configure logging for Flask using a log level (#344)

## v4.0.3
[Check the diff](https://github.com/elastic/apm-agent-python/compare/v4.0.2...v4.0.3)

 * implemented de-dotting of tag names and context keys (#353)
 * wrote a quickfix for the boto3/botocore instrumentation (#367)
 * fixed an issue with psycopg2 and encoded strings (#366)

## v4.0.2
[Check the diff](https://github.com/elastic/apm-agent-python/compare/v4.0.1...v4.0.2)

 * fixed another issue in the new v2 transport (#351)

## v4.0.1
[Check the diff](https://github.com/elastic/apm-agent-python/compare/v4.0.0...v4.0.1)

 * fixed an issue with instrumenting redis-py 3.0+
 * fixed a multithreading issue that occurs when using threaded workers (#335)
 
## v4.0.0
[Check the diff](https://github.com/elastic/apm-agent-python/compare/v3.0.2...v4.0.0)

**BREAKING** Version 4 of the agent implements a new wire protocol for communicating with
the APM Server. This format is only supported in *APM Server 6.5+*.

Further breaking changes:

 * the undocumented `AsyncioHTTPTransport` has been removed.
 * the `flush_interval` and `max_queue_size` settings have been removed.
 * new settings introduced: `api_request_time` and `api_request_size`.
 * Some settings now require a unit for duration or size. See documentation on
   configuration for more information.
 * The option to provide a custom date for exceptions and messages has been removed.

Other changes:
 * on Python 3.7, use [contextvars](https://docs.python.org/3/library/contextvars.html) instead of threadlocals for storing
   current transaction and span. This is a necessary precursor for full asyncio support. (#291)

## v3.0.2
[Check the diff](https://github.com/elastic/apm-agent-python/compare/v3.0.1...v3.0.2)

 * fixed an issue with detecting names of wrapped functions that are partials (#294)
 * fixed a bug in Flask instrumentation that could appear together with FlaskAPI (#286)
 
## v3.0.1

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v3.0.0...v3.0.1)

 * added sanitization for `Set-Cookie` response headers (#264)
 * added instrumentation for the non-standard `Connection.execute()` method for SQLite3 (#271)
 * added "authorization" to list of sensitive keywords, to ensure that "Authorization" 
   HTTP headers are properly sanitized (#275)
 * taught the Logbook handler how to handle the `stack=False` option (#278)
 * fixed a race condition with managing the timer-send thread (#279)

## v3.0.0

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v2.2.1...v3.0.0)

 - adapted "black" code formatter for this repository (#262)
 - **BREAKING**: dropped support for Python 3.3 (#242) 
 - **BREAKING**: changed order of precedence when evaluating configuration (#255, #261)
 - **BREAKING**: changed default value of `span_frames_min_duration` setting 
   from `-1` (always collect) to `5` (only collect for spans longer than 5 ms) (#243)
 - added instrumentation for pymssql (#241)
 - added instrumentation for pyodbc (#238) 

## v2.2.1

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v2.2.0...v2.2.1)

  - fixed an issue with Django Channels (#232, #233)

## v2.2.0

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v2.1.1...v2.2.0)

  - introduced consistent logger name scheme for all elasticapm internal log messages (#212)
  - added instrumentation of cassandra-driver (#205)
  - added instrumentation of elasticsearch-py (#191)
  - added Flask 1.0 to the test matrix (#207)
  - fixed an issue with our minimalistic SQL parser and "fully qualified" table names (#206)
  - fixed issue with spans in Django’s `StreamingHTTPResponse` not being captured (#201, #202)
  - fixed issue with spans with Flask’s streaming response not being captured (#201, #202)

**NOTE**: This will be the last release with support for Python 3.3.

## v2.1.1

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v2.1.0...v2.1.1)

  - fixed bug in Django management command that would be triggered on Django 1.10 or 1.11 while using the `MIDDLEWARE_CLASSES` setting (#186, #187)
  - fix an encoding issue with log messages that are hit in rare cases (#188, #189)

## v2.1.0

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v2.0.1...v2.1.0)

  - made skipping of initial `elasticapm` frames for span stack traces more generic (#167)
  - added `context.process.ppid` field (supported in apm-server 6.3+) (#168)
  - added option to disable stack frame collection for very short spans (#142)
  - several bug fixes:
      - fix an issue in boto3 instrumentation with nonstandard endpoint URLs (#178)
      - fix bug with OPTIONS requests and body capturing (#174)
      - fix issue when message has `%` character, but no params (#175)

## v2.0.1

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v2.0.0...v2.0.1)

  - fixed compatibility issue with aiohttp 3.0 (#157)
  - Added truncation for fields that have a `maxLength` in the JSON Schema (#159)

## v2.0.0

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v1.0.0...v2.0.0)

  - moved the library-frame detection from a processor to the stacktrace collection (#113).
  - added settings to enable/disable source code collection and local variables collection for errors and transactions (#117)
  - added `service.environment` to provide an environment name (e.g. "production", "staging") (#123)
  - added `transaction.id` to errors to better correlate errors with transactions (#122)
  - added `transaction_sample_rate` to define a rate with which transactions are sampled (#116)
  - added `error.handled` to indicate if an exception was handled or not (#124).
  - added `transaction_max_spans` setting to limit the amount of spans that are recorded per transaction (#127)
  - added configuration options to limit captured local variables to a certain length (#130)
  - added options for configuring the amount of context lines that are captured with each frame (#136)
  - added support for tracing queries formatted as [`psycopg2.sql.SQL`](http://initd.org/psycopg/docs/sql.html) objects (#148)
  - switched to `time.perf_counter` as timing function on Python 3 (#138)
  - added option to disable capturing of request body (#151)
  - BREAKING: Several settings and APIs have been renamed (#111, #119, #143):
      - The decorator for custom instrumentation, `elasticapm.trace`, is now `elasticapm.capture_span`
      - The setting `traces_send_frequency` has been renamed to `flush_interval`. The name of the analogous environment variable changed from `ELASTIC_APM_TRACES_SEND_FREQ` to `ELASTIC_APM_FLUSH_INTERVAL`
      - The `app_name` setting has been renamed to `service_name`. The name of the analogous environment variable changed from `ELASTIC_APM_APP_NAME` to `ELASTIC_APM_SERVICE_NAME`.
      - `app_name` arguments to API calls in the whole code base changed to `service_name`.
      - The `app_version` setting has been renamed to `service_version`. The name of the analogous environment variable changed from `ELASTIC_APM_APP_VERSION` to `ELASTIC_APM_SERVICE_VERSION`.
      - `context.request.url.raw` has been renamed to `context.request.url.full` (#121)
  - BREAKING: added `elasticapm.set_custom_context` in favor of the more generic `set_custom_data` function (#133)
  - BREAKING: `include_patterns` and `exclude_patterns` now use shell globs instead of regular expressions, and are matched against the full path file path of the module, not against the module name (#137)
  - BREAKING: renamed several configuration options to align better with other language agents (#145):
      - `disable_instrumentation` became `instrument` and inverted its meaning
      - `max_event_queue_length` became `max_queue_size`
      - `timeout` became `server_timeout`

## v1.0.0

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v1.0.0.dev3...v1.0.0)

  - added `max-event-queue-length` setting. (#67)
  - changed name that the agent reports itself with to the APM server from `elasticapm-python` to `python`. This aligns the Python agent with other languages. (#104)
  - changed Celery integration to store the task state (e.g. `SUCCESS` or `FAILURE`) in `transaction.result` (#100)
  - added setting to disable SSL certificate verification (#108)
  - BREAKING: renamed `server` configuration variable to `server_url` to better align with other language agents (#105)
  - BREAKING: removed the old and unused urllib2-based HTTP transport, and renamed the urllib3 transport (#107)
  - BREAKING: several API changes to `capture_exception`, `capture_message`, and added documentation for these and other APIs (#112)

## v1.0.0.dev3

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v1.0.0.dev2...v1.0.0.dev2)

  - added a background thread to process the transactions queue every 60 seconds (configurable) (#68)
  - adapted trace context for SQL traces to new API (#77)
  - ensured that transaction data is also passed through processors (#84)
  - added `uninstrument` function to reverse instrumentation, and exposed both `instrument` and `uninstrument` as public API in the `elasticapm` namespace (#90)
  - added normalization of HTTP status codes into classes for the `transaction.result` field. A HTTP status of `200` will be turned into `HTTP 2xx`. The unchanged status code is still available in `context.response.status_code`. (#85)

## v1.0.0.dev2

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v1.0.0.dev1...v1.0.0.dev2)

  - added request context information for Flask (#58)
  - added response context information for Flask (#65)
  - BREAKING: changed the `SERVERS` list setting to a single `SERVER` string setting. With this change, we now only support sending events to a single server (#59)
  - BREAKING: removed root trace. Due to historical reason, we used to create a "root trace" which was equivalent to the transaction. This is no longer necessary. #61

## v1.0.0.dev1

[Check the diff](https://github.com/elastic/apm-agent-python/compare/v1.0.0.dev0...v1.0.0.dev1)

  - unified configuration across supported frameworks (#33)
  - added in-app frame detection (#36)
  - added tagging functionality (#28)
  - preliminary support for Django 2.0 (#26)
  - initial set of documentation

## v1.0.0.dev0

First release of the Python agent for Elastic APM
