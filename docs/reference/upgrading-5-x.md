---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/upgrading-5.x.html
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

# Upgrading to version 5 of the agent [upgrading-5-x]

## APM Server 7.3 required for some features [_apm_server_7_3_required_for_some_features]

APM Server and Kibana 7.3 introduced support for collecting breakdown metrics, and central configuration of APM agents. To use these features, please update the Python agent to 5.0+ and APM Server / Kibana to 7.3+


## Tags renamed to Labels [_tags_renamed_to_labels]

To better align with other parts of the Elastic Stack and the [Elastic Common Schema](ecs://reference/index.md), we renamed "tags" to "labels", and introduced limited support for typed labels. While tag values were only allowed to be strings, label values can be strings, booleans, or numerical.

To benefit from this change, ensure that you run at least **APM Server 6.7**, and use `elasticapm.label()` instead of `elasticapm.tag()`. The `tag()` API will continue to work as before, but emit a `DeprecationWarning`. It will be removed in 6.0 of the agent.


