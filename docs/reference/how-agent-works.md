---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/how-the-agent-works.html
---

# How the Agent works [how-the-agent-works]

To gather APM events (called transactions and spans), errors and metrics, the Python agent instruments your application in a few different ways. These events, are then sent to the APM Server. The APM Server converts them to a format suitable for Elasticsearch, and sends them to an Elasticsearch cluster. You can then use the APM app in Kibana to gain insight into latency issues and error culprits within your application.

Broadly, we differentiate between three different approaches to collect the necessary data: framework integration, instrumentation, and background collection.


## Framework integration [how-it-works-framework-integration]

To collect data about incoming requests and background tasks, we integrate with frameworks like [Django](/reference/django-support.md), [Flask](/reference/flask-support.md) and Celery. Whenever possible, framework integrations make use of hooks and signals provided by the framework. Examples of this are:

* `request_started`, `request_finished`, and `got_request_exception` signals from `django.core.signals`
* `request_started`, `request_finished`, and `got_request_exception` signals from `flask.signals`
* `task_prerun`, `task_postrun`, and `task_failure` signals from `celery.signals`

Framework integrations require some limited code changes in your app. E.g. for Django, you need to add `elasticapm.contrib.django` to `INSTALLED_APPS`.


## What if you are not using a framework [how-it-works-no-framework]

If you’re not using a supported framework, for example, a simple Python script, you can still leverage the agent’s [automatic instrumentation](/reference/supported-technologies.md#automatic-instrumentation). Check out our docs on [instrumenting custom code](/reference/instrumenting-custom-code.md).


## Instrumentation [how-it-works-instrumentation]

To collect data from database drivers, HTTP libraries etc., we instrument certain functions and methods in these libraries. Our instrumentation wraps these callables and collects additional data, like

* time spent in the call
* the executed query for database drivers
* the fetched URL for HTTP libraries

We use a 3rd party library, [`wrapt`](https://github.com/GrahamDumpleton/wrapt), to wrap the callables. You can read more on how `wrapt` works in Graham Dumpleton’s excellent series of [blog posts](http://blog.dscpl.com.au/search/label/wrapt).

Instrumentations are set up automatically and do not require any code changes. See [Automatic Instrumentation](/reference/supported-technologies.md#automatic-instrumentation) to learn more about which libraries we support.


## Background collection [how-it-works-background-collection]

In addition to APM and error data, the Python agent also collects system and application metrics in regular intervals. This collection happens in a background thread that is started by the agent.

In addition to the metrics collection background thread, the agent starts two additional threads per process:

* a thread to regularly fetch remote configuration from the APM Server
* a thread to process the collected data and send it to the APM Server via HTTP.

Note that every process that instantiates the agent will have these three threads. This means that when you e.g. use gunicorn or uwsgi workers, each worker will have three threads started by the Python agent.

