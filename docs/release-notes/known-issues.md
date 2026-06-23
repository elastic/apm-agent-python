---
navigation_title: "Known issues"
applies_to:
  stack:
  serverless:
    observability:
  product:
    apm_agent_python: ga
---

# Elastic APM Python Agent known issues [elastic-apm-python-agent-known-issues]

Known issues are significant defects or limitations that may impact your implementation. These issues are actively being worked on and will be addressed in a future release. Review the Elastic APM Python Agent known issues to help you make informed decisions, such as upgrading to a new version.

% Use the following template to add entries to this page.

% :::{dropdown} Title of known issue
% **Details** 
% On [Month/Day/Year], a known issue was discovered that [description of known issue].

% **Workaround** 
% Workaround description.

% **Resolved**
% On [Month/Day/Year], this issue was resolved.

:::

:::{dropdown} FastAPI 0.137+ causes 500 errors on every request
**Details**

On 06/19/2026, a known issue was discovered that FastAPI 0.137 changed how included routers are represented internally, introducing `_IncludedRouter` wrapper objects that do not expose a `.path` attribute. The ElasticAPM Starlette/FastAPI middleware accessed `.path` unconditionally, causing an `AttributeError` and a 500 response on every HTTP request when using `app.include_router()`.

**Workaround**

Pin `fastapi<0.137` until you can upgrade to `elastic-apm>=6.26.2`.

**Resolved**

On 06/22/2026, this issue was resolved in [{{product.apm-agent-python}} 6.26.2](index.md#elastic-apm-python-agent-6262-release-notes).
:::