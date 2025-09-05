---
navigation_title: "Breaking changes"
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# Elastic APM Python Agent breaking changes [elastic-apm-python-agent-breaking-changes]

Before you upgrade, carefully review the Elastic APM RPython Agent breaking changes and take the necessary steps to mitigate any issues.

% To learn how to upgrade, check out <upgrade docs>.

% ## Next version [elastic-apm-python-agent-nextversion-breaking-changes]
% **Release date:** Month day, year

% ::::{dropdown} Title of breaking change
% Description of the breaking change.
% For more information, check [PR #](PR link).
% **Impact**<br> Impact of the breaking change.
% **Action**<br> Steps for mitigating deprecation impact.
% ::::

## 6.0.0 [elastic-apm-python-agent-600-breaking-changes]
**Release date:** February 1, 2021

* Python 2.7 and 3.5 support has been deprecated. The Python agent now requires Python 3.6+. For more information, check [#1021](https://github.com/elastic/apm-agent-python/pull/1021).
* No longer collecting body for `elasticsearch-py` update and `delete_by_query`. For more information, check [#1013](https://github.com/elastic/apm-agent-python/pull/1013).
* Align `sanitize_field_names` config with the [cross-agent spec](https://github.com/elastic/apm/blob/3fa78e2a1eeea81c73c2e16e96dbf6b2e79f3c64/specs/agents/sanitization.md). If you are using a non-default `sanitize_field_names`, surrounding each of your entries with stars (e.g. `*secret*`) will retain the old behavior. For more information, check [#982](https://github.com/elastic/apm-agent-python/pull/982).
* Remove credit card sanitization for field values. This improves performance, and the security value of this check was dubious anyway. For more information, check [#982](https://github.com/elastic/apm-agent-python/pull/982).
* Remove HTTP querystring sanitization. This improves performance, and is meant to standardize behavior across the agents, as defined in [#334](https://github.com/elastic/apm/pull/334). For more information, check [#982](https://github.com/elastic/apm-agent-python/pull/982).
* Remove `elasticapm.tag()` (deprecated since 5.0.0). For more information, check [#1034](https://github.com/elastic/apm-agent-python/pull/1034).
