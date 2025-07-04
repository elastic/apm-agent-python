---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/django-support.html
---

# Django support [django-support]

Getting Elastic APM set up for your Django project is easy, and there are various ways you can tweak it to fit to your needs.


## Installation [django-installation]

Install the Elastic APM agent using pip:

```bash
$ pip install elastic-apm
```

or add it to your project’s `requirements.txt` file.

::::{note}
For apm-server 6.2+, make sure you use version 2.0 or higher of `elastic-apm`.
::::


::::{note}
If you use Django with uwsgi, make sure to [enable threads](http://uwsgi-docs.readthedocs.org/en/latest/Options.html#enable-threads) (enabled by default since 2.0.27) and [py-call-uwsgi-fork-hooks](https://uwsgi-docs.readthedocs.io/en/latest/Options.html#py-call-uwsgi-fork-hooks).
::::



## Setup [django-setup]

Set up the Elastic APM agent in Django with these two steps:

1. Add `elasticapm.contrib.django` to `INSTALLED_APPS` in your settings:

```python
INSTALLED_APPS = (
   # ...
   'elasticapm.contrib.django',
)
```

1. Choose a service name, and set the secret token if needed.

```python
ELASTIC_APM = {
   'SERVICE_NAME': '<SERVICE-NAME>',
   'SECRET_TOKEN': '<SECRET-TOKEN>',
}
```

or as environment variables:

```shell
ELASTIC_APM_SERVICE_NAME=<SERVICE-NAME>
ELASTIC_APM_SECRET_TOKEN=<SECRET-TOKEN>
```

You now have basic error logging set up, and everything resulting in a 500 HTTP status code will be reported to the APM Server.

You can find a list of all available settings in the [Configuration](/reference/configuration.md) page.

::::{note}
The agent only captures and sends data if you have `DEBUG = False` in your settings. To force the agent to capture data in Django debug mode, set the [debug](/reference/configuration.md#config-debug) configuration option, e.g.:

```python
ELASTIC_APM = {
   'SERVICE_NAME': '<SERVICE-NAME>',
   'DEBUG': True,
}
```

::::



## Performance metrics [django-performance-metrics]

In order to collect performance metrics, the agent automatically inserts a middleware at the top of your middleware list (`settings.MIDDLEWARE` in current versions of Django, `settings.MIDDLEWARE_CLASSES` in some older versions). To disable the automatic insertion of the middleware, see [django_autoinsert_middleware](/reference/configuration.md#config-django-autoinsert-middleware).

::::{note}
For automatic insertion to work, your list of middlewares (`settings.MIDDLEWARE` or `settings.MIDDLEWARE_CLASSES`) must be of type `list` or `tuple`.
::::


In addition to broad request metrics (what will appear in the APM app as transactions), the agent also collects fine grained metrics on template rendering, database queries, HTTP requests, etc. You can find more information on what we instrument in the [Automatic Instrumentation](/reference/supported-technologies.md#automatic-instrumentation) section.


### Instrumenting custom Python code [django-instrumenting-custom-python-code]

To gain further insights into the performance of your code, please see [instrumenting custom code](/reference/instrumenting-custom-code.md).


### Ignoring specific views [django-ignoring-specific-views]

You can use the `TRANSACTIONS_IGNORE_PATTERNS` configuration option to ignore specific views. The list given should be a list of regular expressions which are matched against the transaction name as seen in the Elastic APM user interface:

```python
ELASTIC_APM['TRANSACTIONS_IGNORE_PATTERNS'] = ['^OPTIONS ', 'views.api.v2']
```

This example ignores any requests using the `OPTIONS` method and any requests containing `views.api.v2`.


### Using the route as transaction name [django-transaction-name-route]

By default, we use the function or class name of the view as the transaction name. Starting with Django 2.2, Django makes the route (e.g. `users/<int:user_id>/`) available on the `request.resolver_match` object. If you want to use the route instead of the view name as the transaction name, you can set the [`django_transaction_name_from_route`](/reference/configuration.md#config-django-transaction-name-from-route) config option to `true`.

```python
ELASTIC_APM['DJANGO_TRANSACTION_NAME_FROM_ROUTE'] = True
```

::::{note}
in versions previous to Django 2.2, changing this setting will have no effect.
::::



### Integrating with the RUM Agent [django-integrating-with-the-rum-agent]

To correlate performance measurement in the browser with measurements in your Django app, you can help the RUM (Real User Monitoring) agent by configuring it with the Trace ID and Span ID of the backend request. We provide a handy template context processor which adds all the necessary bits into the context of your templates.

To enable this feature, first add the `rum_tracing` context processor to your `TEMPLATES` setting. You most likely already have a list of `context_processors`, in which case you can simply append ours to the list.

```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'context_processors': [
                # ...
                'elasticapm.contrib.django.context_processors.rum_tracing',
            ],
        },
    },
]
```

Then, update the call to initialize the RUM agent (which probably happens in your base template) like this:

```javascript
elasticApm.init({
    serviceName: "my-frontend-service",
    pageLoadTraceId: "{{ apm.trace_id }}",
    pageLoadSpanId: "{{ apm.span_id }}",
    pageLoadSampled: {{ apm.is_sampled_js }}
})
```

See the [JavaScript RUM agent documentation](apm-agent-rum-js://reference/index.md) for more information.


## Enabling and disabling the agent [django-enabling-and-disabling-the-agent]

The easiest way to disable the agent is to set Django’s `DEBUG` option to `True` in your development configuration. No errors or metrics will be logged to Elastic APM.

However, if during debugging you would like to force logging of errors to Elastic APM, then you can set `DEBUG` to `True` inside of the Elastic APM configuration dictionary, like this:

```python
ELASTIC_APM = {
   # ...
   'DEBUG': True,
}
```


## Integrating with Python logging [django-logging]

To easily send Python `logging` messages as "error" objects to Elasticsearch, we provide a `LoggingHandler` which you can use in your logging setup. The log messages will be enriched with a stack trace, data from the request, and more.

::::{note}
the intended use case for this handler is to send high priority log messages (e.g. log messages with level `ERROR`) to Elasticsearch. For normal log shipping, we recommend using [filebeat](beats://reference/filebeat/index.md).
::::


If you are new to how the `logging` module works together with Django, read more [in the Django documentation](https://docs.djangoproject.com/en/2.1/topics/logging/).

An example of how your `LOGGING` setting could look:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'elasticapm': {
            'level': 'WARNING',
            'class': 'elasticapm.contrib.django.handlers.LoggingHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
        'mysite': {
            'level': 'WARNING',
            'handlers': ['elasticapm'],
            'propagate': False,
        },
        # Log errors from the Elastic APM module to the console (recommended)
        'elasticapm.errors': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}
```

With this configuration, logging can be done like this in any module in the `myapp` django app:

You can now use the logger in any module in the `myapp` Django app, for instance `myapp/views.py`:

```python
import logging
logger = logging.getLogger('mysite')

try:
    instance = MyModel.objects.get(pk=42)
except MyModel.DoesNotExist:
    logger.error(
        'Could not find instance, doing something else',
        exc_info=True
    )
```

Note that `exc_info=True` adds the exception information to the data that gets sent to Elastic APM. Without it, only the message is sent.


### Extra data [django-extra-data]

If you want to send more data  than what you get with the agent by default, logging can be done like so:

```python
import logging
logger = logging.getLogger('mysite')

try:
    instance = MyModel.objects.get(pk=42)
except MyModel.DoesNotExist:
    logger.error(
        'There was some crazy error',
        exc_info=True,
        extra={
            'datetime': str(datetime.now()),
        }
    )
```


## Celery integration [django-celery-integration]

For a general guide on how to set up Django with Celery, head over to Celery’s [Django documentation](http://celery.readthedocs.org/en/latest/django/first-steps-with-django.html#django-first-steps).

Elastic APM will automatically log errors from your celery tasks, record performance data and keep the trace.id when the task is launched from an already started Elastic transaction.


## Logging "HTTP 404 Not Found" errors [django-logging-http-404-not-found-errors]

By default, Elastic APM does not log HTTP 404 errors. If you wish to log these errors, add `'elasticapm.contrib.django.middleware.Catch404Middleware'` to `MIDDLEWARE` in your settings:

```python
MIDDLEWARE = (
    # ...
    'elasticapm.contrib.django.middleware.Catch404Middleware',
    # ...
)
```

Note that this middleware respects Django’s [`IGNORABLE_404_URLS`](https://docs.djangoproject.com/en/1.11/ref/settings/#ignorable-404-urls) setting.


## Disable the agent during tests [django-disable-agent-during-tests]

To prevent the agent from sending any data to the APM Server during tests, set the `ELASTIC_APM_DISABLE_SEND` environment variable to `true`, e.g.:

```python
ELASTIC_APM_DISABLE_SEND=true python manage.py test
```


## Troubleshooting [django-troubleshooting]

Elastic APM comes with a Django command that helps troubleshooting your setup. To check your configuration, run

```bash
python manage.py elasticapm check
```

To send a test exception using the current settings, run

```bash
python manage.py elasticapm test
```

If the command succeeds in sending a test exception, it will print a success message:

```bash
python manage.py elasticapm test

Trying to send a test error using these settings:

SERVICE_NAME:      <SERVICE_NAME>
SECRET_TOKEN:      <SECRET_TOKEN>
SERVER:            http://127.0.0.1:8200

Success! We tracked the error successfully! You should be able to see it in a few seconds.
```


## Supported Django and Python versions [supported-django-and-python-versions]

A list of supported [Django](/reference/supported-technologies.md#supported-django) and [Python](/reference/supported-technologies.md#supported-python) versions can be found on our [Supported Technologies](/reference/supported-technologies.md) page.

