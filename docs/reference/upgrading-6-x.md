---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/upgrading-6.x.html
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# Upgrading to version 6 of the agent [upgrading-6-x]

## Python 2 no longer supported [_python_2_no_longer_supported]

Please upgrade to Python 3.6+ to continue to receive regular updates.


## `SANITIZE_FIELD_NAMES` changes [_sanitize_field_names_changes]

If you are using a non-default `sanitize_field_names` config, please note that your entries must be surrounded with stars (e.g. `*secret*`) in order to maintain previous behavior.


## Tags removed (in favor of labels) [_tags_removed_in_favor_of_labels]

Tags were deprecated in the 5.x release (in favor of labels). They have now been removed.


