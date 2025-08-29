---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/upgrading-4.x.html
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

# Upgrading to version 4 of the agent [upgrading-4-x]

4.0 of the Elastic APM Python Agent comes with several backwards incompatible changes.

## APM Server 6.5 required [upgrading-4-x-apm-server]

This version of the agent is **only compatible with APM Server 6.5+**. To upgrade, we recommend to first upgrade APM Server, and then the agent. APM Server 6.5+ is backwards compatible with versions 2.x and 3.x of the agent.


## Configuration options [upgrading-4-x-configuration]

Several configuration options have been removed, or renamed

* `flush_interval` has been removed
* the `flush_interval` and `max_queue_size` settings have been removed.
* new settings introduced: `api_request_time` and `api_request_size`.
* Some settings now require a unit for duration or size. See [size format](configuration.md#config-format-size) and [duration format](configuration.md#config-format-duration).


## Processors [upgrading-4-x-processors]

The method to write processors for sanitizing events has been changed. It will now be called for every type of event (transactions, spans and errors), unless the event types are limited using a decorator. See [Sanitizing data](sanitizing-data.md) for more information.


