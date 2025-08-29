---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/metrics.html
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

# Metrics [metrics]

With Elastic APM, you can capture system and process metrics. These metrics will be sent regularly to the APM Server and from there to Elasticsearch


## Metric sets [metric-sets]

* [CPU/Memory metric set](#cpu-memory-metricset)
* [Breakdown metric set](#breakdown-metricset)
* [Prometheus metric set (beta)](#prometheus-metricset)
* [Custom Metrics](#custom-metrics)


### CPU/Memory metric set [cpu-memory-metricset]

`elasticapm.metrics.sets.cpu.CPUMetricSet`

This metric set collects various system metrics and metrics of the current process.

::::{note}
if you do **not** use Linux, you need to install [`psutil`](https://pypi.org/project/psutil/) for this metric set.
::::


**`system.cpu.total.norm.pct`**
:   type: scaled_float

format: percent

The percentage of CPU time in states other than Idle and IOWait, normalized by the number of cores.


**`system.process.cpu.total.norm.pct`**
:   type: scaled_float

format: percent

The percentage of CPU time spent by the process since the last event. This value is normalized by the number of CPU cores and it ranges from 0 to 100%.


**`system.memory.total`**
:   type: long

format: bytes

Total memory.


**`system.memory.actual.free`**
:   type: long

format: bytes

Actual free memory in bytes.


**`system.process.memory.size`**
:   type: long

format: bytes

The total virtual memory the process has.


**`system.process.memory.rss.bytes`**
:   type: long

format: bytes

The Resident Set Size. The amount of memory the process occupied in main memory (RAM).



#### Linux’s cgroup metrics [cpu-memory-cgroup-metricset]

**`system.process.cgroup.memory.mem.limit.bytes`**
:   type: long

format: bytes

Memory limit for current cgroup slice.


**`system.process.cgroup.memory.mem.usage.bytes`**
:   type: long

format: bytes

Memory usage in current cgroup slice.



### Breakdown metric set [breakdown-metricset]

::::{note}
Tracking and collection of this metric set can be disabled using the [`breakdown_metrics`](/reference/configuration.md#config-breakdown_metrics) setting.
::::


**`span.self_time`**
:   type: simple timer

This timer tracks the span self-times and is the basis of the transaction breakdown visualization.

Fields:

* `sum`: The sum of all span self-times in ms since the last report (the delta)
* `count`: The count of all span self-times since the last report (the delta)

You can filter and group by these dimensions:

* `transaction.name`: The name of the transaction
* `transaction.type`: The type of the transaction, for example `request`
* `span.type`: The type of the span, for example `app`, `template` or `db`
* `span.subtype`: The sub-type of the span, for example `mysql` (optional)



### Prometheus metric set (beta) [prometheus-metricset]

::::{warning}
This functionality is in beta and is subject to change. The design and code is less mature than official GA features and is being provided as-is with no warranties. Beta features are not subject to the support SLA of official GA features.
::::


If you use [`prometheus_client`](https://github.com/prometheus/client_python) to collect metrics, the agent can collect them as well and make them available in Elasticsearch.

The following types of metrics are supported:

* Counters
* Gauges
* Summaries
* Histograms (requires APM Server / Elasticsearch / Kibana 7.14+)

To use the Prometheus metric set, you have to enable it with the [`prometheus_metrics`](/reference/configuration.md#config-prometheus_metrics) configuration option.

All metrics collected from `prometheus_client` are prefixed with `"prometheus.metrics."`. This can be changed using the [`prometheus_metrics_prefix`](/reference/configuration.md#config-prometheus_metrics_prefix) configuration option.


#### Beta limitations [prometheus-metricset-beta]

* The metrics format may change without backwards compatibility in future releases.


## Custom Metrics [custom-metrics]

Custom metrics allow you to send your own metrics to Elasticsearch.

The most common way to send custom metrics is with the [Prometheus metric set](#prometheus-metricset).  However, you can also use your own metric set. If you collect the metrics manually in your code, you can use the base `MetricSet` class:

```python
from elasticapm.metrics.base_metrics import MetricSet

client = elasticapm.Client()
metricset = client.metrics.register(MetricSet)

for x in range(10):
    metricset.counter("my_counter").inc()
```

Alternatively, you can create your own MetricSet class which inherits from the base class. In this case, you’ll usually want to override the `before_collect` method, where you can gather and set metrics before they are collected and sent to Elasticsearch.

You can add your `MetricSet` class as shown in the example above, or you can add an import string for your class to the [`metrics_sets`](/reference/configuration.md#config-metrics_sets) configuration option:

```bash
ELASTIC_APM_METRICS_SETS="elasticapm.metrics.sets.cpu.CPUMetricSet,myapp.metrics.MyMetricSet"
```

Your MetricSet might look something like this:

```python
from elasticapm.metrics.base_metrics import MetricSet

class MyAwesomeMetricSet(MetricSet):
    def before_collect(self):
        self.gauge("my_gauge").set(myapp.some_value)
```

In the example above, the MetricSet would look up `myapp.some_value` and set the metric `my_gauge` to that value. This would happen whenever metrics are collected/sent, which is controlled by the [`metrics_interval`](/reference/configuration.md#config-metrics_interval) setting.

