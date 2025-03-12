---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/wrapper-support.html
---

# Wrapper Support [wrapper-support]

::::{warning}
This functionality is in technical preview and may be changed or removed in a future release. Elastic will work to fix any issues, but features in technical preview are not subject to the support SLA of official GA features.
::::


The following frameworks are supported using our new wrapper script for no-code-changes instrumentation:

* Django
* Flask
* Starlette

Please keep in mind that these instrumentations are a work in progress! We’d love to have feedback on our [issue tracker](https://github.com/elastic/apm-agent-python/issues/new/choose).

## Usage [wrapper-usage]

When installing the agent, an entrypoint script, `elasticapm-run` is installed as well. You can use this script to instrument your app (assuming it’s using a supported framework) without changing your code!

```bash
$ elasticapm-run --version
elasticapm-run 6.14.0
```

Alternatively, you can run the entrypoint directly:

```bash
$ python -m elasticapm.instrumentation.wrapper --version
elasticapm-run 6.14.0
```

The `elasticapm-run` script can be used to run any Python script or module:

```bash
$ elasticapm-run flask run
$ elasticapm-run python myapp.py
```

Generally, config should be passed in via environment variables. For example,

```bash
$ ELASTIC_APM_SERVICE_NAME=my_flask_app elasticapm-run flask run
```

You can also pass config options as arguments to the script:

```bash
$ elasticapm-run --config "service_name=my_flask_app" --config "debug=true" flask run
```


