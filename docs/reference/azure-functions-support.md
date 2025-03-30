---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/azure-functions-support.html
---

# Monitoring Azure Functions [azure-functions-support]


## Prerequisites [_prerequisites_2]

You need an APM Server to which you can send APM data. Follow the [APM Quick start](docs-content://solutions/observability/apps/fleet-managed-apm-server.md) if you have not set one up yet. For the best-possible performance, we recommend setting up APM on {{ecloud}} in the same Azure region as your Azure Functions app.

::::{note}
Currently, only HTTP and timer triggers are supported. Other trigger types may be captured as well, but the amount of captured contextual data may differ.
::::



## Step 1: Enable Worker Extensions [_step_1_enable_worker_extensions]

Elastic APM uses [Worker Extensions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python?tabs=asgi%2Capplication-level&pivots=python-mode-configuration#python-worker-extensions) to instrument Azure Functions. This feature is not enabled by default, and must be enabled in your Azure Functions App. Please follow the instructions in the [Azure docs](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python?tabs=asgi%2Capplication-level&pivots=python-mode-configuration#using-extensions).

Once you have enabled Worker Extensions, these two lines of code will enable Elastic APM’s extension:

```python
from elasticapm.contrib.serverless.azure import ElasticAPMExtension

ElasticAPMExtension.configure()
```

Put them somewhere at the top of your Python file, before the function definitions.


## Step 2: Install the APM Python Agent [_step_2_install_the_apm_python_agent]

You need to add `elastic-apm` as a dependency for your Functions app. Simply add `elastic-apm` to your `requirements.txt` file. We recommend pinning the version to the current newest version of the agent, and periodically updating the version.


## Step 3: Configure APM on Azure Functions [_step_3_configure_apm_on_azure_functions]

The APM Python agent is configured through [App Settings](https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-use-azure-function-app-settings?tabs=portal#settings). These are then picked up by the agent as environment variables.

For the minimal configuration, you will need the [`ELASTIC_APM_SERVER_URL`](/reference/configuration.md#config-server-url) to set the destination for APM data and a [`ELASTIC_APM_SECRET_TOKEN`](/reference/configuration.md#config-secret-token). If you prefer to use an [APM API key](docs-content://solutions/observability/apps/api-keys.md) instead of the APM secret token, use the [`ELASTIC_APM_API_KEY`](/reference/configuration.md#config-api-key) environment variable instead of `ELASTIC_APM_SECRET_TOKEN` in the following example configuration.

```bash
$ az functionapp config appsettings set --settings ELASTIC_APM_SERVER_URL=https://example.apm.northeurope.azure.elastic-cloud.com:443
$ az functionapp config appsettings set --settings ELASTIC_APM_SECRET_TOKEN=verysecurerandomstring
```

You can optionally [fine-tune the Python agent](/reference/configuration.md).

That’s it; Once the agent is installed and working, spans will be captured for [supported technologies](/reference/supported-technologies.md). You can also use [`capture_span`](/reference/api-reference.md#api-capture-span) to capture custom spans, and you can retrieve the `Client` object for capturing exceptions/messages using [`get_client`](/reference/api-reference.md#api-get-client).

