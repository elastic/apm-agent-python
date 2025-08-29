---
navigation_title: "Elastic APM Python Agent"
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/release-notes-6.x.html
  - https://www.elastic.co/guide/en/apm/agent/python/current/release-notes.html
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

# Elastic APM Python Agent release notes [elastic-apm-python-agent-release-notes]

Review the changes, fixes, and more in each version of Elastic APM Python Agent.

To check for security updates, go to [Security announcements for the Elastic stack](https://discuss.elastic.co/c/announcements/security-announcements/31).

% Release notes includes only features, enhancements, and fixes. Add breaking changes, deprecations, and known issues to the applicable release notes sections.

% ## version.next [elastic-apm-python-agent-versionext-release-notes]
% **Release date:** Month day, year

% ### Features and enhancements [elastic-apm-python-agent-versionext-features-enhancements]

% ### Fixes [elastic-apm-python-agent-versionext-fixes]

## 6.24.0 [elastic-apm-python-agent-6240-release-notes]
**Release date:** August 12, 2025

### Features and enhancements [elastic-apm-python-agent-6240-features-enhancements]
* Add support for recent sanic versions [#2190](https://github.com/elastic/apm-agent-python/pull/2190), [#2194](https://github.com/elastic/apm-agent-python/pull/2194)
* Make server certificate verification mandatory in fips mode [#2227](https://github.com/elastic/apm-agent-python/pull/2227)
* Add support Python 3.13 [#2216](https://github.com/elastic/apm-agent-python/pull/2216)
* Add support for azure-data-tables package for azure instrumentation [#2187](https://github.com/elastic/apm-agent-python/pull/2187)
* Add span links from SNS messages [#2363](https://github.com/elastic/apm-agent-python/pull/2363)

### Fixes [elastic-apm-python-agent-6240-fixes]
* Fix psycopg2 cursor execute and executemany signatures [#2331](https://github.com/elastic/apm-agent-python/pull/2331)
* Fix psycopg cursor execute and executemany signatures [#2332](https://github.com/elastic/apm-agent-python/pull/2332)
* Fix asgi middleware distributed tracing [#2334](https://github.com/elastic/apm-agent-python/pull/2334)
* Fix typing of start in Span / capture_span to float [#2335](https://github.com/elastic/apm-agent-python/pull/2335)
* Fix azure instrumentation client_class and metrics sets invocation [#2337](https://github.com/elastic/apm-agent-python/pull/2337)
* Fix mysql_connector instrumentation connection retrieval [#2344](https://github.com/elastic/apm-agent-python/pull/2344)
* Remove spurious Django QuerySet evaluation in case of database errors [#2158](https://github.com/elastic/apm-agent-python/pull/2158)

## 6.23.0 [elastic-apm-python-agent-6230-release-notes]
**Release date:** July 30, 2024

### Features and enhancements [elastic-apm-python-agent-6230-features-enhancements]
* Make published Docker images multi-platform with the addition of linux/arm64 [#2080](https://github.com/elastic/apm-agent-python/pull/2080)

### Fixes [elastic-apm-python-agent-6230-fixes]
* Fix handling consumer iteration if transaction not sampled in kafka instrumentation [#2075](https://github.com/elastic/apm-agent-python/pull/2075)
* Fix race condition with urllib3 at shutdown [#2085](https://github.com/elastic/apm-agent-python/pull/2085)
* Fix compatibility with setuptools>=72 that removed test command [#2090](https://github.com/elastic/apm-agent-python/pull/2090)

## 6.22.3 [elastic-apm-python-agent-6223-release-notes]
**Release date:** June 10, 2024

### Fixes [elastic-apm-python-agent-6223-fixes]
* Fix outcome in ASGI and Starlette apps on error status codes without an exception [#2060](https://github.com/elastic/apm-agent-python/pull/2060)

## 6.22.2 [elastic-apm-python-agent-6222-release-notes]
**Release date:** May 20, 2024

### Fixes [elastic-apm-python-agent-6222-fixes]
* Fix CI release workflow [#2046](https://github.com/elastic/apm-agent-python/pull/2046)

## 6.22.1 [elastic-apm-python-agent-6222-release-notes]
**Release date:** May 17, 2024

### Features and enhancements [elastic-apm-python-agent-6221-features-enhancements]
* Relax wrapt dependency to only exclude 1.15.0 [#2005](https://github.com/elastic/apm-agent-python/pull/2005)

## 6.22.0 [elastic-apm-python-agent-6220-release-notes]
**Release date:** April 3, 2024

### Features and enhancements [elastic-apm-python-agent-6220-features-enhancements]
* Add ability to override default JSON serialization [#2018](https://github.com/elastic/apm-agent-python/pull/2018)

## 6.21.4 [elastic-apm-python-agent-6214-release-notes]
**Release date:** March 19, 2024

### Fixes [elastic-apm-python-agent-6214-fixes]
* Fix urllib3 2.0.1+ crash with many args [#2002](https://github.com/elastic/apm-agent-python/pull/2002)

## 6.21.3 [elastic-apm-python-agent-6213-release-notes]
**Release date:** March 8, 2024

### Fixes [elastic-apm-python-agent-6213-fixes]
* Fix artifacts download in CI workflows [#1996](https://github.com/elastic/apm-agent-python/pull/1996)

## 6.21.2 [elastic-apm-python-agent-6212-release-notes]
**Release date:** March 7, 2024

### Fixes [elastic-apm-python-agent-6212-fixes]
* Fix artifacts upload in CI build-distribution workflow [#1993](https://github.com/elastic/apm-agent-python/pull/1993)

## 6.21.1 [elastic-apm-python-agent-6211-release-notes]
**Release date:** March 7, 2024

### Fixes [elastic-apm-python-agent-6211-fixes]
* Fix CI release workflow [#1990](https://github.com/elastic/apm-agent-python/pull/1990)

## 6.21.0 [elastic-apm-python-agent-6210-release-notes]
**Release date:** March 6, 2024

### Fixes [elastic-apm-python-agent-6210-fixes]
* Fix starlette middleware setup without client argument [#1952](https://github.com/elastic/apm-agent-python/pull/1952)
* Fix blocking of gRPC stream-to-stream requests [#1967](https://github.com/elastic/apm-agent-python/pull/1967)
* Always take into account body reading time for starlette requests [#1970](https://github.com/elastic/apm-agent-python/pull/1970)
* Make urllib3 transport tests more robust against local env [#1969](https://github.com/elastic/apm-agent-python/pull/1969)
* Clarify starlette integration documentation [#1956](https://github.com/elastic/apm-agent-python/pull/1956)
* Make dbapi2 query scanning for dollar quotes a bit more correct [#1976](https://github.com/elastic/apm-agent-python/pull/1976)
* Normalize headers in AWS Lambda integration on API Gateway v1 requests [#1982](https://github.com/elastic/apm-agent-python/pull/1982)

## 6.20.0 [elastic-apm-python-agent-6200-release-notes]
**Release date:** January 10, 2024

### Features and enhancements [elastic-apm-python-agent-6200-features-enhancements]
* Async support for dbapi2 (starting with psycopg) [#1944](https://github.com/elastic/apm-agent-python/pull/1944)
* Add object name to procedure call spans in dbapi2 [#1938](https://github.com/elastic/apm-agent-python/pull/1938)
* Add support for python 3.10 and 3.11 lambda runtimes

### Fixes [elastic-apm-python-agent-6200-fixes]
* Fix asyncpg support for 0.29+ [#1935](https://github.com/elastic/apm-agent-python/pull/1935)
* Fix dbapi2 signature extraction to handle square brackets in table name [#1947](https://github.com/elastic/apm-agent-python/pull/1947)

## 6.19.0 [elastic-apm-python-agent-6190-release-notes]
**Release date:** October 11, 2023

### Features and enhancements [elastic-apm-python-agent-6190-features-enhancements]
* Add Python 3.12 support
* Collect the `configured_hostname` and `detected_hostname` separately, and switch to FQDN for the `detected_hostname`. [#1891](https://github.com/elastic/apm-agent-python/pull/1891)
* Improve postgres dollar-quote detection to be much faster [#1905](https://github.com/elastic/apm-agent-python/pull/1905)

### Fixes [elastic-apm-python-agent-6190-fixes]
* Fix url argument fetching in aiohttp_client instrumentation [#1890](https://github.com/elastic/apm-agent-python/pull/1890)
* Fix a bug in the AWS Lambda instrumentation when `event["headers"] is None` [#1907](https://github.com/elastic/apm-agent-python/pull/1907)
* Fix a bug in AWS Lambda where metadata could be incomplete, causing validation errors with the APM Server [#1914](https://github.com/elastic/apm-agent-python/pull/1914)
* Fix a bug in AWS Lambda where sending the partial transaction would be recorded as an extra span [#1914](https://github.com/elastic/apm-agent-python/pull/1914)

## 6.18.0 [elastic-apm-python-agent-6180-release-notes]
**Release date:** July 25, 2023

### Features and enhancements [elastic-apm-python-agent-6180-features-enhancements]
* Add support for grpc aio server interceptor [#1870](https://github.com/elastic/apm-agent-python/pull/1870)

### Fixes [elastic-apm-python-agent-6180-fixes]
* Fix a bug in the Elasticsearch client instrumentation which was causing loss of database context (including statement) when interacting with Elastic Cloud [#1878](https://github.com/elastic/apm-agent-python/pull/1878)

## 6.17.0 [elastic-apm-python-agent-6170-release-notes]
**Release date:** July 3, 2023

### Features and enhancements [elastic-apm-python-agent-6170-features-enhancements]
* Add `server_ca_cert_file` option to provide custom CA certificate [#1852](https://github.com/elastic/apm-agent-python/pull/1852)
* Add `include_process_args` option to allow users to opt-in to collecting process args [#1867](https://github.com/elastic/apm-agent-python/pull/1867)

### Fixes [elastic-apm-python-agent-6170-fixes]
* Fix a bug in the GRPC instrumentation when reaching the maximum amount of spans per transaction [#1861](https://github.com/elastic/apm-agent-python/pull/1861)

## 6.16.2 [elastic-apm-python-agent-6162-release-notes]
**Release date:** June 12, 2023

### Fixes [elastic-apm-python-agent-6162-fixes]
* Fix compatibility issue with older versions of OpenSSL in lambda runtimes [#1847](https://github.com/elastic/apm-agent-python/pull/1847)
* Add `latest` tag to docker images [#1848](https://github.com/elastic/apm-agent-python/pull/1848)
* Fix issue with redacting `user:pass` in URLs in Python 3.11.4 [#1850](https://github.com/elastic/apm-agent-python/pull/1850)

## 6.16.1 [elastic-apm-python-agent-6161-release-notes]
**Release date:** June 6, 2023

### Fixes [elastic-apm-python-agent-6161-fixes]
* Fix release process for docker and the lambda layer [#1845](https://github.com/elastic/apm-agent-python/pull/1845)

## 6.16.0 [elastic-apm-python-agent-6160-release-notes]
**Release date:** June 5, 2023

### Features and enhancements [elastic-apm-python-agent-6160-features-enhancements]
* Add lambda layer for instrumenting AWS Lambda functions [#1826](https://github.com/elastic/apm-agent-python/pull/1826)
* Implement instrumentation of Azure Functions [#1766](https://github.com/elastic/apm-agent-python/pull/1766)
* Add support for Django to wrapper script [#1780](https://github.com/elastic/apm-agent-python/pull/1780)
* Add support for Starlette to wrapper script [#1830](https://github.com/elastic/apm-agent-python/pull/1830)
* Add `transport_json_serializer` configuration option [#1777](https://github.com/elastic/apm-agent-python/pull/1777)
* Add S3 bucket and key name to OTel attributes [#1790](https://github.com/elastic/apm-agent-python/pull/1790)
* Implement partial transaction support in AWS lambda [#1784](https://github.com/elastic/apm-agent-python/pull/1784)
* Add instrumentation for redis.asyncio [#1807](https://github.com/elastic/apm-agent-python/pull/1807)
* Add support for urllib3 v2.0.1+ [#1822](https://github.com/elastic/apm-agent-python/pull/1822)
* Add `service.environment` to log correlation [#1833](https://github.com/elastic/apm-agent-python/pull/1833)
* Add `ecs_logging` as a dependency [#1840](https://github.com/elastic/apm-agent-python/pull/1840)
* Add support for synchronous psycopg3 [#1841](https://github.com/elastic/apm-agent-python/pull/1841)

### Fixes [elastic-apm-python-agent-6160-fixes]
* Fix spans being dropped if they don’t have a name [#1770](https://github.com/elastic/apm-agent-python/pull/1770)
* Fix AWS Lambda support when `event` is not a dict [#1775](https://github.com/elastic/apm-agent-python/pull/1775)
* Fix deprecation warning with urllib3 2.0.0 pre-release versions [#1778](https://github.com/elastic/apm-agent-python/pull/1778)
* Fix `activation_method` to only send to APM server 8.7.1+ [#1787](https://github.com/elastic/apm-agent-python/pull/1787)
* Fix span.context.destination.service.resource for S3 spans to have an "s3/" prefix. [#1783](https://github.com/elastic/apm-agent-python/pull/1783)

**Note**: While this is considered a bugfix, it can potentially be a breaking change in the Kibana APM app: It can break the history of the S3-Spans / metrics for users relying on `context.destination.service.resource`. If users happen to run agents both with and without this fix (for same or different languages), the same S3-buckets can appear twice in the service map (with and without s3-prefix).

* Fix instrumentation to not bubble up exceptions during instrumentation [#1791](https://github.com/elastic/apm-agent-python/pull/1791)
* Fix HTTP transport to not print useless and confusing stack trace [#1809](https://github.com/elastic/apm-agent-python/pull/1809)

## 6.15.1 [elastic-apm-python-agent-6151-release-notes]
**Release date:** March 6, 2023

### Fixes [elastic-apm-python-agent-6151-fixes]
* Fix issue with botocore instrumentation creating spans with an incorrect `service.name` [#1765](https://github.com/elastic/apm-agent-python/pull/1765)
* Fix a bug in the GRPC instrumentation when the agent is disabled or not recording [#1761](https://github.com/elastic/apm-agent-python/pull/1761)

## 6.15.0 [elastic-apm-python-agent-6150-release-notes]
**Release date:** February 16, 2023

### Features and enhancements [elastic-apm-python-agent-6150-features-enhancements]
* Add `service.agent.activation_method` to the metadata [#1743](https://github.com/elastic/apm-agent-python/pull/1743)

### Fixes [elastic-apm-python-agent-6150-fixes]
* Small fix to underlying Starlette logic to prevent duplicate Client objects [#1735](https://github.com/elastic/apm-agent-python/pull/1735)
* Change `server_url` default to `http://127.0.0.1:8200` to avoid ipv6 ambiguity [#1744](https://github.com/elastic/apm-agent-python/pull/1744)
* Fix an issue in GRPC instrumentation with unsampled transactions [#1740](https://github.com/elastic/apm-agent-python/pull/1740)
* Fix error in async Elasticsearch instrumentation when spans are dropped [#1758](https://github.com/elastic/apm-agent-python/pull/1758)

## 6.14.0 [elastic-apm-python-agent-6140-release-notes]
**Release date:** January 30, 2023

### Features and enhancements [elastic-apm-python-agent-6140-features-enhancements]
* GRPC support [#1703](https://github.com/elastic/apm-agent-python/pull/1703)
* Wrapper script Flask support (experimental) [#1709](https://github.com/elastic/apm-agent-python/pull/1709)

### Fixes [elastic-apm-python-agent-6140-fixes]
* Fix an async issue with long elasticsearch queries [#1725](https://github.com/elastic/apm-agent-python/pull/1725)
* Fix a minor inconsistency with the W3C tracestate spec [#1728](https://github.com/elastic/apm-agent-python/pull/1728)
* Fix a cold start performance issue with our AWS Lambda integration [#1727](https://github.com/elastic/apm-agent-python/pull/1727)
* Mark `**kwargs` config usage in our AWS Lambda integration as deprecated [#1727](https://github.com/elastic/apm-agent-python/pull/1727)

## 6.13.2 [elastic-apm-python-agent-6132-release-notes]
**Release date:** November 17, 2022

### Fixes [elastic-apm-python-agent-6132-fixes]
* Fix error in Elasticsearch instrumentation when spans are dropped [#1690](https://github.com/elastic/apm-agent-python/pull/1690)
* Lower log level for errors in APM Server version fetching [#1692](https://github.com/elastic/apm-agent-python/pull/1692)
* Fix for missing parent.id when logging from a DroppedSpan under a leaf span [#1695](https://github.com/elastic/apm-agent-python/pull/1695)

## 6.13.1 [elastic-apm-python-agent-6131-release-notes]
**Release date:** November 3, 2022

### Fixes [elastic-apm-python-agent-6131-fixes]
* Fix elasticsearch instrumentation for track_total_hits=False [#1687](https://github.com/elastic/apm-agent-python/pull/1687)

## 6.13.0 [elastic-apm-python-agent-6130-release-notes]
**Release date:** October 26, 2022

### Features and enhancements [elastic-apm-python-agent-6130-features-enhancements]
* Add support for Python 3.11
* Add backend granularity data to SQL backends as well as Cassandra and pymongo [#1585](https://github.com/elastic/apm-agent-python/pull/1585), [#1639](https://github.com/elastic/apm-agent-python/pull/1639)
* Add support for instrumenting the Elasticsearch 8 Python client [#1642](https://github.com/elastic/apm-agent-python/pull/1642)
* Add `*principal*` to default `sanitize_field_names` configuration [#1664](https://github.com/elastic/apm-agent-python/pull/1664)
* Add docs and better support for custom metrics, including in AWS Lambda [#1643](https://github.com/elastic/apm-agent-python/pull/1643)
* Add support for capturing span links from AWS SQS in AWS Lambda [#1662](https://github.com/elastic/apm-agent-python/pull/1662)

### Fixes [elastic-apm-python-agent-6130-fixes]
* Fix Django’s `manage.py check` when agent is disabled [#1632](https://github.com/elastic/apm-agent-python/pull/1632)
* Fix an issue with long body truncation for Starlette [#1635](https://github.com/elastic/apm-agent-python/pull/1635)
* Fix an issue with transaction outcomes in Flask for uncaught exceptions [#1637](https://github.com/elastic/apm-agent-python/pull/1637)
* Fix Starlette instrumentation to make sure transaction information is still present during exception handling [#1674](https://github.com/elastic/apm-agent-python/pull/1674)

## 6.12.0 [elastic-apm-python-agent-6120-release-notes]
**Release date:** September 7, 2022

### Features and enhancements [elastic-apm-python-agent-6120-features-enhancements]
* Add redis query to context data for redis instrumentation [#1406](https://github.com/elastic/apm-agent-python/pull/1406)
* Add AWS request ID to all botocore spans (at `span.context.http.request.id`) [#1625](https://github.com/elastic/apm-agent-python/pull/1625)

### Fixes [elastic-apm-python-agent-6120-fixes]
* Differentiate Lambda URLs from API Gateway in AWS Lambda integration [#1609](https://github.com/elastic/apm-agent-python/pull/1609)
* Restrict the size of Django request bodies to prevent APM Server rejection [#1610](https://github.com/elastic/apm-agent-python/pull/1610)
* Restrict length of `exception.message` for exceptions captured by the agent [#1619](https://github.com/elastic/apm-agent-python/pull/1619)
* Restrict length of Starlette request bodies [#1549](https://github.com/elastic/apm-agent-python/pull/1549)
* Fix error when using elasticsearch(sniff_on_start=True) [#1618](https://github.com/elastic/apm-agent-python/pull/1618)
* Improve handling of ignored URLs and capture_body=off for Starlette [#1549](https://github.com/elastic/apm-agent-python/pull/1549)
* Fix possible error in the transport flush for Lambda functions [#1628](https://github.com/elastic/apm-agent-python/pull/1628)

## 6.11.0 [elastic-apm-python-agent-6110-release-notes]
**Release date:** August 9, 2022

### Features and enhancements [elastic-apm-python-agent-6110-features-enhancements]
* Added lambda support for ELB triggers [#1605](https://github.com/elastic/apm-agent-python/pull/1605)

## 6.10.2 [elastic-apm-python-agent-6102-release-notes]
**Release date:** August 9, 2022

### Fixes [elastic-apm-python-agent-6102-fixes]
* Fixed an issue with non-integer ports in Django [#1590](https://github.com/elastic/apm-agent-python/pull/1590)
* Fixed an issue with non-integer ports in Redis [#1591](https://github.com/elastic/apm-agent-python/pull/1591)
* Fixed a performance issue for local variable shortening via `varmap()` [#1593](https://github.com/elastic/apm-agent-python/pull/1593)
* Fixed `elasticapm.label()` when a Client object is not available [#1596](https://github.com/elastic/apm-agent-python/pull/1596)

## 6.10.1 [elastic-apm-python-agent-6101-release-notes]
**Release date:** June 30, 2022

### Fixes [elastic-apm-python-agent-6101-fixes]
* Fix an issue with Kafka instrumentation and unsampled transactions [#1579](https://github.com/elastic/apm-agent-python/pull/1579)

## 6.10.0 [elastic-apm-python-agent-6100-release-notes]
**Release date:** June 22, 2022

### Features and enhancements [elastic-apm-python-agent-6100-features-enhancements]
* Add instrumentation for [`aiobotocore`](https://github.com/aio-libs/aiobotocore) [#1520](https://github.com/elastic/apm-agent-python/pull/1520)
* Add instrumentation for [`kafka-python`](https://kafka-python.readthedocs.io/en/master/) [#1555](https://github.com/elastic/apm-agent-python/pull/1555)
* Add API for span links, and implement span link support for OpenTelemetry bridge [#1562](https://github.com/elastic/apm-agent-python/pull/1562)
* Add span links to SQS ReceiveMessage call [#1575](https://github.com/elastic/apm-agent-python/pull/1575)
* Add specific instrumentation for SQS delete/batch-delete [#1567](https://github.com/elastic/apm-agent-python/pull/1567)
* Add `trace_continuation_strategy` setting [#1564](https://github.com/elastic/apm-agent-python/pull/1564)

### Fixes [elastic-apm-python-agent-6100-fixes]
* Fix return for `opentelemetry.Span.is_recording()` [#1530](https://github.com/elastic/apm-agent-python/pull/1530)
* Fix error logging for bad SERVICE_NAME config [#1546](https://github.com/elastic/apm-agent-python/pull/1546)
* Do not instrument old versions of Tornado > 6.0 due to incompatibility [#1566](https://github.com/elastic/apm-agent-python/pull/1566)
* Fix transaction names for class based views in Django 4.0+ [#1571](https://github.com/elastic/apm-agent-python/pull/1571)
* Fix a problem with our logging handler failing to report internal errors in its emitter [#1568](https://github.com/elastic/apm-agent-python/pull/1568)

## 6.9.1 [elastic-apm-python-agent-691-release-notes]
**Release date:** March 30, 2022

### Fixes [elastic-apm-python-agent-691-fixes]
* Fix `otel_attributes`-related regression with older versions of APM Server (<7.16) [#1510](https://github.com/elastic/apm-agent-python/pull/1510)

## 6.9.0 [elastic-apm-python-agent-690-release-notes]
**Release date:** March 29, 2022

### Features and enhancements [elastic-apm-python-agent-690-features-enhancements]
* Add OpenTelemetry API bridge [#1411](https://github.com/elastic/apm-agent-python/pull/1411)
* Change default for `sanitize_field_names` to sanitize `*auth*` instead of `authorization` [#1494](https://github.com/elastic/apm-agent-python/pull/1494)
* Add `span_stack_trace_min_duration` to replace deprecated `span_frames_min_duration` [#1498](https://github.com/elastic/apm-agent-python/pull/1498)
* Enable exact_match span compression by default [#1504](https://github.com/elastic/apm-agent-python/pull/1504)
* Allow parent celery tasks to specify the downstream `parent_span_id` in celery headers [#1500](https://github.com/elastic/apm-agent-python/pull/1500)

### Fixes [elastic-apm-python-agent-690-fixes]
* Fix Sanic integration to properly respect the `capture_body` config [#1485](https://github.com/elastic/apm-agent-python/pull/1485)
* Lambda fixes to align with the cross-agent spec [#1489](https://github.com/elastic/apm-agent-python/pull/1489)
* Lambda fix for custom `service_name` [#1493](https://github.com/elastic/apm-agent-python/pull/1493)
* Change default for `stack_trace_limit` from 500 to 50 [#1492](https://github.com/elastic/apm-agent-python/pull/1492)
* Switch all duration handling to use `datetime.timedelta` objects [#1488](https://github.com/elastic/apm-agent-python/pull/1488)

## 6.8.1 [elastic-apm-python-agent-681-release-notes]
**Release date:** March 9, 2022

### Fixes [elastic-apm-python-agent-681-fixes]
* Fix `exit_span_min_duration` and disable by default [#1483](https://github.com/elastic/apm-agent-python/pull/1483)

## 6.8.0 [elastic-apm-python-agent-680-release-notes]
**Release date:** February 22, 2022

### Features and enhancements [elastic-apm-python-agent-680-features-enhancements]
* use "unknown-python-service" as default service name if no service name is configured [#1438](https://github.com/elastic/apm-agent-python/pull/1438)
* add transaction name to error objects [#1441](https://github.com/elastic/apm-agent-python/pull/1441)
* don’t send unsampled transactions to APM Server 8.0+ [#1442](https://github.com/elastic/apm-agent-python/pull/1442)
* implement snapshotting of certain configuration during transaction lifetime [#1431](https://github.com/elastic/apm-agent-python/pull/1431)
* propagate traceparent IDs via Celery [#1371](https://github.com/elastic/apm-agent-python/pull/1371)
* removed Python 2 compatibility shims [#1463](https://github.com/elastic/apm-agent-python/pull/1463)

**Note:** Python 2 support was already removed with version 6.0 of the agent, this now removes unused compatibilit shims.

### Fixes [elastic-apm-python-agent-680-fixes]
* fix span compression for redis, mongodb, cassandra and memcached [#1444](https://github.com/elastic/apm-agent-python/pull/1444)
* fix recording of status_code for starlette [#1466](https://github.com/elastic/apm-agent-python/pull/1466)
* fix aioredis span context handling [#1462](https://github.com/elastic/apm-agent-python/pull/1462)

## 6.7.2 [elastic-apm-python-agent-672-release-notes]
**Release date:** December 7, 2021

### Fixes [elastic-apm-python-agent-672-fixes]
* fix AttributeError in sync instrumentation of httpx [#1423](https://github.com/elastic/apm-agent-python/pull/1423)
* add setting to disable span compression, default to disabled [#1429](https://github.com/elastic/apm-agent-python/pull/1429)

## 6.7.1 [elastic-apm-python-agent-671-release-notes]
**Release date:** November 29, 2021

### Fixes [elastic-apm-python-agent-671-fixes]
* fix an issue with Sanic exception tracking [#1414](https://github.com/elastic/apm-agent-python/pull/1414)
* asyncpg: Limit SQL queries in context data to 10000 characters [#1416](https://github.com/elastic/apm-agent-python/pull/1416)

## 6.7.0 [elastic-apm-python-agent-670-release-notes]
**Release date:** November 17, 2021

### Features and enhancements [elastic-apm-python-agent-670-features-enhancements]
* Add support for Sanic framework [#1390](https://github.com/elastic/apm-agent-python/pull/1390)

### Fixes [elastic-apm-python-agent-670-fixes]
* fix compatibility issues with httpx 0.21 [#1403](https://github.com/elastic/apm-agent-python/pull/1403)
* fix `span_compression_exact_match_max_duration` default value [#1407](https://github.com/elastic/apm-agent-python/pull/1407)

## 6.6.3 [elastic-apm-python-agent-663-release-notes]
**Release date:** November 15, 2021

### Fixes [elastic-apm-python-agent-663-fixes]
* fix an issue with `metrics_sets` configuration referencing the `TransactionMetricSet` removed in 6.6.2 [#1397](https://github.com/elastic/apm-agent-python/pull/1397)

## 6.6.2 [elastic-apm-python-agent-662-release-notes]
**Release date:** November 10, 2021

### Fixes [elastic-apm-python-agent-662-fixes]
* Fix an issue where compressed spans would count against `transaction_max_spans` [#1377](https://github.com/elastic/apm-agent-python/pull/1377)
* Make sure HTTP connections are not re-used after a process fork [#1374](https://github.com/elastic/apm-agent-python/pull/1374)
* Fix an issue with psycopg2 instrumentation when multiple hosts are defined [#1386](https://github.com/elastic/apm-agent-python/pull/1386)
* Update the `User-Agent` header to the new [spec](https://github.com/elastic/apm/pull/514) [#1378](https://github.com/elastic/apm-agent-python/pull/1378)
* Improve status_code handling in AWS Lambda integration [#1382](https://github.com/elastic/apm-agent-python/pull/1382)
* Fix `aiohttp` exception handling to allow for non-500 responses including `HTTPOk` [#1384](https://github.com/elastic/apm-agent-python/pull/1384)
* Force transaction names to strings [#1389](https://github.com/elastic/apm-agent-python/pull/1389)
* Remove unused `http.request.socket.encrypted` context field [#1332](https://github.com/elastic/apm-agent-python/pull/1332)
* Remove unused transaction metrics (APM Server handles these metrics instead) [#1388](https://github.com/elastic/apm-agent-python/pull/1388)

## 6.6.1 [elastic-apm-python-agent-661-release-notes]
**Release date:** November 2, 2021

### Fixes [elastic-apm-python-agent-661-fixes]
* Fix some context fields and metadata handling in AWS Lambda support [#1368](https://github.com/elastic/apm-agent-python/pull/1368)

## 6.6.0 [elastic-apm-python-agent-660-release-notes]
**Release date:** October 18, 2021

### Features and enhancements [elastic-apm-python-agent-660-features-enhancements]
* Add experimental support for AWS lambda instrumentation [#1193](https://github.com/elastic/apm-agent-python/pull/1193)
* Add support for span compression [#1321](https://github.com/elastic/apm-agent-python/pull/1321)
* Auto-infer destination resources for easier instrumentation of new resources [#1359](https://github.com/elastic/apm-agent-python/pull/1359)
* Add support for dropped span statistics [#1327](https://github.com/elastic/apm-agent-python/pull/1327)

### Fixes [elastic-apm-python-agent-660-fixes]
* Ensure that Prometheus histograms are encoded correctly for APM Server [#1354](https://github.com/elastic/apm-agent-python/pull/1354)
* Remove problematic (and duplicate) `event.dataset` from logging integrations [#1365](https://github.com/elastic/apm-agent-python/pull/1365)
* Fix for memcache instrumentation when configured with a unix socket [#1357](https://github.com/elastic/apm-agent-python/pull/1357)

## 6.5.0 [elastic-apm-python-agent-650-release-notes]
**Release date:** October 4, 2021

### Features and enhancements [elastic-apm-python-agent-650-features-enhancements]
* Add instrumentation for Azure Storage (blob/table/fileshare) and Azure Queue [#1316](https://github.com/elastic/apm-agent-python/pull/1316)

### Fixes [elastic-apm-python-agent-650-fixes]
* Improve span coverage for `asyncpg` [#1328](https://github.com/elastic/apm-agent-python/pull/1328)
* aiohttp: Correctly pass custom client to tracing middleware [#1345](https://github.com/elastic/apm-agent-python/pull/1345)
* Fixed an issue with httpx instrumentation [#1337](https://github.com/elastic/apm-agent-python/pull/1337)
* Fixed an issue with Django 4.0 removing a private method [#1347](https://github.com/elastic/apm-agent-python/pull/1347)

## 6.4.0 [elastic-apm-python-agent-640-release-notes]
**Release date:** August 31, 2021

### Features and enhancements [elastic-apm-python-agent-640-features-enhancements]
* Rename the experimental `log_ecs_formatting` config to `log_ecs_reformatting` [#1300](https://github.com/elastic/apm-agent-python/pull/1300)
* Add support for Prometheus histograms [#1165](https://github.com/elastic/apm-agent-python/pull/1165)

### Fixes [elastic-apm-python-agent-640-fixes]
* Fixed cookie sanitization when Cookie is capitalized [#1301](https://github.com/elastic/apm-agent-python/pull/1301)
* Fix a bug with exception capturing for bad UUIDs [#1304](https://github.com/elastic/apm-agent-python/pull/1304)
* Fix potential errors in json serialization [#1203](https://github.com/elastic/apm-agent-python/pull/1203)
* Fix an issue with certain aioredis commands [#1308](https://github.com/elastic/apm-agent-python/pull/1308)

## 6.3.3 [elastic-apm-python-agent-633-release-notes]
**Release date:** July 14, 2021

### Fixes [elastic-apm-python-agent-633-fixes]
* ensure that the elasticsearch instrumentation handles DroppedSpans correctly [#1190](https://github.com/elastic/apm-agent-python/pull/1190)

## 6.3.2 [elastic-apm-python-agent-632-release-notes]
**Release date:** July 7, 2021

### Fixes [elastic-apm-python-agent-632-fixes]
* Fix handling of non-http scopes in Starlette/FastAPI middleware [#1187](https://github.com/elastic/apm-agent-python/pull/1187)

## 6.3.1 [elastic-apm-python-agent-631-release-notes]
**Release date:** July 7, 2021

### Fixes [elastic-apm-python-agent-631-fixes]
* Fix issue with Starlette/FastAPI hanging on startup [#1185](https://github.com/elastic/apm-agent-python/pull/1185)

## 6.3.0 [elastic-apm-python-agent-630-release-notes]
**Release date:** July 6, 2021

### Features and enhancements [elastic-apm-python-agent-630-features-enhancements]
* Add additional context information about elasticsearch client requests [#1108](https://github.com/elastic/apm-agent-python/pull/1108)
* Add `use_certifi` config option to allow users to disable `certifi` [#1163](https://github.com/elastic/apm-agent-python/pull/1163)

### Fixes [elastic-apm-python-agent-630-fixes]
* Fix for Starlette 0.15.0 error collection [#1174](https://github.com/elastic/apm-agent-python/pull/1174)
* Fix for Starlette static files [#1137](https://github.com/elastic/apm-agent-python/pull/1137)

## 6.2.3 [elastic-apm-python-agent-623-release-notes]
**Release date:** June 28, 2021

### Fixes [elastic-apm-python-agent-623-fixes]
* suppress the default_app_config attribute in Django 3.2+ [#1155](https://github.com/elastic/apm-agent-python/pull/1155)
* bump log level for multiple set_client calls to WARNING [#1164](https://github.com/elastic/apm-agent-python/pull/1164)
* fix issue with adding disttracing to SQS messages when dropping spans [#1170](https://github.com/elastic/apm-agent-python/pull/1170)

## 6.2.2 [elastic-apm-python-agent-622-release-notes]
**Release date:** June 7, 2021

### Fixes [elastic-apm-python-agent-622-fixes]
* Fix an attribute access bug introduced in 6.2.0 [#1149](https://github.com/elastic/apm-agent-python/pull/1149)

## 6.2.1 [elastic-apm-python-agent-621-release-notes]
**Release date:** June 3, 2021

### Fixes [elastic-apm-python-agent-621-fixes]
* catch and log exceptions in interval timer threads [#1145](https://github.com/elastic/apm-agent-python/pull/1145)

## 6.2.0 [elastic-apm-python-agent-620-release-notes]
**Release date:** May 31, 2021

### Features and enhancements [elastic-apm-python-agent-620-features-enhancements]
* Added support for aioredis 1.x [#2526](https://github.com/elastic/apm-agent-python/pull/1082)
* Added support for aiomysql [#1107](https://github.com/elastic/apm-agent-python/pull/1107)
* Added Redis pub/sub instrumentation [#1129](https://github.com/elastic/apm-agent-python/pull/1129)
* Added specific instrumentation for AWS SQS [#1123](https://github.com/elastic/apm-agent-python/pull/1123)

### Fixes [elastic-apm-python-agent-620-fixes]
* ensure metrics are flushed before agent shutdown [#1139](https://github.com/elastic/apm-agent-python/pull/1139)
* added safeguard for exceptions in processors [#1138](https://github.com/elastic/apm-agent-python/pull/1138)
* ensure sockets are closed which were opened for cloud environment detection [#1134](https://github.com/elastic/apm-agent-python/pull/1134)

## 6.1.3 [elastic-apm-python-agent-613-release-notes]
**Release date:** April 28, 2021

### Fixes [elastic-apm-python-agent-613-fixes]
* added destination information to asyncpg instrumentation [#1115](https://github.com/elastic/apm-agent-python/pull/1115)
* fixed issue with collecting request meta data with Django REST Framework [#1117](https://github.com/elastic/apm-agent-python/pull/1117)
* fixed httpx instrumentation for newly released httpx 0.18.0 [#1118](https://github.com/elastic/apm-agent-python/pull/1118)

## 6.1.2 [elastic-apm-python-agent-612-release-notes]
**Release date:** April 14, 2021

### Fixes [elastic-apm-python-agent-612-fixes]
* fixed issue with empty transaction name for the root route with Django [#1095](https://github.com/elastic/apm-agent-python/pull/1095)
* fixed on-the-fly initialisation of Flask apps [#1099](https://github.com/elastic/apm-agent-python/pull/1099)

## 6.1.1 [elastic-apm-python-agent-611-release-notes]
**Release date:** April 8, 2021

### Fixes [elastic-apm-python-agent-611-fixes]
* fixed a validation issue with the newly introduced instrumentation for S3, SNS and DynamoDB [#1090](https://github.com/elastic/apm-agent-python/pull/1090)

## 6.1.0 [elastic-apm-python-agent-610-release-notes]
**Release date:** March 31, 2021

### Features and enhancements [elastic-apm-python-agent-610-features-enhancements]
* Add global access to Client singleton object at `elasticapm.get_client()` [#1043](https://github.com/elastic/apm-agent-python/pull/1043)
* Add `log_ecs_formatting` config option [#1058](https://github.com/elastic/apm-agent-python/pull/1058) [#1063](https://github.com/elastic/apm-agent-python/pull/1063)
* Add instrumentation for httplib2 [#1031](https://github.com/elastic/apm-agent-python/pull/1031)
* Add better instrumentation for some AWS services (S3, SNS, DynamoDB) [#1054](https://github.com/elastic/apm-agent-python/pull/1054)
* Added beta support for collecting metrics from prometheus_client [#1083](https://github.com/elastic/apm-agent-python/pull/1083)

### Fixes [elastic-apm-python-agent-610-fixes]
* Fix for potential `capture_body: error` hang in Starlette/FastAPI [#1038](https://github.com/elastic/apm-agent-python/pull/1038)
* Fix a rare error around processing stack frames [#1012](https://github.com/elastic/apm-agent-python/pull/1012)
* Fix for Starlette/FastAPI to correctly capture request bodies as strings [#1041](https://github.com/elastic/apm-agent-python/pull/1042)
* Fix transaction names for Starlette Mount routes [#1037](https://github.com/elastic/apm-agent-python/pull/1037)
* Fix for elastic excepthook arguments [#1050](https://github.com/elastic/apm-agent-python/pull/1050)
* Fix issue with remote configuration when resetting config values [#1068](https://github.com/elastic/apm-agent-python/pull/1068)
* Use a label for the elasticapm Django app that is compatible with Django 3.2 validation [#1064](https://github.com/elastic/apm-agent-python/pull/1064)
* Fix an issue with undefined routes in Starlette [#1076](https://github.com/elastic/apm-agent-python/pull/1076)

## 6.0.0 [elastic-apm-python-agent-600-release-notes]
**Release date:** February 1, 2021

### Fixes [elastic-apm-python-agent-600-fixes]
* Fix for GraphQL span spamming from scalar fields with required flag [#1015](https://github.com/elastic/apm-agent-python/pull/1015)


