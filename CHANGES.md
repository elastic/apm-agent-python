### 3.2 ###
 * prefixed Django and Flask transaction names with HTTP methods names
 * Note: This means views in the "Views" list on the Opbeat performance tab will 
   change their name and you will have both non-prefixed names and http method 
   prefixed names in the list until the old names fall out of the selected timeframe

### 3.1.4 ###
 * added possibility to override the transport class used by the client
 * fixed a regression in our frame walker for Django templates in Django 1.9+

### 3.1.3 ###
 * fixed an issue where SSL connections would not get closed on the client
 * added support for OPBEAT_WRAPT_EXTENSIONS to override building of the
   wrapt C extension module during installation.

### 3.1.2 ###
 * preliminary support for Django 1.9
 * support for Python 3.5
 * added OPBEAT_DISABLE_SEND environment variable to completely stop sending
   data to Opbeat
 * improved test suite
  
### 3.1.1 ###
 * Fixed bug in Redis instrumentation introduced in 3.1 refactor.

## 3.1 ##
 * Flask APM support. Install as opbeat[flask] to ensure flask deps are installed.
 * Introduce @opbeat.trace decorator for better insights into custom code
 * Internal refactoring to support the decorator.
 * Stop instrumenting pipelined Redis operations.
 
### 3.0.4 ##
 * Only log one line per module we failed to instrument

### 3.0.3 ##
 * Fix a problem that occurs when `end_transaction` gets called twice in a row
 * Silently ignore `DatabaseError` when collecting user info for Django.
 * Better error logging with `async=True`
 * Renamed `async` keyword in anticipation of Python 3.5+
 * Instruments Django middleware by default to give better insights in APM
 * Better sanitation of http body
 * A bit of cleanups and refactoring

### 3.0.2 ##
 * Fix a bug in trace reporting that occurred if the traced code would raise
 * Introduce a management command to test out local Opbeat configuration and
   send a test exception.
 * Include templates in stackframes in traces.
 * Various bug fixes related to stackframes in traces.

### 3.0.1 ##
 * instrument python-memcached
 * Make sure only one of urllib3 and requests will show up on traces

