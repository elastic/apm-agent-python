---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/getting-started.html
  - https://www.elastic.co/guide/en/apm/agent/python/current/index.html
---

# APM Python agent [getting-started]

The Elastic APM Python agent sends performance metrics and error logs to the APM Server. It has built-in support for Django and Flask performance metrics and error logging, as well as generic support of other WSGI frameworks for error logging.


## How does the Agent work? [how-it-works]

The Python Agent instruments your application to collect APM events in a few different ways:

To collect data about incoming requests and background tasks, the Agent integrates with [supported technologies](/reference/supported-technologies.md) to make use of hooks and signals provided by the framework. These framework integrations require limited code changes in your application.

To collect data from database drivers, HTTP libraries etc., we instrument certain functions and methods in these libraries. Instrumentations are set up automatically and do not require any code changes.

In addition to APM and error data, the Python agent also collects system and application metrics in regular intervals. This collection happens in a background thread that is started by the agent.

More detailed information on how the Agent works can be found in the [advanced topics](/reference/how-agent-works.md).


## Additional components [additional-components]

APM Agents work in conjunction with the [APM Server](docs-content://solutions/observability/apps/application-performance-monitoring-apm.md), [Elasticsearch](docs-content://get-started/introduction.md#what-is-es), and [Kibana](docs-content://get-started/introduction.md#what-is-kib). The [APM documentation](docs-content://solutions/observability/apps/application-performance-monitoring-apm.md) provides details on how these components work together, and provides a matrix outlining [Agent and Server compatibility](docs-content://solutions/observability/apps/apm-agent-compatibility.md).

