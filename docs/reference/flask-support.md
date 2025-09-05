---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/flask-support.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# Flask support [flask-support]

Getting Elastic APM set up for your Flask project is easy, and there are various ways you can tweak it to fit to your needs.


## Installation [flask-installation]

Install the Elastic APM agent using pip:

```bash
$ pip install "elastic-apm[flask]"
```

or add `elastic-apm[flask]` to your project’s `requirements.txt` file.

::::{note}
For apm-server 6.2+, make sure you use version 2.0 or higher of `elastic-apm`.
::::


::::{note}
If you use Flask with uwsgi, make sure to [enable threads](http://uwsgi-docs.readthedocs.org/en/latest/Options.html#enable-threads) (enabled by default since 2.0.27) and [py-call-uwsgi-fork-hooks](https://uwsgi-docs.readthedocs.io/en/latest/Options.html#py-call-uwsgi-fork-hooks).
::::


::::{note}
If you see an error log that mentions `psutil not found`, you can install `psutil` using `pip install psutil`, or add `psutil` to your `requirements.txt` file.
::::



## Setup [flask-setup]

To set up the agent, you need to initialize it with appropriate settings.

The settings are configured either via environment variables, the application’s settings, or as initialization arguments.

You can find a list of all available settings in the [Configuration](/reference/configuration.md) page.

To initialize the agent for your application using environment variables:

```python
from elasticapm.contrib.flask import ElasticAPM

app = Flask(__name__)

apm = ElasticAPM(app)
```

To configure the agent using `ELASTIC_APM` in your application’s settings:

```python
from elasticapm.contrib.flask import ElasticAPM

app.config['ELASTIC_APM'] = {
    'SERVICE_NAME': '<SERVICE-NAME>',
    'SECRET_TOKEN': '<SECRET-TOKEN>',
}
apm = ElasticAPM(app)
```

The final option is to initialize the agent with the settings as arguments:

```python
from elasticapm.contrib.flask import ElasticAPM

apm = ElasticAPM(app, service_name='<APP-ID>', secret_token='<SECRET-TOKEN>')
```


### Debug mode [flask-debug-mode]

::::{note}
Please note that errors and transactions will only be sent to the APM Server if your app is **not** in [Flask debug mode](https://flask.palletsprojects.com/en/3.0.x/quickstart/#debug-mode).
::::


To force the agent to send data while the app is in debug mode, set the value of `DEBUG` in the `ELASTIC_APM` dictionary to `True`:

```python
app.config['ELASTIC_APM'] = {
        'SERVICE_NAME': '<SERVICE-NAME>',
        'SECRET_TOKEN': '<SECRET-TOKEN>',
        'DEBUG': True
}
```


### Building applications on the fly? [flask-building-applications-on-the-fly]

You can use the agent’s `init_app` hook for adding the application on the fly:

```python
from elasticapm.contrib.flask import ElasticAPM
apm = ElasticAPM()

def create_app():
    app = Flask(__name__)
    apm.init_app(app, service_name='<SERVICE-NAME>', secret_token='<SECRET-TOKEN>')
    return app
```


## Usage [flask-usage]

Once you have configured the agent, it will automatically track transactions and capture uncaught exceptions within Flask. If you want to send additional events, a couple of shortcuts are provided on the ElasticAPM Flask middleware object by raising an exception or logging a generic message.

Capture an arbitrary exception by calling `capture_exception`:

```python
try:
    1 / 0
except ZeroDivisionError:
    apm.capture_exception()
```

Log a generic message with `capture_message`:

```python
apm.capture_message('hello, world!')
```


## Shipping Logs to Elasticsearch [flask-logging]

This feature has been deprecated and will be removed in a future version.

Please see our [Logging](/reference/logs.md) documentation for other supported ways to ship logs to Elasticsearch.

Note that you can always send exceptions and messages to the APM Server with [`capture_exception`](/reference/api-reference.md#client-api-capture-exception) and and [`capture_message`](/reference/api-reference.md#client-api-capture-message).

```python
from elasticapm import get_client

@app.route('/')
def bar():
    try:
        1 / 0
    except ZeroDivisionError:
        get_client().capture_exception()
```


### Extra data [flask-extra-data]

In addition to what the agents log by default, you can send extra information:

```python
@app.route('/')
def bar():
    try:
        1 / 0
    except ZeroDivisionError:
        app.logger.error('Math is hard',
            exc_info=True,
            extra={
                'good_at_math': False,
            }
        )
    )
```


### Celery tasks [flask-celery-tasks]

The Elastic APM agent will automatically send errors and performance data from your Celery tasks to the APM Server.


## Performance metrics [flask-performance-metrics]

If you’ve followed the instructions above, the agent has already hooked into the right signals and should be reporting performance metrics.


### Ignoring specific routes [flask-ignoring-specific-views]

You can use the [`TRANSACTIONS_IGNORE_PATTERNS`](/reference/configuration.md#config-transactions-ignore-patterns) configuration option to ignore specific routes. The list given should be a list of regular expressions which are matched against the transaction name:

```python
app.config['ELASTIC_APM'] = {
    ...
    'TRANSACTIONS_IGNORE_PATTERNS': ['^OPTIONS ', '/api/']
    ...
}
```

This would ignore any requests using the `OPTIONS` method and any requests containing `/api/`.


### Integrating with the RUM Agent [flask-integrating-with-the-rum-agent]

To correlate performance measurement in the browser with measurements in your Flask app, you can help the RUM (Real User Monitoring) agent by configuring it with the Trace ID and Span ID of the backend request. We provide a handy template context processor which adds all the necessary bits into the context of your templates.

The context processor is installed automatically when you initialize `ElasticAPM`. All that is left to do is to update the call to initialize the RUM agent (which probably happens in your base template) like this:

```javascript
elasticApm.init({
    serviceName: "my-frontend-service",
    pageLoadTraceId: "{{ apm["trace_id"] }}",
    pageLoadSpanId: "{{ apm["span_id"]() }}",
    pageLoadSampled: {{ apm["is_sampled_js"] }}
})
```

See the [JavaScript RUM agent documentation](apm-agent-rum-js://reference/index.md) for more information.


## Supported Flask and Python versions [supported-flask-and-python-versions]

A list of supported [Flask](/reference/supported-technologies.md#supported-flask) and [Python](/reference/supported-technologies.md#supported-python) versions can be found on our [Supported Technologies](/reference/supported-technologies.md) page.