### 3.0 ##
 * introduced instrumentation to enable in-depth performance monitoring
 * began deprecation of camelCase style `capture` methods on `Client.
   Full deprecation in 4.0.

### 2.1.1 ##
 * refactored AyncWorker, should now be better behaved when shutting down
 * fixed bug with django-configurations

## 2.1 ##
 * fixed issue with template debug in Django 1.9 (unreleased)
 * added experimental support for instrumenting Django middleware for
   better metrics data

### 2.0.4 ###
 * fixed bug with Django and `DEBUG = True`

### 2.0.3 ###
 * fixed bug in collecting Django POST data

### 2.0.2 ###
 * start using the new intake URL
 * Flask: module now adheres to the Flask.debug option and does not log to
   Opbeat unless it is False

### 2.0.1 ###
 * Fixed a bug when `__name__` does not exist for `view_func` given to
   `OpbeatAPMMiddleware`

# 2.0 #
 * Async support was refactored, removed old `AsyncClient` classes
 * `OpbeatAPMMiddleware` was added to time requests
 * `APP_ID` now configurable from environment
 * Lots of cleanups 

## 1.4 ##
 * added preliminary support for Django 1.8
 * dropped support for Django 1.3
 * When using Django, only try to submit user data if ``django.contrib.auth`` is
   installed. Thanks @nickbruun for the report and fix!

### 1.3.2 ###
 * fixed configuration of Flask integration to follow our documentation. The old
   behaviour still works, but has been deprecated.
   Please refer to https://opbeat.com/docs/articles/error-logging-in-flask/ for
   the configuration variable names.

### 1.3.1 ###

 * fixed catching local variables in celery tasks
 * added AppConfig for Django 1.7, thanks @stefanfoulis
 * fixed JSON encoding for the ``bytes`` type in Python 3, thanks Trey Long for
   the report

## 1.3 ##

 * added support for Django 1.7
 * dropped support for Django 1.2
 * switched from nosetests to py.test

## 1.2 ##

 * support for Python 3

## 1.1 ##

 * Renamed from opbeat_python to opbeat.
 * Simplified configuration
 * Conform to the updated Opbeat API.

# 1.0 #

 * Changes to conform to the Opbeat API.
 * Forked from Raven 1.9.0

## 1.9.0 ##

 * Signatures are no longer sent with messages. This requires the server version to be at least 4.4.6.
 * Several fixes and additions were added to the Django report view.
 * ``long`` types are now handled in ``transform()``.
 * Improved integration with Celery (and django-celery) for capturing errors.

## 1.8.0 ##

 * There is now a builtin view as part of the Django integration for sending events server-side
  (from the client) to Sentry. The view is currently undocumented, but is available as ``{% url raven-report %}``
  and will use your server side credentials. To use this view you'd simply swap out the servers configuration in
  raven-js and point it to the given URL.
 * A new middleware for ZeroRPC now exists.
 * A new protocol for registering transports now exists.
 * Corrected some behavior in the UDP transport.
 * Celery signals are now connected by default within the Django integration.

## 1.7.0 ##

 * The password sanitizer will now attempt to sanitize key=value pairs within strings (such as the querystring).
 * Two new santiziers were added: RemoveStackLocalsProcessor and RemovePostDataProcessor

### 1.6.0 ###

 * Stacks must now be passed as a list of tuples (frame, lineno) rather than a list of frames. This
  includes calls to logging (extra={'stack': []}), as well as explicit client calls (capture(stack=[])).

  This corrects some issues (mostly in tracebacks) with the wrong lineno being reported for a frame.

## 1.4.0 ##

 * raven now tracks the state of the Sentry server. If it receives an error, it will slow down
  requests to the server (by passing them into a named logger, sentry.errors), and increasingly
  delay the next try with repeated failures, up to about a minute.

### 1.3.6 ###

 * gunicorn is now disabled in default logging configuration

### 1.3.5 ###

 * Moved exception and message methods to capture{Exception,Message}.
 * Added ``captureQuery`` method.

### 1.3.4 ###

 * Corrected duplicate DSN behavior in Django client.

### 1.3.3 ###

 * Django can now be configured by setting SENTRY_DSN.
 * Improve logging for send_remote failures (and correct issue created when
  send_encoded was introduced).
 * Renamed SantizePassworsProcessor to SanitizePassworsProcessor.

### 1.3.2 ###

 * Support sending the culprit with logging messages as part of extra.

### 1.3.1 ###

 * Added client.exception and client.message shortcuts.

## 1.3.0 ##

 * Refactored client send API to be more easily extensible.
 * MOAR TESTS!

### 1.2.2 ###

 * Gracefully handle exceptions in Django client when using integrated
  setup.
 * Added Client.error_logger as a new logger instance that points to
  ``sentry.errors``.

### 1.2.1 ###

 * Corrected behavior with raven logging errors to send_remote
  which could potentially cause a very large backlog to Sentry
  when it should just log to ``sentry.errors``.
 * Ensure the ``site`` argument is sent to the server.

## 1.2.0 ##

 * Made DSN a first-class citizen throughout raven.
 * Added a Pylons-specific WSGI middleware.
 * Improved the generic WSGI middleware to capture HTTP information.
 * Improved logging and logbook handlers.

### 1.1.6 ###

 * Corrected logging stack behavior so that it doesnt capture raven+logging
  extensions are part of the frames.

### 1.1.5 ###

 * Remove logging attr magic.

### 1.1.4 ###

 * Correct encoding behavior on bool and float types.

### 1.1.3 ###

 * Fix 'request' attribute on Django logging.

### 1.1.2 ###

 * Corrected logging behavior with extra data to match pre 1.x behavior.

### 1.1.1 ###

 * Handle frames that are missing f_globals and f_locals.
 * Stricter conversion of int and boolean values.
 * Handle invalid sources for templates in Django.

## 1.1.0 ##

 * varmap was refactored to send keys back to callbacks.
 * SanitizePasswordProcessor now handles http data.

### 1.0.5 ###

 * Renaming raven2 to raven as it causes too many issues.

### 1.0.4 ###

 * Corrected a bug in setup_logging.
 * raven now sends "sentry_version" header which is the expected
  server version.

### 1.0.3 ###

 * Handle more edge cases on stack iteration.

### 1.0.2 ###

 * Gracefully handle invalid f_locals.

### 1.0.1 ###

 * All datetimes are assumed to be utcnow() as of Sentry 2.0.0-RC5

## 1.0.0 ##

 * Now only works with Sentry>=2.0.0 server.
 * raven is now listed as raven2 on PyPi.

## 0.8.0 ##

 * raven.contrib.celery is now useable.
 * raven.contrib.django.celery is now useable.
 * Fixed a bug with request.raw_post_data buffering in Django.

### 0.7.1 ###

 * Servers would stop iterating after the first successful post which was not the
  intended behavior.

## 0.7.0 ##

 * You can now explicitly pass a list of frame objects to the process method.

### 0.6.1 ###

 * The default logging handler (SentryHandler) will now accept a set of kwargs to instantiate
  a new client with (GH-10).
 * Fixed a bug with checksum generation when module or function were missing (GH-9).

## 0.6 ##

 * Added a Django-specific WSGI middleware.

### 0.5.1 ###

 * Two minor fixes for the Django client:
 * Ensure the __sentry__ key exists in data in (GH-8).
 * properly set ``kwargs['data']`` to an empty list when its a NoneType (GH-6).

## 0.5 ##

 * Require ``servers`` on base Client.
 * Added support for the ``site`` option in Client.
 * Moved ``raven.contrib.django.logging`` to ``raven.contrib.django.handlers``.

## 0.4 ##

 * Fixed an infinite loop in ``iter_tb``.

## 0.3 ##

 * Removed the ``thrashed`` key in ``request.sentry`` for the Django integration.
 * Changed the logging handler to correctly inherit old-style classes (GH-1).
 * Added a ``client`` argument to ``raven.contrib.django.models.get_client()``.

## 0.2 ##

 * auto_log_stacks now works with create_from_text
 * added Client.get_ident

## 0.1 ##

 * Initial version of raven (extracted from django-sentry 1.12.1).
