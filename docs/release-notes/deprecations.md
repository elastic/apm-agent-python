---
navigation_title: "Deprecations"
---

# {{apm-py-agent}} deprecations [elastic-apm-python-agent-deprecations]
Over time, certain Elastic functionality becomes outdated and is replaced or removed. To help with the transition, Elastic deprecates functionality for a period before removal, giving you time to update your applications. 

Review the deprecated functionality for {{apm-py-agent}}. While deprecations have no immediate impact, we strongly encourage you update your implementation after you upgrade. To learn how to upgrade, check out [Upgrading](/reference/upgrading.md).

% ## Next version
% **Release date:** Month day, year

% ::::{dropdown} Deprecation title
% Description of the deprecation.
% For more information, check [PR #](PR link).
% **Impact**<br> Impact of deprecation.
% **Action**<br> Steps for mitigating deprecation impact.
% ::::

## 6.23.0 [elastic-apm-python-agent-6230-deprecations]
**Release date:** July 30, 2024

* Python 3.6 support will be removed in version 7.0.0 of the agent.
* The log shipping LoggingHandler will be removed in version 7.0.0 of the agent.
* The log shipping feature in the Flask instrumentation will be removed in version 7.0.0 of the agent.
* The log shipping feature in the Django instrumentation will be removed in version 7.0.0 of the agent.
* The OpenTracing bridge will be removed in version 7.0.0 of the agent.
* Celery 4.0 support is deprecated because it’s not installable anymore with a modern pip.

## 6.20.0 [elastic-apm-python-agent-6200-deprecations]
**Release date:** January 10, 2024

* The log shipping LoggingHandler will be removed in version 7.0.0 of the agent.

## 6.19.0 [elastic-apm-python-agent-6190-deprecations]
**Release date:** October 11, 2023

* The log shipping feature in the Flask instrumentation will be removed in version 7.0.0 of the agent.